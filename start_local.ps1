$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$VenvPath = Join-Path $Root ".venv"
if (-not (Test-Path $VenvPath)) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        py -m venv $VenvPath
    } else {
        python -m venv $VenvPath
    }
}

$Python = Join-Path $VenvPath "Scripts\python.exe"
& $Python -m pip install --upgrade pip
& $Python -m pip install -r requirements.txt

if (-not $env:HOST) {
    $env:HOST = "127.0.0.1"
}

if (-not $env:PORT) {
    $env:PORT = "7860"
}

Write-Host "Starting voice-service at http://$($env:HOST):$($env:PORT)"
& $Python -m uvicorn app.main:app --host $env:HOST --port $env:PORT

