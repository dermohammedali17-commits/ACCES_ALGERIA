"""Offline tests for the Comtrade adapter and the mirror-trade PoC (synthetic data, no network)."""

import pandas as pd
import pytest

from src.infrastructure.adapters.comtrade_adapter import ComtradeAdapter, normalize
from src.poc.mirror_trade import build_comparison, top_partners


def raw(rows):
    return pd.DataFrame(rows)


def test_normalize_coerces_types_and_drops_empty_values():
    df = raw([
        {"period": 2023, "reporterCode": 12, "partnerCode": 276, "flowCode": "M",
         "cmdCode": 8703, "primaryValue": "1000.5", "junk": "x"},
        {"period": 2023, "reporterCode": 12, "partnerCode": 156, "flowCode": "M",
         "cmdCode": 8703, "primaryValue": None, "junk": "y"},
    ])
    out = normalize(df)
    assert len(out) == 1
    assert out.loc[0, "primaryValue"] == 1000.5
    assert out.loc[0, "cmdCode"] == "8703"
    assert out.loc[0, "refYear"] == 2023
    assert "junk" not in out.columns


def test_normalize_empty_and_none():
    assert normalize(None).empty
    assert normalize(pd.DataFrame()).empty


def test_build_comparison_hand_calculated():
    direct = normalize(raw([
        {"period": 2022, "reporterCode": 12, "partnerCode": 276, "cmdCode": "8703", "primaryValue": 600},
        {"period": 2022, "reporterCode": 12, "partnerCode": 156, "cmdCode": "8703", "primaryValue": 400},
        {"period": 2022, "reporterCode": 12, "partnerCode": 0,   "cmdCode": "8703", "primaryValue": 1000},  # World row
    ]))
    mirror = normalize(raw([
        {"period": 2022, "reporterCode": 97,  "partnerCode": 12, "cmdCode": "8703", "primaryValue": 500},
        {"period": 2022, "reporterCode": 156, "partnerCode": 12, "cmdCode": "8703", "primaryValue": 350},
    ]))
    out = build_comparison(direct, mirror)
    row = out.iloc[0]
    assert row["direct_import_usd"] == 1000          # World aggregate excluded -> no double counting
    assert row["mirror_export_usd"] == 850
    assert row["gap_usd"] == 150
    assert row["mirror_to_direct_ratio"] == 0.85
    assert row["best_available_usd"] == 1000
    assert row["source_note"] == "both"


def test_build_comparison_flags_mirror_only_year():
    direct = normalize(raw([
        {"period": 2022, "reporterCode": 12, "partnerCode": 276, "cmdCode": "8703", "primaryValue": 100},
    ]))
    mirror = normalize(raw([
        {"period": 2022, "reporterCode": 97, "partnerCode": 12, "cmdCode": "8703", "primaryValue": 90},
        {"period": 2023, "reporterCode": 97, "partnerCode": 12, "cmdCode": "8703", "primaryValue": 120},
    ]))
    out = build_comparison(direct, mirror).set_index("refYear")
    assert out.loc[2023, "source_note"].startswith("MIRROR ONLY")
    assert out.loc[2023, "best_available_usd"] == 120


def test_top_partners_orders_by_value():
    direct = normalize(raw([
        {"period": 2022, "partnerCode": 276, "partnerDesc": "Germany", "cmdCode": "8703", "primaryValue": 10},
        {"period": 2022, "partnerCode": 156, "partnerDesc": "China", "cmdCode": "8703", "primaryValue": 30},
        {"period": 2022, "partnerCode": 0, "partnerDesc": "World", "cmdCode": "8703", "primaryValue": 40},
    ]))
    top = top_partners(direct, 2022, n=2)
    assert list(top["partnerDesc"]) == ["China", "Germany"]


# --- adapter behaviour -----------------------------------------------------


def make_adapter(tmp_path, fetch):
    return ComtradeAdapter(fetch_fn=fetch, cache_dir=tmp_path, min_interval_s=0, max_retries=3)


def test_adapter_caches_identical_requests(tmp_path):
    calls = []

    def fake(**params):
        calls.append(params)
        return raw([{"period": 2022, "reporterCode": 12, "partnerCode": 276,
                     "cmdCode": "8703", "primaryValue": 5}])

    a = make_adapter(tmp_path, fake)
    first = a.fetch_flows("12", "M", [2022], ["8703"])
    second = a.fetch_flows("12", "M", [2022], ["8703"])
    assert len(calls) == 1                      # second call served from local cache
    assert first.loc[0, "primaryValue"] == second.loc[0, "primaryValue"] == 5


def test_adapter_retries_then_succeeds(tmp_path, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    state = {"n": 0}

    def flaky(**params):
        state["n"] += 1
        if state["n"] < 3:
            raise ConnectionError("boom")
        return raw([{"period": 2022, "cmdCode": "8703", "primaryValue": 1}])

    out = make_adapter(tmp_path, flaky).fetch_flows("12", "M", [2022], ["8703"])
    assert state["n"] == 3 and len(out) == 1


def test_adapter_raises_after_max_retries(tmp_path, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)

    def always_fail(**params):
        raise ConnectionError("down")

    with pytest.raises(RuntimeError):
        make_adapter(tmp_path, always_fail).fetch_flows("12", "M", [2022], ["8703"])


def test_adapter_builds_expected_request(tmp_path):
    seen = {}

    def spy(**params):
        seen.update(params)
        return pd.DataFrame()

    make_adapter(tmp_path, spy).fetch_flows("97", "X", [2021, 2022], ["8703", "8704"], partner_code="12")
    assert seen["reporterCode"] == "97"
    assert seen["flowCode"] == "X"
    assert seen["partnerCode"] == "12"
    assert seen["period"] == "2021,2022"
    assert seen["cmdCode"] == "8703,8704"
    assert seen["clCode"] == "HS"


def test_run_fails_loudly_when_api_returns_nothing(tmp_path, monkeypatch):
    from src.poc import mirror_trade

    monkeypatch.setattr(mirror_trade, "OUTPUT_DIR", tmp_path / "out")
    adapter = make_adapter(tmp_path, lambda **p: None)
    with pytest.raises(RuntimeError, match="No data returned"):
        mirror_trade.run(2022, 2022, adapter=adapter)
    assert not (tmp_path / "out").exists()      # no misleading empty output file


def test_run_end_to_end_with_fake_api(tmp_path, monkeypatch):
    from src.poc import mirror_trade

    monkeypatch.setattr(mirror_trade, "OUTPUT_DIR", tmp_path / "out")

    def fake(**p):
        if p["flowCode"] == "M":
            return raw([{"period": 2022, "reporterCode": 12, "partnerCode": 276,
                         "cmdCode": "8703", "primaryValue": 1000}])
        return raw([{"period": 2022, "reporterCode": int(p["reporterCode"]), "partnerCode": 12,
                     "cmdCode": "8703", "primaryValue": 100}])

    out = mirror_trade.run(2022, 2022, hs_codes=["8703"], adapter=make_adapter(tmp_path, fake))
    assert out.loc[0, "direct_import_usd"] == 1000
    assert out.loc[0, "mirror_export_usd"] == 500            # 5 default reporters x 100
    assert (tmp_path / "out" / "algeria_hs87_mirror_trade.csv").exists()
