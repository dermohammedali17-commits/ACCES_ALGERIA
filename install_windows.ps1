# ACCESS ALGERIA - one-shot installer for Windows (PowerShell)
# Run from the repository root:  powershell -ExecutionPolicy Bypass -File .\install_windows.ps1
# Requires Python 3.10+ (https://www.python.org/downloads/) and Git (needed for the git+ packages).

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

function Run-Checked($exe, [string[]]$arguments) {
    & $exe @arguments | Out-Host
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
    # Install package by package so one failure does not hide the others
    $failed = @()
    $lines = Get-Content (Join-Path $root $reqFile) | Where-Object { $_.Trim() -ne "" -and -not $_.Trim().StartsWith("#") }
    foreach ($line in $lines) {
        Write-Host "--> pip install $line" -ForegroundColor Yellow
        & $py -m pip install $line | Out-Host
        if ($LASTEXITCODE -ne 0) { $failed += $line }
    }
    if ($failed.Count -gt 0) {
        Write-Host "`nFAILED in ${name}:" -ForegroundColor Red
        $failed | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
    } else {
        Write-Host "All packages installed in $name" -ForegroundColor Green
    }
    return $py
}

Write-Host "Python:" -NoNewline; py --version
Write-Host "Git:" -NoNewline; git --version

# 1) Core system: Phases 1-4
$py = Make-Venv ".venv" "requirements.txt"
Write-Host "`n--- crawl4ai browser setup ---" -ForegroundColor Cyan
& $py -c "from crawl4ai.install import post_install; post_install()"
& $py -c "import wbgapi, comtradeapicall, dlt, instructor, crawl4ai, langgraph, ragas, lightrag; print('core imports OK')"

# 2) Mirror trade (comtrade-downloader) - separate env because it pins pandas<3
Make-Venv ".venv-comtrade" "requirements-comtrade-mirror.txt" | Out-Null

# 3) GPL-3.0 document processing (marker + surya) - separate env, large download (PyTorch)
$answer = Read-Host "`nInstall marker + surya now? (multi-GB, GPL-3.0 isolated env) [y/N]"
if ($answer -match '^[yY]') { Make-Venv ".venv-marker" "requirements-gpl-isolated.txt" | Out-Null }

Write-Host "`nDone. Activate the core env with:  .\.venv\Scripts\Activate.ps1" -ForegroundColor Green
