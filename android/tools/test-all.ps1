#requires -Version 5.1
# Run all checks: core tests, standalone server protocol, real-PhoneIngest
# integration (when a backend venv with fastapi/uvicorn/websockets is
# available), then build the APK.
$ErrorActionPreference = "Continue"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$repo = Split-Path $root -Parent
$env:XIAOQI_BACKEND = Join-Path $repo "backend"

$pyCandidates = @()
if ($env:XIAOQI_PY -and (Test-Path $env:XIAOQI_PY)) {
    $pyCandidates += $env:XIAOQI_PY
}
$pyCandidates += @(
    (Join-Path $repo "backend\.venv\Scripts\python.exe"),
    (Join-Path $repo "backend\.venv\bin\python")
)
$python = $null
foreach ($candidate in $pyCandidates) {
    if (Test-Path $candidate) {
        $python = $candidate
        break
    }
}
if (-not $python) {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { $python = $cmd.Source }
}
if ($python) { $env:XIAOQI_PY = $python }

$hasBackendDeps = $false
if ($python) {
    & $python -c "import fastapi, uvicorn, websockets" 2>$null
    $hasBackendDeps = ($LASTEXITCODE -eq 0)
}

$failures = 0

Write-Host ""
Write-Host "===== 1/4 Core self-tests =====" -ForegroundColor Cyan
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root "tools\test-core.ps1")
if ($LASTEXITCODE -ne 0) { $failures++ }

Write-Host ""
Write-Host "===== 2/4 Standalone dev server =====" -ForegroundColor Cyan
if ($python) {
    & $python -B (Join-Path $root "tools\test-dev-server.py")
    if ($LASTEXITCODE -ne 0) { $failures++ }
} else {
    Write-Warning "Python not found; dev server test skipped."
    $failures++
}

Write-Host ""
Write-Host "===== 3/4 Real PhoneIngest + WebSocket =====" -ForegroundColor Cyan
if ($hasBackendDeps -and (Test-Path (Join-Path $repo "backend\xiaoqi\ingest\phone.py"))) {
    & $python -B (Join-Path $root "tools\test-integration.py")
    if ($LASTEXITCODE -ne 0) { $failures++ }
} else {
    Write-Warning "backend venv with fastapi/uvicorn/websockets not found; integration test skipped."
}

Write-Host ""
Write-Host "===== 4/4 Build APK =====" -ForegroundColor Cyan
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root "tools\build-apk.ps1")
if ($LASTEXITCODE -ne 0) { $failures++ }

Write-Host ""
if ($failures -eq 0) {
    Write-Host "ALL CHECKS PASSED" -ForegroundColor Green
    exit 0
}
Write-Host "$failures check group(s) failed" -ForegroundColor Red
exit 1
