"""PoC 2 - Mirror Trade Statistics Engine (Algeria, HS Chapter 87).

Reconstructs Algeria's vehicle imports two ways:
  * DIRECT: Algeria as reporter (flow = imports)           -> declared by Algeria
  * MIRROR: partner countries as reporters (flow = exports) -> declared by exporters, partner = Algeria
and compares them year by year.

Run:   python -m src.poc.mirror_trade
Env:   COMTRADE_API_KEY (optional; without it the public preview endpoint is used, max 500 rows/call)

Interpretation notes (do not skip):
  * Imports are usually valued CIF and exports FOB, so mirror values are expected to be a bit
    LOWER than direct values for the same flow (roughly 5-15%); a large gap means missing
    reporters, reporting lag or re-exports, not necessarily error.
  * Mirror coverage is limited to the reporters listed below. It is a lower bound of what the
    world exported to Algeria, not the full picture.
"""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path
from typing import Iterable

import pandas as pd

from src.infrastructure.adapters.comtrade_adapter import ALGERIA_CODE, ComtradeAdapter

DEFAULT_HS = ("8703", "8704")  # 8703 passenger cars, 8704 goods vehicles
# Comtrade reporter codes. "97" is the European Union aggregate (do not add EU member
# states alongside it: that would double count).
DEFAULT_MIRROR_REPORTERS = {
    "97": "European Union",
    "156": "China",
    "792": "Turkiye",
    "392": "Japan",
    "410": "Republic of Korea",
}
OUTPUT_DIR = Path(__file__).resolve().parents[2] / "data" / "output"


def build_comparison(direct: pd.DataFrame, mirror: pd.DataFrame) -> pd.DataFrame:
    """Per year x HS code: direct vs mirror value (USD). Pure function (unit-tested)."""

    def agg(df: pd.DataFrame, name: str) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame(columns=["refYear", "cmdCode", name])
        # Exclude any "World" partner aggregate rows (partnerCode 0) to avoid double counting
        d = df[df["partnerCode"].astype(str) != "0"] if "partnerCode" in df.columns else df
        return (
            d.groupby(["refYear", "cmdCode"], as_index=False)["primaryValue"].sum()
            .rename(columns={"primaryValue": name})
        )

    merged = agg(direct, "direct_import_usd").merge(
        agg(mirror, "mirror_export_usd"), on=["refYear", "cmdCode"], how="outer"
    )
    merged = merged.sort_values(["cmdCode", "refYear"]).reset_index(drop=True)
    merged["gap_usd"] = merged["direct_import_usd"] - merged["mirror_export_usd"]
    merged["mirror_to_direct_ratio"] = (
        merged["mirror_export_usd"] / merged["direct_import_usd"]
    ).round(3)
    merged["best_available_usd"] = merged[["direct_import_usd", "mirror_export_usd"]].max(axis=1)
    merged["source_note"] = merged.apply(_source_note, axis=1)
    return merged


def _source_note(row: pd.Series) -> str:
    has_d = pd.notna(row["direct_import_usd"]) and row["direct_import_usd"] > 0
    has_m = pd.notna(row["mirror_export_usd"]) and row["mirror_export_usd"] > 0
    if has_d and has_m:
        return "both"
    if has_m:
        return "MIRROR ONLY (Algeria direct data missing/lagging)"
    if has_d:
        return "direct only (no mirror coverage)"
    return "no data"


def top_partners(direct: pd.DataFrame, year: int, n: int = 10) -> pd.DataFrame:
    if direct.empty:
        return direct
    d = direct[(direct["refYear"] == year) & (direct["partnerCode"].astype(str) != "0")]
    return (
        d.groupby(["partnerCode", "partnerDesc"], as_index=False)["primaryValue"].sum()
        .sort_values("primaryValue", ascending=False).head(n)
    )


def run(
    start_year: int,
    end_year: int,
    hs_codes: Iterable[str] = DEFAULT_HS,
    reporters: dict[str, str] = DEFAULT_MIRROR_REPORTERS,
    adapter: ComtradeAdapter | None = None,
) -> pd.DataFrame:
    adapter = adapter or ComtradeAdapter()
    years = list(range(start_year, end_year + 1))
    hs = list(hs_codes)

    print(f"[1/2] Direct: Algeria imports, HS {hs}, {years[0]}-{years[-1]}")
    direct = adapter.fetch_flows(ALGERIA_CODE, "M", years, hs)

    if direct.empty:
        print("      WARNING: no direct data returned (Algeria reporting lag, network error or bad key)")

    print("[2/2] Mirror: partner exports to Algeria")
    frames = []
    for code, label in reporters.items():
        print(f"      - {label} ({code})")
        frame = adapter.fetch_flows(code, "X", years, hs, partner_code=ALGERIA_CODE)
        if frame.empty:
            print(f"        WARNING: no data for {label}")
        frames.append(frame)
    mirror = pd.concat([f for f in frames if not f.empty], ignore_index=True) if any(
        not f.empty for f in frames
    ) else pd.DataFrame()

    if direct.empty and mirror.empty:
        # comtradeapicall swallows network/auth errors and returns nothing: never write an
        # empty file that looks like a successful run.
        raise RuntimeError(
            "No data returned from UN Comtrade for any query. Check internet access, "
            "COMTRADE_API_KEY and the requested years. Nothing was written."
        )

    comparison = build_comparison(direct, mirror)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_csv = OUTPUT_DIR / "algeria_hs87_mirror_trade.csv"
    comparison.to_csv(out_csv, index=False)
    print(f"\nSaved: {out_csv}")
    return comparison


def main() -> None:
    last_full_year = dt.date.today().year - 1
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--end-year", type=int, default=last_full_year)
    p.add_argument("--start-year", type=int, default=None, help="default: end-year minus 4 (5 years)")
    p.add_argument("--hs", nargs="+", default=list(DEFAULT_HS))
    args = p.parse_args()
    start = args.start_year if args.start_year is not None else args.end_year - 4
    result = run(start, args.end_year, args.hs)
    with pd.option_context("display.width", 200, "display.float_format", "{:,.0f}".format):
        print(result.to_string(index=False) if not result.empty else "No data returned.")


if __name__ == "__main__":
    main()
