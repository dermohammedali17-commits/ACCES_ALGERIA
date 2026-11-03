from __future__ import annotations

import json
import logging
import os
import time
from collections.abc import Iterable
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any, ClassVar
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from src.data.reference.country_reference import CountryReference

log = logging.getLogger(__name__)

COMTRADE_PREVIEW_URL = (
    "https://comtradeapi.un.org/public/v1/preview/C/A/HS"
)

COMTRADE_DATA_URL = (
    "https://comtradeapi.un.org/data/v1/get/C/A/HS"
)

WORLD_BANK_URL = (
    "https://api.worldbank.org/v2/country"
)

PREVIEW_LIMIT = 500

USER_AGENT = "ACCESS-ALGERIA-Research/2.0"


def utc_now() -> datetime:
    return datetime.now(UTC)


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _retry_delay(
    attempt: int,
    retry_after: str | None = None,
) -> float:

    if retry_after:
        try:
            return min(max(float(retry_after), 0), 60)
        except ValueError:
            try:
                retry_date = parsedate_to_datetime(retry_after)

                if retry_date.tzinfo is None:
                    retry_date = retry_date.replace(
                        tzinfo=UTC
                    )

                seconds = (
                    retry_date - utc_now()
                ).total_seconds()

                return min(max(seconds, 0), 60)

            except (TypeError, ValueError, OverflowError):
                pass

    return min(2 ** attempt, 30)


class TradeRecord(BaseModel):

    model_config = ConfigDict(extra="allow")

    reporter_code: int
    partner_code: int

    period: str
    flow_code: str
    commodity_code: str

    trade_value_usd: float | None = None

    fob_value_usd: float | None = None
    cif_value_usd: float | None = None

    net_weight_kg: float | None = None

    reporter_name: str | None = None
    partner_name: str | None = None

    is_mirror_estimate: bool = False

    is_reported: bool | None = None
    is_aggregate: bool | None = None

    source: str

    retrieved_at: datetime = Field(default_factory=utc_now)


