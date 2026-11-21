import json
from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from src.data.mie.engine import MarketIntelligenceEngine
from src.data.mie.metadata import SOURCES, WORLD_BANK_SOURCES
from src.data.mie.models import EvidenceBundle, Observation, Retrieval
from src.data.mie.persistence import freshness, load_bundle, retention_due, save_bundle
from src.data.mie.presentation import render_evidence


class FakeWorldBank:
    def fetch(self, indicator, start_year, end_year):
        if indicator == "NV.IND.MANF.ZS":
            raise RuntimeError("provider unreachable")
        if indicator == "TM.TAX.MRCH.WM.AR.ZS":
            pytest.fail("pending tariff must not be queried")
        return [{"date": str(start_year), "value": 12.5},
                {"date": str(end_year), "value": None}]


class FakeComtrade:
    def __init__(self):
        self.calls = []
        self._fetch = lambda **params: None

    def fetch_flows(self, reporter, flow, years, codes, partner_code=None):
        self.calls.append((reporter, flow, tuple(years), tuple(codes), partner_code))
        if flow == "X" and reporter == "156":
            raise RuntimeError("one mirror reporter unavailable")
        if flow == "X":
            return pd.DataFrame(columns=["refYear", "cmdCode", "primaryValue"])
        return pd.DataFrame([{"refYear": 2022, "cmdCode": "8703",
                              "primaryValue": 100, "reporterCode": "12"}])


def test_metadata_contract_has_stable_ids_and_pending_tariff():
    assert set(WORLD_BANK_SOURCES) == {
        "NY.GDP.MKTP.CD", "NV.IND.MANF.ZS", "TM.TAX.MRCH.WM.AR.ZS"
    }
    assert all(item.version and item.provider and item.definition and item.unit
               and item.geography and item.temporal_granularity
               and item.query_defaults and item.limitations and item.retrieval_semantics
               for item in SOURCES.values())
    assert WORLD_BANK_SOURCES["TM.TAX.MRCH.WM.AR.ZS"].status == "PENDING_VALIDATION"
    assert SOURCES["comtrade.algeria_direct_imports"].query_defaults["flow"] == "M"
    assert SOURCES["comtrade.selected_reporter_mirror_exports"].query_defaults["flow"] == "X"


def test_engine_keeps_direct_and_mirror_separate_and_reports_coverage():
    comtrade = FakeComtrade()
    bundle = MarketIntelligenceEngine(comtrade, FakeWorldBank()).collect(2022, 2023)
    direct = [item for item in bundle.retrievals
              if item.source_id == "comtrade.algeria_direct_imports"]
    mirrors = [item for item in bundle.retrievals
               if item.source_id == "comtrade.selected_reporter_mirror_exports"]
    assert len(direct) == 1 and direct[0].status == "PARTIAL"
    assert len(mirrors) == 5
    assert any(item.status == "FAILED" for item in mirrors)
    assert all(call[3] == ("8703", "8704") for call in comtrade.calls)
    assert all(not (call[0] == "12" and call[1] == "X") for call in comtrade.calls)
    assert not any(item.indicator_id == "TM.TAX.MRCH.WM.AR.ZS" for item in bundle.observations)
    assert all(item.validation_status == "UNVERIFIED" and item.confidence_level is None
               for item in bundle.observations)
    assert any(item.status == "PENDING_VALIDATION" for item in bundle.retrievals)
    assert any(item.status == "FAILED" for item in bundle.retrievals)
    assert any(item.status == "UNCONFIRMED_EMPTY" for item in bundle.retrievals)
    assert all(item.status != "NO_DATA" for item in mirrors)
    assert any("without HTTP status and total count" in warning
               for retrieval in mirrors for warning in retrieval.warnings)
    assert any("does not expose pagination, total-count" in warning
               for retrieval in bundle.retrievals for warning in retrieval.warnings)
    direct_observation = next(item for item in bundle.observations
                              if item.source_id == "comtrade.algeria_direct_imports")
    assert "reporterCode=12" in direct_observation.source_url
    assert "cmdCode=8703%2C8704" in direct_observation.source_url
    assert not hasattr(bundle, "score")


