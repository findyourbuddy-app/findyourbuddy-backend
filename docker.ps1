# Tek komutla yönetim: backend + scraper + redis container'larını durdurur,
# en son koddan yeniden build alır, ayağa kaldırır, sonra portu internete açar.
Set-Location $PSScriptRoot

docker compose down
docker compose up --build -d
docker compose ps

Write-Host "Backend'i internete açan tunnel başlatılıyor (Ctrl+C ile durdur)..." -ForegroundColor Yellow
npx --yes localtunnel --port 8000
