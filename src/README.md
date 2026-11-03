# Python source

| Path | Purpose |
|---|---|
| `data/trade_pipeline.py` | UN Comtrade and World Bank data clients, normalization, retrieval reports, and duplicate audits. |
| `data/reference/country_reference.py` | Loads and validates the country reference dataset. |
| `document/gazette_parser.py` | Injected service boundary for Gazette PDF layout parsing and structured extraction. |
| `scoring/engine.py` | Deterministic nine-dimension scorer with completeness-based confidence. |
| `scoring/opportunity_scorer_b.py` | Existing evidence-aware Model B scorer with named dimensions and priority bands. |
| `infrastructure/adapters/comtrade_adapter.py` | UN Comtrade API wrapper with rate limiting, retry, and local caching. |
| `poc/mirror_trade.py` | Existing mirror-trade proof of concept for Algeria vehicle imports. |

The two scoring modules remain separate implementations while their intended roles are evaluated. Tests for the newer data and document modules live in `tests/test_trade_pipeline.py`, `tests/test_world_bank_client.py`, `tests/test_country_reference.py`, and `tests/test_scoring_engine.py`. The existing adapter and mirror-trade tests remain in `tests/test_mirror_trade.py` and `tests/test_opportunity_scorer_b.py`.
