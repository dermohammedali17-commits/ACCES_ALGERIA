# Python source

| Path | Purpose |
|---|---|
| `data/trade_pipeline.py` | UN Comtrade and World Bank data clients, normalization, retrieval reports, and duplicate audits. |
| `data/reference/country_reference.py` | Loads and validates the country reference dataset. |
| `document/gazette_parser.py` | Injected service boundary for Gazette PDF layout parsing and structured extraction. |
| `scoring/engine.py` | Compatibility scorers retained for existing callers; not used by new P04 workflows. |
| `scoring/opportunity_scorer_b.py` | Canonical fixed-weight, nine-dimension, evidence-aware Model B scoring engine. |
| `scoring/p04_engine.py` | P04 eligibility gates, score gating, explainable decision package, and quarantine boundary. |
| `scoring/cli.py` | Local JSON intake and decision-package output for one P04 assessment. |
| `infrastructure/adapters/comtrade_adapter.py` | UN Comtrade API wrapper with rate limiting, retry, and local caching. |
| `poc/mirror_trade.py` | Existing mirror-trade proof of concept for Algeria vehicle imports. |

New opportunity-scoring integrations use `p04_engine.py`; it invokes the canonical Model B scorer only after the required evidence-backed gates resolve. `engine.py` stays for compatibility and its results are not comparable with P04 packages. Data and document module tests live in `tests/test_trade_pipeline.py`, `tests/test_world_bank_client.py`, `tests/test_country_reference.py`, and `tests/test_scoring_engine.py`. Adapter and mirror-trade tests remain in `tests/test_mirror_trade.py` and `tests/test_opportunity_scorer_b.py`.
