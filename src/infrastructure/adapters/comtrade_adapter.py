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
import time
from pathlib import Path
from typing import Callable, Iterable, Optional

import pandas as pd

ALGERIA_CODE = "12"
HS_CLASSIFICATION = "HS"

# Columns we keep (only those present in the response are used).
KEEP_COLUMNS = [
    "refYear", "period", "reporterCode", "reporterDesc", "partnerCode", "partnerDesc",
    "flowCode", "cmdCode", "cmdDesc", "qtyUnitCode", "qty", "netWgt", "primaryValue",
]

DEFAULT_CACHE_DIR = Path(__file__).resolve().parents[3] / "data" / "cache" / "comtrade"

FetchFn = Callable[..., Optional[pd.DataFrame]]


def _default_fetch(**params) -> Optional[pd.DataFrame]:
    """Call the real API. Imported lazily so tests and offline use do not need the network."""
    import comtradeapicall

    key = os.environ.get("COMTRADE_API_KEY", "").strip()
    if key:
        return comtradeapicall.getFinalData(key, **params)
    return comtradeapicall.previewFinalData(**params)


class ComtradeAdapter:
    def __init__(
        self,
        fetch_fn: Optional[FetchFn] = None,
        cache_dir: Path | str = DEFAULT_CACHE_DIR,
        min_interval_s: float = 1.2,
        max_retries: int = 3,
        use_cache: bool = True,
    ) -> None:
        self._fetch = fetch_fn or _default_fetch
        self.cache_dir = Path(cache_dir)
        self.min_interval_s = min_interval_s
        self.max_retries = max_retries
        self.use_cache = use_cache
        self._last_call = 0.0

    # -- internals ---------------------------------------------------------

    def _cache_path(self, params: dict) -> Path:
        digest = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()[:20]
        return self.cache_dir / f"{digest}.json"

    def _throttle(self) -> None:
        wait = self.min_interval_s - (time.monotonic() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        self._last_call = time.monotonic()

    def _call(self, params: dict) -> pd.DataFrame:
        path = self._cache_path(params)
        if self.use_cache and path.exists():
            return pd.read_json(path, orient="records", dtype=False)

        last_error: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                self._throttle()
                df = self._fetch(**params)
                if df is None:
                    df = pd.DataFrame()
                if self.use_cache and not df.empty:
                    self.cache_dir.mkdir(parents=True, exist_ok=True)
                    df.to_json(path, orient="records")
                return df
            except Exception as exc:  # network / API errors: back off and retry
                last_error = exc
                time.sleep(min(2 ** attempt, 10))
        raise RuntimeError(f"Comtrade request failed after {self.max_retries} attempts: {last_error}")

    # -- public API --------------------------------------------------------

    def fetch_flows(
        self,
        reporter_code: str,
        flow_code: str,
        years: Iterable[int],
        hs_codes: Iterable[str],
        partner_code: Optional[str] = None,
    ) -> pd.DataFrame:
        """Annual HS trade flows. flow_code: 'M' imports, 'X' exports."""
        params = dict(
            typeCode="C",
            freqCode="A",
            clCode=HS_CLASSIFICATION,
            period=",".join(str(y) for y in years),
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
        return normalize(self._call(params))


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