def audit_trade_duplicates(
    dataframe: pd.DataFrame,
    sample_limit: int = 10,
) -> dict[str, Any]:
    """Diagnose duplicate and potentially conflicting trade records.

    This function is read-only: it does not remove records or modify the input
    DataFrame. Direct and mirror sources are evaluated separately.
    """
    if sample_limit < 0:
        raise ValueError("sample_limit cannot be negative")

    if dataframe.empty:
        return {
            "total_records": 0,
            "exact_duplicate_groups": 0,
            "exact_duplicate_records": 0,
            "dimensional_collision_groups": 0,
            "cross_source_match_groups": 0,
            "direct_duplicates": 0,
            "mirror_duplicates": 0,
            "samples": {
                "exact_duplicates": [],
                "dimensional_collisions": [],
                "cross_source_matches": [],
            },
        }

    required_columns = [
        "reporter_code",
        "partner_code",
        "period",
        "flow_code",
        "commodity_code",
        "trade_value_usd",
        "fob_value_usd",
        "cif_value_usd",
        "net_weight_kg",
        "is_mirror_estimate",
        "is_reported",
        "is_aggregate",
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in dataframe.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing required columns: {missing_columns}"
        )

    base_key = [
        "reporter_code",
        "partner_code",
        "period",
        "flow_code",
        "commodity_code",
    ]

    value_columns = [
        "trade_value_usd",
        "fob_value_usd",
        "cif_value_usd",
        "net_weight_kg",
        "is_reported",
        "is_aggregate",
    ]

    source_column = "is_mirror_estimate"
    exact_key = base_key + value_columns + [source_column]
    working = dataframe.copy()

    # Exact duplicates are identified within the same source.
    exact_mask = working.duplicated(subset=exact_key, keep=False)
    exact_rows = working.loc[exact_mask]
    exact_groups = exact_rows.groupby(exact_key, dropna=False).size()

    exact_duplicate_groups = int((exact_groups > 1).sum())
    exact_duplicate_records = int(
        (exact_groups - 1).clip(lower=0).sum()
    )

    # Count excess exact duplicates separately by source.
    direct_duplicates = 0
    mirror_duplicates = 0

    if not exact_rows.empty:
        for _, group in exact_rows.groupby(exact_key, dropna=False):
            excess = len(group) - 1
            if bool(group.iloc[0][source_column]):
                mirror_duplicates += excess
            else:
                direct_duplicates += excess

    # A dimensional collision has the same base key and source, but different
    # retained values or record characteristics.
    collision_key = base_key + [source_column]
    collision_groups = working.groupby(collision_key, dropna=False)
    dimensional_collision_samples: list[dict[str, Any]] = []
    dimensional_collision_groups = 0

    for key, group in collision_groups:
        distinct_versions = group[value_columns].drop_duplicates()
        if len(distinct_versions) > 1:
            dimensional_collision_groups += 1
            if len(dimensional_collision_samples) < sample_limit:
                dimensional_collision_samples.append({
                    "key": list(key),
                    "record_count": len(group),
                    "distinct_versions": len(distinct_versions),
                })

    # Matching dimensions across Direct and Mirror are not duplicates.
    cross_source_samples: list[dict[str, Any]] = []
    cross_source_match_groups = 0

    for key, group in working.groupby(base_key, dropna=False):
        source_count = group[source_column].nunique(dropna=False)
        if source_count > 1:
            cross_source_match_groups += 1
            if len(cross_source_samples) < sample_limit:
                cross_source_samples.append({
                    "key": list(key),
                    "record_count": len(group),
                    "sources": sorted(
                        "MIRROR" if bool(value) else "DIRECT"
                        for value in group[source_column].unique()
                    ),
                })

    exact_samples = (
        exact_rows.head(sample_limit)
        .drop(columns=["retrieved_at"], errors="ignore")
        .to_dict(orient="records")
    )

    return {
        "total_records": len(working),
        "exact_duplicate_groups": exact_duplicate_groups,
        "exact_duplicate_records": exact_duplicate_records,
        "dimensional_collision_groups": dimensional_collision_groups,
        "cross_source_match_groups": cross_source_match_groups,
        "direct_duplicates": int(direct_duplicates),
        "mirror_duplicates": int(mirror_duplicates),
        "samples": {
            "exact_duplicates": exact_samples,
            "dimensional_collisions": dimensional_collision_samples,
            "cross_source_matches": cross_source_samples,
        },
    }

class MacroRecord(BaseModel):

    country: str = "DZA"

    indicator_code: str
    indicator_name: str

    year: int
    value: float

    source: str = "World Bank"

    retrieved_at: datetime = Field(default_factory=utc_now)


