"""MIE source registry. Pending items remain visible and are not treated as enabled."""

from src.data.mie.models import SourceMetadata

WORLD_BANK_SOURCES = {
    "NY.GDP.MKTP.CD": SourceMetadata(
        "world_bank.gdp_current_usd", "World Bank", "GDP (current US$)", "current US$",
        "Algeria (DZA)", "annual", {"country": "DZA"},
        ("Provider revisions may change historical observations.",),
        "Successful retrieval does not prove completeness.",
    ),
    "NV.IND.MANF.ZS": SourceMetadata(
        "world_bank.manufacturing_value_added_pct_gdp", "World Bank",
        "Manufacturing value added (% of GDP)", "% of GDP", "Algeria (DZA)",
        "annual", {"country": "DZA"},
        ("Provider revisions may change historical observations.",),
        "Null observations remain missing; no imputation.",
    ),
    "TM.TAX.MRCH.WM.AR.ZS": SourceMetadata(
        "world_bank.weighted_mean_tariff_pending_validation", "World Bank",
        "Tariff rate, applied, weighted mean", "%", "Algeria (DZA)",
        "annual", {"country": "DZA"},
        ("Not product-specific; geography, definition and scope require validation.",),
        "PENDING_VALIDATION; excluded from conclusions until validated.",
        status="PENDING_VALIDATION",
    ),
}

COMTRADE_DIRECT = SourceMetadata(
    "comtrade.algeria_direct_imports", "UN Comtrade",
    "Algeria-reported imports", "reported primary value (USD)", "Algeria (reporter 12)",
    "annual", {"flow": "M", "reporter": "12", "partner": "0 (World)",
                "commodities": ["8703", "8704"]},
    ("Preview mode may cap results at 500 rows.", "Imports may use CIF valuation."),
    "Direct import declarations only; empty response is not proof of zero trade.",
)

COMTRADE_MIRROR = SourceMetadata(
    "comtrade.selected_reporter_mirror_exports", "UN Comtrade",
    "Selected reporters' exports with Algeria as partner", "reported primary value (USD)",
    "Selected reporting partners to Algeria", "annual",
    {"flow": "X", "partner": "12", "reporters": ["97", "156", "792", "392", "410"],
     "commodities": ["8703", "8704"]},
    ("Coverage is limited to configured reporters.", "Exports commonly use FOB valuation."),
    "Mirror evidence kept separate from Algeria-reported imports; never substituted or summed.",
)

SOURCES = {item.source_id: item for item in (
    *WORLD_BANK_SOURCES.values(), COMTRADE_DIRECT, COMTRADE_MIRROR,
)}