def test_invalid_year_range_rejected():
    with pytest.raises(ValueError):
        MarketIntelligenceEngine(FakeComtrade(), FakeWorldBank()).collect(2024, 2022)


def test_comtrade_confirmed_empty_and_provider_failure_remain_distinct():
    class DiagnosticComtrade:
        mode = "PREVIEW"

        def __init__(self, failure=False):
            self.failure = failure
            self.last_diagnostics = {}

        def fetch_flows(self, *args, **kwargs):
            if self.failure:
                self.last_diagnostics = {"response": "ERROR", "http_status": 503,
                                         "provider_message": "temporarily unavailable"}
                raise RuntimeError("provider failure")
            self.last_diagnostics = {"response": "HTTP_RESPONSE", "http_status": 200,
                                     "total_count": 0,
                                     "parameters": {"reporterCode": "12",
                                                    "partnerCode": "0", "flowCode": "M",
                                                    "period": "2023", "cmdCode": "8703,8704"}}
            return pd.DataFrame()

    confirmed = MarketIntelligenceEngine(
        DiagnosticComtrade(), FakeWorldBank()).collect(2023, 2023)
    direct = next(item for item in confirmed.retrievals
                  if item.source_id == "comtrade.algeria_direct_imports")
    assert direct.status == "NO_DATA"
    assert direct.record_count == 0
    assert direct.diagnostics["total_count"] == 0
    assert direct.missing_periods == ("2023",)

    failed_bundle = MarketIntelligenceEngine(
        DiagnosticComtrade(failure=True), FakeWorldBank()).collect(2023, 2023)
    failed = next(item for item in failed_bundle.retrievals
                  if item.source_id == "comtrade.algeria_direct_imports")
    assert failed.status == "FAILED"
    assert failed.diagnostics["http_status"] == 503
    assert failed.missing_periods == ("2023",)


def make_bundle():
    observation = Observation(
        "world_bank.gdp_current_usd", "NY.GDP.MKTP.CD", None, "current US$",
        "Algeria (DZA)", "2023", "WORLD_BANK_API",
        "https://example.test/data?token=secret&date=2023", datetime.now(UTC).isoformat(),
    )
    retrieval = Retrieval("wb-1", observation.source_id, "NO_DATA", ("2023",), (),
                          ("2023",), "WORLD_BANK_API", 0)
    return EvidenceBundle.create(parameters={"api_key": "secret"}, observations=[observation],
                                 retrievals=[retrieval])


def test_bundle_round_trip_redacts_secrets_and_is_fresh(tmp_path):
    path = save_bundle(make_bundle(), tmp_path)
    content = path.read_text(encoding="utf-8")
    assert "secret" not in content
    assert "token" not in content
    loaded = load_bundle(path)
    assert loaded["schema_version"] == "1.0"
    assert loaded["observations"][0]["value"] is None
    assert loaded["parameters"]["api_key"] == "[REDACTED]"
    assert "date=2023" in loaded["observations"][0]["source_url"]
    assert freshness(path, datetime.now(UTC) + timedelta(days=91))["refresh_due"]


def test_retention_rules_are_explicit_and_non_deleting():
    retrieved = datetime(2024, 2, 29, tzinfo=UTC)
    assert not retention_due(retrieved, "normalized_data", datetime(2026, 2, 27, tzinfo=UTC))
    assert retention_due(retrieved, "normalized_data", datetime(2026, 2, 28, tzinfo=UTC))
    assert retention_due(retrieved, "evidence_bundle", datetime(2029, 2, 28, tzinfo=UTC))
    with pytest.raises(ValueError, match="Unknown artifact"):
        retention_due(retrieved, "unknown", retrieved)


def test_bundle_uses_safe_filename_and_rejects_unknown_version(tmp_path):
    bundle = make_bundle()
    path = save_bundle(bundle, tmp_path)
    assert path.parent == tmp_path
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["schema_version"] = "99"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="schema version"):
        load_bundle(path)


def test_presentation_includes_provenance_and_missing_coverage_only():
    bundle = make_bundle()
    text = render_evidence(bundle)
    assert "NO_DATA" in text
    assert "missing none" not in text
    assert "FACT" in text
    assert "score" not in text.lower()
