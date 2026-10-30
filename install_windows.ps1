# ACCESS ALGERIA - one-shot installer for Windows (PowerShell)
# Run from the repository root:  powershell -ExecutionPolicy Bypass -File .\install_windows.ps1
# Requires Python 3.10+ (https://www.python.org/downloads/) and Git.

$ErrorActionPreference = "Stop"

function Make-Venv($name, $reqFile, $extra) {
    Write-Host "`n=== $name ($reqFile) ===" -ForegroundColor Cyan
    if (-not (Test-Path $name)) { py -m venv $name }
    & "$name\Scripts\python.exe" -m pip install --upgrade pip
    & "$name\Scripts\python.exe" -m pip install -r $reqFile
    if ($extra) { & $extra $name }
}

# 1) Core system: Phases 1-4 (wbgapi, comtradeapicall, dlt, dbt, LightRAG, instructor,
#    crawl4ai, langgraph, langgraph-swarm, opyncorporates, ragas)
Make-Venv ".venv" "requirements.txt" {
    param($n)
    & "$n\Scripts\crawl4ai-setup.exe"      # downloads the Playwright browser
    & "$n\Scripts\crawl4ai-doctor.exe"     # sanity check
}

# 2) Mirror trade (comtrade-downloader) - separate env because it pins pandas<3
Make-Venv ".venv-comtrade" "requirements-comtrade-mirror.txt" $null

# 3) GPL-3.0 document processing (marker + surya) - separate env, large download (PyTorch)
$answer = Read-Host "`nInstall marker + surya now? (multi-GB, GPL-3.0 isolated env) [y/N]"
if ($answer -match '^[yY]') { Make-Venv ".venv-marker" "requirements-gpl-isolated.txt" $null }

Write-Host "`nDone. Activate the core env with:  .\.venv\Scripts\Activate.ps1" -ForegroundColor Green
