# findyourbuddy-backend

## Kurulum

```bash
git clone <repo-url>
cd findyourbuddy-backend

python -m venv env
env\Scripts\activate   # Windows
# source env/bin/activate   # macOS/Linux

pip install -r requirements.txt

cp .env.example .env   # değerleri kendi ortamınıza göre doldurun
```

## Lokal veritabanı

```bash
docker compose up -d
```

`.env.example` içindeki `DATABASE_URL`, yukarıdaki `docker-compose.yml` servisiyle uyumludur.

## Migration

```bash
alembic upgrade head
```

## Çalıştırma

```bash
uvicorn app.main:app --reload
```

API varsayılan olarak `http://127.0.0.1:8000` üzerinde çalışır, health check için `GET /health`.

## Test

```bash
pytest
```
