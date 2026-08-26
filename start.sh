#!/usr/bin/env bash
# Linux sunucu — backend başlatır
cd "$(dirname "$0")"

# Redis cache'siz calisirsa /swipes/candidates her seferinde sifirdan
# DB sorgusu + skorlama yapar (esles sayfasi yavaslar). Container'i burada
# otomatik ayaga kaldiriyoruz ki native calistirmada da cache calissin.
if command -v docker >/dev/null 2>&1; then
    docker compose up -d redis >/dev/null
else
    echo "UYARI: Docker bulunamadi, Redis cache devre disi kalacak (eslesme sayfasi yavas olabilir)."
fi

.venv/bin/python run_server.py
