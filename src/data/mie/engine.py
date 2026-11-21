"""Narrow offline-testable orchestration over existing provider adapters."""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

import pandas as pd

from src.data.mie.metadata import (
    COMTRADE_DIRECT,
    COMTRADE_MIRROR,
    WORLD_BANK_SOURCES,
)
from src.data.mie.models import EvidenceBundle, Observation, Retrieval
from src.data.trade_pipeline import WorldBankRESTClient
from src.infrastructure.adapters.comtrade_adapter import ComtradeAdapter


class MarketIntelligenceEngine:
    def __init__(self, comtrade: Any | None = None, world_bank: Any | None = None) -> None:
        self.comtrade = (comtrade if comtrade is not None else
                         ComtradeAdapter(strict_errors=True))
        self.world_bank = world_bank if world_bank is not None else WorldBankRESTClient()

    def collect(self, start_year: int, end_year: int) -> EvidenceBundle:
        if start_year > end_year:
            raise ValueError("start_year must not exceed end_year")
        years = list(range(start_year, end_year + 1))
        periods = tuple(str(year) for year in years)
        observations: list[Observation] = []
        retrievals: list[Retrieval] = []
        self._collect_world_bank(years, periods, observations, retrievals)
        # Partner 0 is the explicit World aggregate. Omitting partnerCode can
        # return partner-level rows or provider-dependent defaults.
        self._collect_trade(years, periods, observations, retrievals, "12", "M", "0",
                            COMTRADE_DIRECT)
        reporters = COMTRADE_MIRROR.query_defaults["reporters"]
        for reporter in reporters:
            self._collect_trade(years, periods, observations, retrievals, reporter, "X", "12",
                                COMTRADE_MIRROR)
        return EvidenceBundle.create(
            parameters={"start_year": start_year, "end_year": end_year,
                        "hs_codes": ["8703", "8704"], "mirror_reporters": reporters},
            observations=observations, retrievals=retrievals,
        )

    def _collect_world_bank(self, years: list[int], periods: tuple[str, ...],
                            observations: list[Observation], retrievals: list[Retrieval]) -> None:
        for code, source in WORLD_BANK_SOURCES.items():
            if source.status != "ACTIVE":
                retrievals.append(Retrieval(
                    f"{source.source_id}:{periods[0]}-{periods[-1]}", source.source_id,
                    "PENDING_VALIDATION", periods, (), periods, "NOT_QUERIED", 0,
                    ("Indicator excluded from conclusions pending validation.",),
                ))
                continue
            self._retrieve_world_bank(code, source, years, periods, observations, retrievals)

    def _retrieve_world_bank(self, code: str, source: Any, years: list[int],
                             periods: tuple[str, ...], observations: list[Observation],
                             retrievals: list[Retrieval]) -> None:
        rid = f"{source.source_id}:{periods[0]}-{periods[-1]}"
        try:
            rows = self.world_bank.fetch(code, years[0], years[-1])
            if not isinstance(rows, list):
                raise TypeError("World Bank adapter must return a list")
            valid: set[str] = set()
            now = datetime.now(UTC).isoformat()
            for row in rows:
                try:
                    year = str(int(row["date"]))
                    raw = row.get("value")
                    value = float(raw) if raw is not None else None
                except (KeyError, TypeError, ValueError, OverflowError):
                    continue
                if year not in periods or value is None or not math.isfinite(value):
                    continue
                observations.append(Observation(
                    source.source_id, code, value, source.unit, source.geography, year,
                    "WORLD_BANK_API", f"https://api.worldbank.org/v2/country/DZA/indicator/{code}", now,
                ))
                valid.add(year)
            missing = tuple(period for period in periods if period not in valid)
            status = "SUCCESS" if not missing else "PARTIAL" if valid else "NO_DATA"
            retrievals.append(Retrieval(rid, source.source_id, status, periods,
                                         tuple(sorted(valid)), missing, "WORLD_BANK_API", len(valid)))
        except Exception as exc:  # noqa: BLE001 -- capture provider failures as retrieval status
            retrievals.append(Retrieval(rid, source.source_id, "FAILED", periods, (), periods,
                                         "WORLD_BANK_API", 0, error=type(exc).__name__))

    def _collect_trade(self, years: list[int], periods: tuple[str, ...],
                       observations: list[Observation], retrievals: list[Retrieval],
                       reporter: str, flow: str, partner: str | None, source: Any) -> None:
        rid = f"{source.source_id}:{reporter}:{periods[0]}-{periods[-1]}"
        source_mode = "UNKNOWN"
        diagnostics: dict[str, Any] = {}
        try:
            frame = self.comtrade.fetch_flows(reporter, flow, years, ["8703", "8704"],
                                              partner_code=partner)
            if not isinstance(frame, pd.DataFrame):
                raise TypeError("Comtrade adapter must return a DataFrame")
            if hasattr(self.comtrade, "mode"):
                source_mode = self.comtrade.mode
            elif hasattr(self.comtrade, "authenticated"):
                source_mode = "AUTHENTICATED" if self.comtrade.authenticated else "PREVIEW"
            elif hasattr(self.comtrade, "_fetch"):
                source_mode = "CONFIGURED_ADAPTER"
            now = datetime.now(UTC).isoformat()
            diagnostics = dict(getattr(self.comtrade, "last_diagnostics", {}) or {})
            valid: set[str] = set()
            for row in frame.to_dict(orient="records"):
                year = str(row.get("refYear", row.get("period", "")))[:4]
                if year not in periods:
                    continue
                value = row.get("primaryValue")
                if pd.isna(value) or (value is not None and not math.isfinite(float(value))):
                    value = None
                observations.append(Observation(
                    source.source_id, str(row.get("cmdCode", "unknown")),
                    float(value) if value is not None else None, source.unit,
                    source.geography, year, f"COMTRADE_{flow}_{source_mode}",
                    ("https://comtradeapi.un.org/public/v1/preview/C/A/HS"
                     if source_mode == "PREVIEW" else
                     "https://comtradeapi.un.org/data/v1/get/C/A/HS"
                     if source_mode == "AUTHENTICATED" else
                     "https://comtradeapi.un.org/")
                    + "?" + urlencode({"reporterCode": reporter,
                                      "partnerCode": partner or "0",
                                      "period": year, "flowCode": flow,
                                      "cmdCode": "8703,8704"}), now,
                    attributes={str(key): value for key, value in row.items()
                                if key != "primaryValue"},
                ))
                if value is not None:
                    valid.add(year)
            missing = tuple(period for period in periods if period not in valid)
            confirmed_empty = (frame.empty and diagnostics.get("http_status") == 200
                               and diagnostics.get("total_count") == 0)
            status = ("SUCCESS" if not missing else "PARTIAL" if valid else
                      "NO_DATA" if confirmed_empty else
                      "UNCONFIRMED_EMPTY" if frame.empty else "NO_DATA")
            warnings: tuple[str, ...] = (
                "Adapter does not expose pagination, total-count, or per-commodity "
                "completeness; period coverage means at least one valid observation "
                "for that year, not complete coverage of both HS codes.",
            )
            if frame.empty and not confirmed_empty:
                warnings += ("Comtrade returned no rows without HTTP status and total count "
                             "confirming a valid zero-result response; treat as unresolved.",)
            retrievals.append(Retrieval(rid, source.source_id, status, periods,
                                         tuple(sorted(valid)), missing, source_mode, len(frame),
                                         warnings +
                                         (("Preview results may be capped; response is not a completeness claim.",)
                                          if source_mode == "PREVIEW" else
                                          ("Adapter does not expose authenticated/preview mode; "
                                           "completeness is not asserted.",)
                                          if source_mode == "CONFIGURED_ADAPTER" else ()),
                                         diagnostics=diagnostics))
        except Exception as exc:  # noqa: BLE001 -- capture provider failures as retrieval status
            diagnostics = dict(getattr(self.comtrade, "last_diagnostics", {}) or {})
            retrievals.append(Retrieval(rid, source.source_id, "FAILED", periods, (), periods,
                                         source_mode, 0, error=type(exc).__name__,
                                         diagnostics=diagnostics))