class ComtradeRESTClient:
    """
    UN Comtrade REST client.

    Preview API is used without an API key.
    Authenticated Data API is used when a key exists.
    """

    def __init__(
        self,
        timeout: int = 30,
        retries: int = 2,
    ):

        if timeout <= 0:
            raise ValueError("timeout must be positive")

        if retries < 0:
            raise ValueError("retries cannot be negative")

        self.timeout = timeout
        self.retries = retries

        self.api_key = os.getenv("COMTRADE_API_KEY")

        self.authenticated = bool(self.api_key)

        self.base_url = (
            COMTRADE_DATA_URL
            if self.authenticated
            else COMTRADE_PREVIEW_URL
        )

    @property
    def mode(self) -> str:

        return (
            "AUTHENTICATED"
            if self.authenticated
            else "PREVIEW"
        )

    def fetch(
        self,
        reporter: int,
        partner: int,
        year: int,
        flow: str,
        commodity: str = "87",
    ) -> list[dict[str, Any]]:

        params = {
            "reporterCode": reporter,
            "partnerCode": partner,
            "period": year,
            "flowCode": flow,
            "cmdCode": commodity,
            "motCode": 0,
            "partner2Code": 0,
            "breakdownMode": "classic",
        }

        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        }

        if self.api_key:
            headers["Ocp-Apim-Subscription-Key"] = self.api_key

        url = f"{self.base_url}?{urlencode(params)}"

        request = Request(url, headers=headers)

        for attempt in range(self.retries + 1):

            try:

                with urlopen(
                    request,
                    timeout=self.timeout,
                ) as response:

                    payload = json.loads(
                        response.read().decode("utf-8")
                    )

                if not isinstance(payload, dict):
                    raise TypeError(
                        "Invalid Comtrade response structure"
                    )

                if payload.get("error"):
                    raise ValueError(
                        "Comtrade API returned an error"
                    )

                records = payload.get("data")

                if not isinstance(records, list):
                    raise TypeError(
                        "Comtrade response data must be a list"
                    )

                return records

            except HTTPError as exc:

                retryable = (
                    exc.code == 429
                    or 500 <= exc.code < 600
                )

                if not retryable or attempt >= self.retries:

                    log.error(
                        "Comtrade HTTP failure: status=%s reporter=%s year=%s",
                        exc.code,
                        reporter,
                        year,
                    )

                    raise

                delay = _retry_delay(
                    attempt,
                    exc.headers.get("Retry-After")
                    if exc.headers
                    else None,
                )

                time.sleep(delay)

            except (URLError, TimeoutError, ConnectionError):

                if attempt >= self.retries:

                    log.exception(
                        "Comtrade connection failure: reporter=%s year=%s",
                        reporter,
                        year,
                    )

                    raise

                time.sleep(_retry_delay(attempt))

        return []


class WorldBankRESTClient:
    """
    World Bank Indicators API V2 client.
    """
    def __init__(
        self,
        timeout: int = 30,
        retries: int = 2,
        country_code: str = "DZA",
    ):
        if timeout <= 0:
            raise ValueError("timeout must be positive")

        if retries < 0:
            raise ValueError("retries cannot be negative")

        country_code = country_code.strip().upper()

        if not country_code:
            raise ValueError("country_code must not be empty")

        self.timeout = timeout
        self.retries = retries
        self.country_code = country_code
        
    def fetch(
        self,
        indicator: str,
        start_year: int,
        end_year: int,
    ) -> list[dict[str, Any]]:

        if start_year > end_year:
            raise ValueError(
                "start_year must not exceed end_year"
            )

        params = {
            "date": f"{start_year}:{end_year}",
            "format": "json",
            "per_page": 100,
        }

        url = (
            f"{WORLD_BANK_URL}/{self.country_code}/indicator/"
            f"{indicator}?{urlencode(params)}"
        )

        request = Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
            },
        )

        for attempt in range(self.retries + 1):

            try:

                with urlopen(
                    request,
                    timeout=self.timeout,
                ) as response:

                    payload = json.loads(
                        response.read().decode("utf-8")
                    )

                if (
                    not isinstance(payload, list)
                    or len(payload) < 2
                ):
                    raise ValueError(
                        "Invalid World Bank response envelope"
                    )

                metadata, records = payload[0], payload[1]

                if not isinstance(metadata, dict):
                    raise TypeError(
                        "Invalid World Bank metadata"
                    )

                if records is None:
                    return []

                if not isinstance(records, list):
                    raise TypeError(
                        "Invalid World Bank observations"
                    )

                return records

            except HTTPError as exc:

                retryable = (
                    exc.code == 429
                    or 500 <= exc.code < 600
                )

                if not retryable or attempt >= self.retries:

                    log.error(
                        "World Bank HTTP failure: indicator=%s status=%s",
                        indicator,
                        exc.code,
                    )

                    raise

                time.sleep(
                    _retry_delay(
                        attempt,
                        exc.headers.get("Retry-After")
                        if exc.headers
                        else None,
                    )
                )

            except (URLError, TimeoutError, ConnectionError):

                if attempt >= self.retries:

                    log.exception(
                        "World Bank connection failure: indicator=%s",
                        indicator,
                    )

                    raise

                time.sleep(_retry_delay(attempt))

        return []


