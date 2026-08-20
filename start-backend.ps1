# Start FindYourBuddy FastAPI Backend Server with Auto-Port Selection
Write-Host "Starting FindYourBuddy FastAPI Backend..." -ForegroundColor Green
Set-Location -Path $PSScriptRoot
if (Test-Path ".\.venv\Scripts\python.exe") {
    .\.venv\Scripts\python.exe run_server.py
} else {
    python run_server.py
}
