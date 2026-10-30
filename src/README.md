# src/ - ACCESS ALGERIA code

| Path | Purpose | Blueprint layer |
|---|---|---|
| `scoring/opportunity_scorer_b.py` | Deterministic Model B engine (9 dimensions, HIGH/MEDIUM/LOW confidence). Source of truth: `04_OPPORTUNITY_SCORING/` | Layer 5 |
| `infrastructure/adapters/comtrade_adapter.py` | UN Comtrade wrapper: API key, rate limit, retry, local cache | Layer 1 |
| `poc/mirror_trade.py` | PoC 2: Algeria HS 8703/8704 direct vs mirror imports | Layer 1 |

Run everything: `powershell -ExecutionPolicy Bypass -File .\run_all.ps1`
Tests only: `.\.venv\Scripts\python.exe -m pytest -q`

Rule: LLMs/agents may propose dimension inputs with evidence, but never set a score.
