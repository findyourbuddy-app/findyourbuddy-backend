# FindYourBuddy Backend + Tunnel Script
Write-Host "Starting Backend FastAPI Server..." -ForegroundColor Cyan
Set-Location "c:\Users\Engin Çetintaş\Desktop\Projects\freelance\Mobil-uygulama\findyourbuddy-backend"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd 'c:\Users\Engin Çetintaş\Desktop\Projects\freelance\Mobil-uygulama\findyourbuddy-backend'; .\.venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

Write-Host "Starting Public Tunnel on Port 8000..." -ForegroundColor Yellow
npx --yes localtunnel --port 8000
