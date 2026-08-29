# Windows lokal — backend başlatır
Set-Location $PSScriptRoot

# Redis cache'siz calisirsa /swipes/candidates her seferinde sifirdan
# DB sorgusu + skorlama yapar (esles sayfasi yavaslar). Container'i burada
# otomatik ayaga kaldiriyoruz ki native calistirmada da cache calissin.
if (Get-Command docker -ErrorAction SilentlyContinue) {
    docker compose up -d redis | Out-Null
} else {
    Write-Host "UYARI: Docker bulunamadi, Redis cache devre disi kalacak (eslesme sayfasi yavas olabilir)." -ForegroundColor Yellow
}

.\.venv\Scripts\python run_server.py
