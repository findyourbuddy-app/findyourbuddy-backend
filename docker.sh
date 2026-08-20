#!/usr/bin/env bash
# Tek komutla yönetim: backend + scraper + redis container'larını durdurur,
# en son koddan yeniden build alır, ayağa kaldırır, sonra portu internete açar.
set -e
cd "$(dirname "$0")"

docker compose down
docker compose up --build -d
docker compose ps

echo "Backend'i internete açan tunnel başlatılıyor (Ctrl+C ile durdur)..."
npx --yes localtunnel --port 8000
