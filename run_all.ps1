# ACCESS ALGERIA - run tests, then the mirror-trade PoC, with ONE command:
#   powershell -ExecutionPolicy Bypass -File .\run_all.ps1
#
# Optional (recommended) before running - UN Comtrade key (free: comtradedeveloper.un.org):
#   $env:COMTRADE_API_KEY = "your-key"
# Without a key the public preview endpoint is used (max 500 rows per request).

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { throw "Run install_windows.ps1 first (.venv not found)." }

Write-Host "`n=== 1/2 Unit tests (Model B + trade adapter) ===" -ForegroundColor Cyan
& $py -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Tests failed - stopping before the data run." }

Write-Host "`n=== 2/2 PoC 2: Algeria HS 8703/8704 mirror trade ===" -ForegroundColor Cyan
if (-not $env:COMTRADE_API_KEY) {
    Write-Host "No COMTRADE_API_KEY set: using the public preview endpoint (500 rows max)." -ForegroundColor Yellow
}
& $py -m src.poc.mirror_trade
if ($LASTEXITCODE -ne 0) { throw "Mirror-trade run failed (see message above)." }

Write-Host "`nOutput: data\output\algeria_hs87_mirror_trade.csv" -ForegroundColor Green
