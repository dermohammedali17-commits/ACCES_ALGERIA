# ACCESS ALGERIA Development Guide

Development commands for the Python code in `src/` and `tests/`. Run them from the repository root in PowerShell.

## Environments

- `.venv` (Python 3.12): project and test environment.
- `.venv-marker`: isolated Marker/Surya environment; do not run project tests here.
- `.venv-comtrade`: isolated mirror-trade analysis environment.

Use the project interpreter explicitly:

```powershell
.\.venv\Scripts\python.exe --version
```

## Checks

Development tools are pinned in `requirements-dev.txt`. They are not installed or changed by this guide.

```powershell
.\.venv\Scripts\python.exe -m pytest -m "not live"
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy
```

Pytest settings, Ruff rules, and the mypy file list are maintained in `pyproject.toml`. Live tests are marked `live`; exclude them from ordinary runs as shown above. Run a live test only when you intentionally select it and accept its network access.

## Network and credentials in tests

`tests/conftest.py` blocks IPv4 and IPv6 TCP `connect` and `connect_ex` calls for tests that are not marked `live`. It also removes `COMTRADE_API_KEY` from each test's environment. Use fakes for ordinary unit tests; never place credentials in code or fixtures.

## Protected modules

Do not change these without an explicit decision by the project owner:

- `src/scoring/engine.py`: Model B weights and scoring logic.
- `src/data/trade_pipeline.py`: trade retrieval behavior and provenance fields.
- `src/data/reference/`: country reference data.

## Repository hygiene

- Do not commit `.venv*`, `.env`, caches, or coverage output.
- Preserve `src/data/trade_pipeline.py.bak`; it is an older draft, not a restore point.
- The website (`access-algeria-website/`) and `.agents/` are separate concerns.