class TradeMacroPipeline:
    """
    ACCESS ALGERIA external economic data pipeline.

    Sources:
    - UN Comtrade
    - World Bank Indicators API V2
    """

    MIRROR_REPORTER_PRIORITY = ("CHN", "TUR", "FRA", "DEU")

    INDICATORS: ClassVar[dict[str, str]] = {
        "NY.GDP.MKTP.CD": "GDP (current US$)",
        "NV.IND.MANF.ZS": (
            "Manufacturing value added (% GDP)"
        ),
        "TM.TAX.MRCH.WM.AR.ZS": (
            "Tariff rate, applied, weighted mean (%)"
        ),
    }

    def __init__(
        self,
        client: ComtradeRESTClient | None = None,
        world_bank_client: WorldBankRESTClient | None = None,
        country_reference: CountryReference | None = None,
    ):

        self.client = (
            client
            if client is not None
            else ComtradeRESTClient()
        )
        self.country_reference = (
            country_reference
            if country_reference is not None
            else CountryReference()
        )
        target_markets = (
            self.country_reference.get_target_markets()
        )
        if len(target_markets) != 1:
            raise ValueError(
                "Country reference must contain exactly "
                "one target market."
            )
        self.target_country = target_markets[0]

        if (
            self.target_country["is_active"].strip().lower()
            != "true"
        ):
            raise ValueError(
                "The target market must be active."
            )
        self.target_comtrade_code = int(
            self.target_country["comtrade_code"]
        )
        self.target_world_bank_code = (
            self.target_country["world_bank_code"]
        )
        self.target_iso3 = (
            self.target_country["iso3"]
        )
        self.mirror_reporters = (
            self._build_mirror_reporters()
        )
        self.world_bank_client = (
            world_bank_client
            if world_bank_client is not None
            else WorldBankRESTClient(
                country_code=self.target_world_bank_code
            )
        )
    def _build_mirror_reporters(self) -> tuple[int, ...]:
        active_countries = (
            self.country_reference.get_active_countries()
        )

        countries_by_iso3 = {
            country["iso3"].strip().upper(): country
            for country in active_countries
            if country["iso3"].strip().upper()
            != self.target_iso3.strip().upper()
        }

        reporter_codes = []

        for iso3 in self.MIRROR_REPORTER_PRIORITY:
            country = countries_by_iso3.get(iso3)

            if country is not None:
                reporter_codes.append(
                    int(country["comtrade_code"])
                )

        return tuple(reporter_codes)

    def _country_name(self, comtrade_code: int):
        country = (
            self.country_reference.get_by_comtrade_code(
                str(comtrade_code)
            )
        )

        if country is None:
            return None

        return country["country_name"]

    def _normalize(
        self,
        row: dict[str, Any],
        mirror: bool,
    ) -> TradeRecord:

        reporter_code = int(
            row.get("reporterCode", 0)
        )

        partner_code = int(
            row.get("partnerCode", 0)
        )

        reporter_name = (
            row.get("reporterDesc")
            or self._country_name(reporter_code)
        )

        partner_name = (
            row.get("partnerDesc")
            or self._country_name(partner_code)
        )

        return TradeRecord(
            reporter_code=reporter_code,
            partner_code=partner_code,
            period=str(row.get("period", "")),
            flow_code=str(row.get("flowCode", "")),
            commodity_code=str(row.get("cmdCode", "87")),
            trade_value_usd=_safe_float(
                row.get("primaryValue")
            ),
            fob_value_usd=_safe_float(
                row.get("fobvalue")
            ),
            cif_value_usd=_safe_float(
                row.get("cifvalue")
            ),
            net_weight_kg=_safe_float(
                row.get("netWgt")
            ),
            reporter_name=reporter_name,
            partner_name=partner_name,
            is_mirror_estimate=mirror,
            is_reported=row.get("isReported"),
            is_aggregate=row.get("isAggregate"),
            source=(
                "UN Comtrade mirror exports"
                if mirror
                else "UN Comtrade direct imports"
            ),
        )

    @staticmethod
    def _status(
        success: bool,
        partial: bool = False,
    ) -> str:

        if not success:
            return "FAILED"

        if partial:
            return "PARTIAL"

        return "SUCCESS"
    

    def fetch_trade_with_report(
        self,
        years: Iterable[int],
    ) -> tuple[pd.DataFrame, dict[str, Any]]:

        requested_years = sorted(
            set(map(int, years))
        )

        if not requested_years:
            raise ValueError(
                "At least one year must be provided"
            )

        output = []
        year_reports = []

        for year in requested_years:

            if year < 1900 or year > utc_now().year:
                raise ValueError(
                    f"Invalid trade year: {year}"
                )

            direct_error = None
            mirror_errors = []

            try:
                direct = self.client.fetch(
                    self.target_comtrade_code,
                    0,
                    year,
                    "M",
                )

            except (OSError, ValueError, TypeError) as exc:
                direct = []
                direct_error = type(exc).__name__

            if direct:

                try:
                    normalized = [
                        self._normalize(row, False).model_dump()
                        for row in direct
                    ]

                except (ValueError, TypeError, KeyError, AttributeError) as exc:
                    direct_error = type(exc).__name__
                    direct = []

                else:
                    output.extend(normalized)

                    year_reports.append({
                        "year": year,
                        "status": "SUCCESS",
                        "source_type": "DIRECT_IMPORTS",
                        "records": len(normalized),
                        "mirror_estimate": False,
                        "direct_import_error": None,
                        "mirror_errors": [],
                    })

                    continue

            mirror_count = 0
            mirror_rejected_count = 0
            successful_reporters = []

            for reporter in self.mirror_reporters:

                try:

                    rows = self.client.fetch(
                        reporter,
                        12,
                        year,
                        "X",
                    )

                    normalized = []

                    for row in rows:
                        try:
                            record = self._normalize(row, True)
                            normalized.append(record.model_dump())

                        except (ValueError, TypeError, KeyError, AttributeError) as exc:
                            mirror_rejected_count += 1
                            mirror_errors.append({
                                "reporter": reporter,
                                "error": type(exc).__name__,
                                "record_rejected": True,
                            })

                    output.extend(normalized)

                    if normalized:
                        successful_reporters.append(reporter)

                    mirror_count += len(normalized)

                except (OSError, ValueError, TypeError) as exc:

                    mirror_errors.append({

                        "reporter": reporter,
                        "error": type(exc).__name__,

                    })

                time.sleep(0.15)

            if mirror_count:

                year_reports.append({

                    "year": year,
                    "status": "PARTIAL",
                    "source_type": "MIRROR_ESTIMATE",

                    "records": mirror_count,
                    "rejected_records": mirror_rejected_count,

                    "mirror_estimate": True,

                    "successful_reporters": successful_reporters,
                

                    "direct_import_error": direct_error,
                    "mirror_errors": mirror_errors,

                    "warning": (
                        "Mirror exports are not equivalent "
                        "to direct Algerian import declarations."
                    ),

                })

            else:

                year_reports.append({

                    "year": year,
                    "status": "FAILED",
                    "source_type": "UNAVAILABLE",

                    "records": 0,
                    "rejected_records": mirror_rejected_count,

                    "mirror_estimate": False,

                    "direct_import_error": direct_error,
                    "mirror_errors": mirror_errors,

                })

        dataframe = pd.DataFrame(output)

        retrieved_years = (
            sorted(
                {
                    int(value)
                    for value in dataframe["period"].unique()
                }
            )
            if not dataframe.empty
            else []
        )

        missing_years = sorted(
            set(requested_years) - set(retrieved_years)
        )

        statuses = [
            item["status"]
            for item in year_reports
        ]

        overall_status = (
            "FAILED"
            if not any(status != "FAILED" for status in statuses)
            else "PARTIAL"
            if any(status != "SUCCESS" for status in statuses)
            else "SUCCESS"
        )

        endpoint_mode = getattr(
            self.client,
            "mode",
            "CUSTOM_CLIENT",
        )

        report = {

            "source": "UN Comtrade",
            "endpoint_mode": endpoint_mode,

            "status": overall_status,

            "requested_years": requested_years,
            "retrieved_years": retrieved_years,
            "missing_years": missing_years,

            "record_count": len(dataframe),

            "retrieved_at": utc_now().isoformat(),

            "preview_limit": (
                PREVIEW_LIMIT
                if endpoint_mode == "PREVIEW"
                else None
            ),

            "preview_warning": (
                "Preview responses may be limited to 500 records."
                if endpoint_mode == "PREVIEW"
                else None
            ),

            "years": year_reports,

        }

        dataframe.attrs["retrieval_report"] = report

        return dataframe, report

    def fetch_trade(
        self,
        years: Iterable[int],
    ) -> pd.DataFrame:

        dataframe, _ = self.fetch_trade_with_report(years)

        return dataframe

    def fetch_macro_with_report(
        self,
        start_year: int,
        end_year: int,
    ) -> tuple[pd.DataFrame, dict[str, Any]]:

        if start_year > end_year:
            raise ValueError(
                "start_year must not exceed end_year"
            )

        if start_year < 1900 or end_year > utc_now().year:
            raise ValueError(
                "Invalid World Bank year range"
            )

        requested_years = list(
            range(start_year, end_year + 1)
        )

        output = []
        indicator_reports = []

        for code, name in self.INDICATORS.items():

            indicator_error = None
            valid_years = []

            try:

                records = self.world_bank_client.fetch(
                    code,
                    start_year,
                    end_year,
                )

                for row in records:

                    if row.get("value") is None:
                        continue

                    year = int(row["date"])

                    value = _safe_float(row.get("value"))

                    if value is None:
                        continue

                    if year not in requested_years:
                        continue

                    valid_years.append(year)

                    output.append(
                        MacroRecord(
                            country=self.target_iso3,

                            indicator_code=code,
                            indicator_name=name,

                            year=year,
                            value=value,

                        ).model_dump()
                    )

            except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:

                indicator_error = type(exc).__name__

                log.exception("World Bank indicator failed: %s", code)

            retrieved_years = sorted(
                set(valid_years)
            )

            missing_years = sorted(
                set(requested_years) - set(retrieved_years)
            )

            if indicator_error or not retrieved_years:
                status = "FAILED"

            elif missing_years:
                status = "PARTIAL"

            else:
                status = "SUCCESS"

            indicator_reports.append({

                "indicator_code": code,
                "indicator_name": name,

                "status": status,

                "requested_years": requested_years,
                "retrieved_years": retrieved_years,
                "missing_years": missing_years,

                "record_count": len(retrieved_years),

                "error": indicator_error,

            })

        dataframe = pd.DataFrame(output)

        statuses = [
            item["status"]
            for item in indicator_reports
        ]

        overall_status = (
            "SUCCESS"
            if all(status == "SUCCESS" for status in statuses)
            else "FAILED"
            if all(status == "FAILED" for status in statuses)
            else "PARTIAL"
        )

        report = {

            "source": "World Bank",
            "endpoint_mode": "REST_API_V2",

            "status": overall_status,

            "country": self.target_iso3,

            "requested_years": requested_years,

            "record_count": len(dataframe),

            "retrieved_at": utc_now().isoformat(),

            "indicators": indicator_reports,

        }

        dataframe.attrs["retrieval_report"] = report

        return dataframe, report

    def fetch_macro(
        self,
        start_year: int,
        end_year: int,
    ) -> pd.DataFrame:

        dataframe, _ = self.fetch_macro_with_report(
            start_year,
            end_year,
        )
        return dataframe

