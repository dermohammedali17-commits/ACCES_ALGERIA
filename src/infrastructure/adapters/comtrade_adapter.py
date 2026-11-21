"""UN Comtrade adapter (wraps `comtradeapicall`).

Implements the execution boundary from the blueprint: API key management, rate limiting,
retry with backoff and local caching, so the rest of the system never calls the API directly.

Key handling
  * COMTRADE_API_KEY set  -> authenticated `getFinalData` (large queries, higher limits)
  * no key                -> public `previewFinalData` (free, max 500 records per call)
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Optional
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

ALGERIA_CODE = "12"
HS_CLASSIFICATION = "HS"

# Columns we keep (only those present in the response are used).
KEEP_COLUMNS = [
    "refYear", "period", "reporterCode", "reporterDesc", "partnerCode", "partnerDesc",
    "flowCode", "cmdCode", "cmdDesc", "qtyUnitCode", "qty", "netWgt", "primaryValue",
]

DEFAULT_CACHE_DIR = Path(__file__).resolve().parents[3] / "data" / "cache" / "comtrade"

FetchFn = Callable[..., pd.DataFrame | None]


class _ComtradeResponseError(RuntimeError):
    """Provider rejected a request; retain safe HTTP diagnostics for the adapter."""

    def __init__(self, status: int, payload: object) -> None:
        super().__init__(f"Comtrade returned HTTP {status}")
        self.code = status
        self.payload = payload


def _default_fetch(**params) -> pd.DataFrame | None:
    """Call Comtrade and preserve response metadata lost by comtradeapicall."""
    key = os.environ.get("COMTRADE_API_KEY", "").strip()
    access_path = "data/v1/get" if key else "public/v1/preview"
    endpoint = "https://comtradeapi.un.org/{}/{}/{}/{}".format(
        access_path, params["typeCode"], params["freqCode"], params["clCode"]
    )
    query = {
        "reportercode": params.get("reporterCode"),
        "flowCode": params.get("flowCode"),
        "period": params.get("period"),
        "cmdCode": params.get("cmdCode"),
        "partnerCode": params.get("partnerCode"),
        "partner2Code": params.get("partner2Code"),
        "motCode": params.get("motCode"),
        "customsCode": params.get("customsCode"),
        "maxRecords": params.get("maxRecords"),
        "format": params.get("format_output"),
        "aggregateBy": params.get("aggregateBy"),
        "breakdownMode": params.get("breakdownMode"),
        "countOnly": params.get("countOnly"),
        "includeDesc": params.get("includeDesc"),
    }
    if key:
        # Match the existing client contract. This value is never included in diagnostics.
        query["subscription-key"] = key
    query_string = urlencode({name: value for name, value in query.items() if value is not None})
    request = Request(f"{endpoint}?{query_string}", headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=120) as response:
            status = response.status
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raw_body = exc.read()
        try:
            payload = json.loads(raw_body.decode("utf-8")) if raw_body else None
        except (UnicodeDecodeError, json.JSONDecodeError):
            payload = raw_body.decode("utf-8", errors="replace")[:1000] if raw_body else None
        raise _ComtradeResponseError(exc.code, payload) from None

    if not isinstance(payload, dict):
        raise TypeError("Comtrade returned an unexpected JSON response")
    provider_error = payload.get("error")
    if provider_error:
        raise _ComtradeResponseError(status, {"error": provider_error})

    if params.get("countOnly"):
        frame = pd.DataFrame([{"count": payload.get("count")}])
    else:
        rows = payload.get("data")
        if not isinstance(rows, list):
            raise TypeError("Comtrade response did not contain a data list")
        frame = pd.json_normalize(rows)

    # attrs flow through the adapter before normalization, without changing returned columns.
    frame.attrs.update({
        "http_status": status,
        "total_count": payload.get("count"),
        "provider_error": provider_error or "",
    })
    for name in ("page", "pages", "has_more", "pagination"):
        if name in payload:
            frame.attrs[name] = payload[name]
    return frame


class ComtradeAdapter:
    def __init__(
        self,
        fetch_fn: FetchFn | None = None,
        cache_dir: Path | str = DEFAULT_CACHE_DIR,
        min_interval_s: float = 1.2,
        max_retries: int = 3,
        use_cache: bool = True,
        strict_errors: bool = False,
    ) -> None:
        self._fetch = fetch_fn or _default_fetch
        self.cache_dir = Path(cache_dir)
        self.min_interval_s = min_interval_s
        self.max_retries = max_retries
        self.use_cache = use_cache
        self.strict_errors = strict_errors
        self._last_call = 0.0
        self.last_diagnostics: dict[str, object] = {}

    # -- internals ---------------------------------------------------------

    def _cache_path(self, params: dict) -> Path:
        # Preview and authenticated responses have different coverage and limits.
        cache_key = {**params, "_access_mode": self.mode}
        digest = hashlib.sha256(json.dumps(cache_key, sort_keys=True).encode()).hexdigest()[:20]
        return self.cache_dir / f"{digest}.json"

    @property
    def authenticated(self) -> bool:
        """Whether the current process is configured to use authenticated access."""
        return bool(os.environ.get("COMTRADE_API_KEY", "").strip())

    @property
    def mode(self) -> str:
        return "AUTHENTICATED" if self.authenticated else "PREVIEW"

    def _throttle(self) -> None:
        wait = self.min_interval_s - (time.monotonic() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        self._last_call = time.monotonic()

    def _call(self, params: dict) -> pd.DataFrame:
        self.last_diagnostics = {"parameters": _safe_parameters(params),
                                 "access_mode": self.mode}
        path = self._cache_path(params)
        if self.use_cache and path.exists():
            frame = pd.read_json(path, orient="records", dtype=False)
            self.last_diagnostics.update({"response": "CACHE", "row_count": len(frame)})
            return frame

        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                self._throttle()
                df = self._fetch(**params)
                if df is None:
                    self.last_diagnostics.update({"response": "UNCONFIRMED_EMPTY",
                                                  "row_count": 0,
                                                  "provider_message": "Client returned None"})
                    if self.strict_errors:
                        raise TypeError("Comtrade client returned no response object")
                    return pd.DataFrame()
                if not isinstance(df, pd.DataFrame):
                    raise TypeError("Comtrade client returned an unexpected response type")
                attrs = df.attrs
                self.last_diagnostics.update(_frame_diagnostics(attrs))
                self.last_diagnostics.update({"response": "HTTP_RESPONSE", "row_count": len(df)})
                if self.use_cache and not df.empty:
                    self.cache_dir.mkdir(parents=True, exist_ok=True)
                    df.to_json(path, orient="records")
                return df
            except Exception as exc:  # noqa: BLE001 -- API clients expose varying error types.
                last_error = exc
                self.last_diagnostics.update(_exception_diagnostics(exc))
                time.sleep(min(2 ** attempt, 10))
        raise RuntimeError(f"Comtrade request failed after {self.max_retries} attempts: "
                           f"{self.last_diagnostics.get('error_type', 'provider error')}") from last_error

    # -- public API --------------------------------------------------------

    def fetch_flows(
        self,
        reporter_code: str,
        flow_code: str,
        years: Iterable[int],
        hs_codes: Iterable[str],
        partner_code: str | None = None,
    ) -> pd.DataFrame:
        """Annual HS trade flows. flow_code: 'M' imports, 'X' exports."""
        years_list = [int(year) for year in years]
        params = dict(
            typeCode="C",
            freqCode="A",
            clCode=HS_CLASSIFICATION,
            period=",".join(str(year) for year in years_list),
            reporterCode=str(reporter_code),
            cmdCode=",".join(hs_codes),
            flowCode=flow_code,
            partnerCode=partner_code,
            partner2Code=None,
            customsCode=None,
            motCode=None,
            maxRecords=500,
            format_output="JSON",
            aggregateBy=None,
            breakdownMode="classic",
            countOnly=None,
            includeDesc=True,
        )
        if not self.authenticated and len(years_list) > 1:
            # Public preview accepts one annual period per request.
            frames = []
            request_diagnostics = []
            for year in years_list:
                annual_params = {**params, "period": str(year)}
                frames.append(self._call(annual_params))
                request_diagnostics.append(dict(self.last_diagnostics))
            self.last_diagnostics["requests"] = request_diagnostics
            if all(item.get("http_status") == 200 for item in request_diagnostics):
                self.last_diagnostics["http_status"] = 200
            else:
                self.last_diagnostics.pop("http_status", None)
            total_count: int | float = 0
            has_total_count = True
            for item in request_diagnostics:
                count = item.get("total_count")
                if not isinstance(count, (int, float)):
                    has_total_count = False
                    break
                total_count += count
            if has_total_count:
                self.last_diagnostics["total_count"] = total_count
            else:
                self.last_diagnostics.pop("total_count", None)
            return normalize(pd.concat(frames, ignore_index=True))
        return normalize(self._call(params))


_SAFE_PARAMS = ("typeCode", "freqCode", "clCode", "period", "reporterCode",
                "cmdCode", "flowCode", "partnerCode", "maxRecords", "format_output")


def _safe_parameters(params: dict) -> dict[str, object]:
    return {key: params[key] for key in _SAFE_PARAMS if key in params}


def _frame_diagnostics(attrs: dict) -> dict[str, object]:
    # Provider wrappers sometimes attach response headers or count metadata to attrs.
    safe_keys = {"http_status", "status_code", "total_count", "totalRecords",
                 "count", "pages", "page", "has_more", "pagination", "provider_error"}
    result = {key: _safe_payload(value)
              for key, value in attrs.items() if key in safe_keys
              and isinstance(value, (str, int, float, bool, dict, list, type(None)))}
    if "total_count" not in result:
        for alias in ("totalRecords", "count"):
            if alias in result:
                result["total_count"] = result[alias]
                break
    return result


def _safe_message(value: object) -> str:
    message = str(value)
    message = re.sub(r"(?i)(api[_ -]?key|subscription[_ -]?key|token|authorization)\s*[:=]\s*[^,;\s]+",
                     r"\1=[REDACTED]", message)
    message = re.sub(r"(?i)(authorization\s*[:=]\s*)(?:bearer\s+)?[^,;\r\n]+",
                     r"\1[REDACTED]", message)
    return message[:1000]


def _safe_payload(value: object) -> object:
    if isinstance(value, dict):
        return {str(key): ("[REDACTED]" if re.search(
            r"(?i)(api[_ -]?key|token|secret|password|subscription|authorization)", str(key)
        ) else _safe_payload(item)) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe_payload(item) for item in value]
    if isinstance(value, str):
        return _safe_message(value)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return _safe_message(value)


def _exception_diagnostics(exc: Exception) -> dict[str, object]:
    result: dict[str, object] = {"response": "ERROR", "error_type": type(exc).__name__,
                                 "provider_message": _safe_message(exc)}
    status = getattr(exc, "code", getattr(exc, "status_code", None))
    if isinstance(status, int):
        result["http_status"] = status
    payload = getattr(exc, "payload", None)
    if payload is None and hasattr(exc, "read"):
        try:
            body = exc.read()
            if body:
                decoded = body.decode("utf-8", errors="replace") if isinstance(body, bytes) else str(body)
                try:
                    payload = json.loads(decoded)
                except (json.JSONDecodeError, TypeError):
                    payload = decoded[:1000]
        except Exception:  # noqa: BLE001 -- diagnostics must not mask provider error
            payload = None
    if payload is not None:
        result["provider_error"] = _safe_payload(payload)
    return result


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Keep known columns, coerce numerics, drop empty rows. Pure function (unit-tested)."""
    if df is None or df.empty:
        return pd.DataFrame(columns=KEEP_COLUMNS)
    cols = [c for c in KEEP_COLUMNS if c in df.columns]
    out = df[cols].copy()
    for c in ("qty", "netWgt", "primaryValue"):
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce")
    for c in ("reporterCode", "partnerCode", "cmdCode"):
        if c in out.columns:
            out[c] = out[c].astype(str)
    if "refYear" not in out.columns and "period" in out.columns:
        out["refYear"] = pd.to_numeric(out["period"].astype(str).str[:4], errors="coerce")
    if "primaryValue" in out.columns:
        out = out.dropna(subset=["primaryValue"])
    return out.reset_index(drop=True)
