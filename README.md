# findyourbuddy-backend

Etkinlik bazlı arkadaş eşleştirme platformunun ana REST API'si.
FastAPI · SQLAlchemy 2.0 · Postgres (Supabase) · Alembic · slowapi · APScheduler.

Mimari, veri akışı, eşleşme/trust/kota algoritmaları ve datetime sözleşmesi için:
**[docs/mimari.md](docs/mimari.md)**. Alınan tekil teknik kararlar
`docs/tech-kararlari.md`, yol haritası `docs/yapilacaklar.md`. Deploy sırası,
yedekleme/felaket kurtarma, staff erişim SOP'u ve olay müdahalesi:
**[docs/production-runbook.md](docs/production-runbook.md)**.

Öne çıkanlar:
- **Datetime:** tüm UTC datetime'lar `Z` OLMADAN serialize edilir (naive UTC).
  Backend içinde `app.core.datetime_utils.utcnow()` kullanın.
- **Zamanlanmış işler** (`app/core/scheduler.py`): süresi geçen etkinlik/bookmark
  temizliği, no-show cezaları, trust skoru yeniden hesabı, hesap askıya alma,
  geri bildirim bildirimleri.
- **Scraper entegrasyonu:** `POST /internal/events/ingest` (X-Scraper-Api-Key).

## Kurulum

```bash
git clone <repo-url>
cd findyourbuddy-backend

uv sync

cp .env.example .env   # değerleri kendi ortamınıza göre doldurun
```

## Lokal veritabanı

```bash
docker compose up -d
```

`.env.example` içindeki `DATABASE_URL`, yukarıdaki `docker-compose.yml` servisiyle uyumludur.

## Migration

```bash
uv run alembic upgrade head
```

## Çalıştırma

```bash
uv run uvicorn app.main:app --reload
```

API `http://127.0.0.1:8000` üzerinde çalışır, health check için `GET /health/`.

Alternatif olarak `uv run python run_server.py` boştaki ilk portu seçer
(sırasıyla 8001, 8000, 8080, 8088). Mobil istemcinin dev fallback'i 8001'i
beklediği için lokal geliştirmede bu script tercih edilir.

## Test

```bash
uv run pytest
```
