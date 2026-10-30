# ACCESS ALGERIA - one-shot installer for Windows (PowerShell)
# Run from the repository root:  powershell -ExecutionPolicy Bypass -File .\install_windows.ps1
# Requires Python 3.10+ (https://www.python.org/downloads/) and Git (needed for the git+ packages).

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

function Run-Checked($exe, [string[]]$arguments) {
    & $exe @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed (exit $LASTEXITCODE): $exe $($arguments -join ' ')"
    }
}

function Make-Venv($name, $reqFile) {
    Write-Host "`n=== $name ($reqFile) ===" -ForegroundColor Cyan
    $venvPath = Join-Path $root $name
    $py = Join-Path $venvPath "Scripts\python.exe"
    if (-not (Test-Path $py)) { Run-Checked "py" @("-m", "venv", $venvPath) }
    Run-Checked $py @("-m", "pip", "install", "--upgrade", "pip")
    Run-Checked $py @("-m", "pip", "install", "-r", (Join-Path $root $reqFile))
    return $py
}

# 1) Core system: Phases 1-4
$py = Make-Venv ".venv" "requirements.txt"
Write-Host "`n--- crawl4ai browser setup ---" -ForegroundColor Cyan
Run-Checked $py @("-c", "from crawl4ai.install import post_install; post_install()")
Run-Checked $py @("-c", "import wbgapi, comtradeapicall, dlt, instructor, crawl4ai, langgraph, ragas, lightrag; print('core imports OK')")

# 2) Mirror trade (comtrade-downloader) - separate env because it pins pandas<3
Make-Venv ".venv-comtrade" "requirements-comtrade-mirror.txt" | Out-Null

# 3) GPL-3.0 document processing (marker + surya) - separate env, large download (PyTorch)
$answer = Read-Host "`nInstall marker + surya now? (multi-GB, GPL-3.0 isolated env) [y/N]"
if ($answer -match '^[yY]') { Make-Venv ".venv-marker" "requirements-gpl-isolated.txt" | Out-Null }

Write-Host "`nDone. Activate the core env with:  .\.venv\Scripts\Activate.ps1" -ForegroundColor Green
