# Tech Kararları

Bu dosya, `findyourbuddy-backend` geliştirilirken alınan teknik kararları ve
uyulması gereken standartları belgeler. Yeni bir özellik eklerken burayla
çelişen bir şey yapıyorsanız ya kararı burada güncelleyin ya da mevcut
standarda uyun.

> Dört repoyu kapsayan mimari genel bakış, veri akışı ve güncel algoritma
> formülleri (eşleşme, trust score, swipe kotası, datetime sözleşmesi) için:
> **[mimari.md](mimari.md)**.

## Stack

- **Framework:** FastAPI
- **ORM:** SQLAlchemy 2.0 (`Mapped[...]` / `mapped_column` stili, `DeclarativeBase`)
- **Veritabanı:** PostgreSQL (Supabase üzerinde barındırılıyor)
- **Migration:** Alembic, `alembic/env.py` içinde `sqlalchemy.url` doğrudan
  `app.config.get_settings()`'ten okunuyor — `alembic.ini`'ye URL yazılmıyor
- **Bağımlılık yönetimi:** uv, `pyproject.toml` + `uv.lock`, sürümler
  `uv.lock` üzerinden sabitleniyor
- **Auth:** JWT (`python-jose`) + `passlib[bcrypt]` şifre hashleme
- **Test:** `pytest` + `httpx`/`TestClient`, kapsam ölçümü için `pytest-cov`

## Veritabanı bağlantısı

- Supabase'e **connection pooler** üzerinden bağlanılıyor
  (`aws-0-<region>.pooler.supabase.com:6543`), **direct connection**
  (`db.<ref>.supabase.co:5432`) kullanılmıyor. Sebep: direct connection
  host'u sadece IPv6 (AAAA) kaydına sahip, IPv4-only ağlardan
  `getaddrinfo` hatasıyla bağlanılamıyor.
- Şifredeki özel karakterler (`?` gibi) connection string'de URL-encode
  edilmeli (`%3F`), aksi halde URI yanlış parse edilir.
- `alembic/env.py`'de `set_main_option` çağrısına giden URL'deki `%`
  karakterleri `%%` ile escape edilmeli — configparser interpolation
  syntax'ıyla çakışıyor.
- Yerel geliştirme için `docker-compose.yml` ile lokal Postgres
  ayağa kaldırılabilir (`.env.example` bu değerlerle uyumlu).

## Konfigürasyon

- Tüm ayarlar `app/config.py`'deki `Settings` (Pydantic Settings) üzerinden,
  `.env`'den okunuyor. Kod içinde hardcoded değer yok; sabitler ya config
  alanı ya da modül seviyesinde adlandırılmış bir sabit olarak tanımlanıyor.
- Yeni bir ayar eklerken hem `app/config.py`'ye hem `.env.example`'a
  ekleyin.

## Mimari / katmanlama

```
app/
  core/       -> altyapısal, domain'e özgü olmayan yardımcılar (security, deps, notifications, logging)
  models/     -> SQLAlchemy modelleri
  schemas/    -> Pydantic request/response şemaları
  services/   -> iş mantığı, domain exception'ları (routerlardan bağımsız, test edilebilir)
  routers/    -> HTTP katmanı; sadece servis çağırma + exception -> HTTPException çevirisi
```

- Servisler düz fonksiyonlar olarak yazılıyor (flat functions), gereksiz
  sınıf hiyerarşisi yok.
- Domain hataları için özel `Exception` alt sınıfları kullanılıyor
  (ör. `DuplicateSwipeError`, `NotMatchParticipantError`); router bunları
  `except` ile yakalayıp uygun HTTP status koduna çeviriyor.
- Sabit seçenek kümeleri (yön, sebep, durum gibi) için Python `Enum`
  kullanılıyor, magic string yok (`SwipeDirection`, `ReportReason`,
  `ReportStatus`).

## Değiştirilebilir altyapı (Protocol pattern)

Somut sağlayıcıya bağımlı olmaması gereken altyapı parçaları (medya
depolama, bildirim gönderimi) `typing.Protocol` ile arayüz olarak
tanımlanıyor, `lru_cache`'li bir factory fonksiyonuyla enjekte ediliyor:

- `app/services/media_service.py` — `MediaStorage` Protocol +
  `LocalMediaStorage` (şu an disk'e yazıyor, ileride S3/R2'ye geçilebilir)
- `app/core/notifications.py` — `NotificationSender` Protocol +
  `LoggingNotificationSender` (şu an sadece loglıyor, ileride FCM
  entegre edilebilir)

Yeni bir sağlayıcıya geçerken sadece bu dosyalardaki concrete class ve
factory fonksiyonu değişir, iş mantığı (`notification_service.py`,
`user_service.py` vb.) dokunulmadan kalır.

## Route tanımlama

- Route path'leri her zaman açık yazılır (`@router.get("/")`), boş string
  (`@router.get("")`) kullanılmaz — okunurluğu bozuyor, "boş bırakılmış"
  gibi görünüyor.

## Test stratejisi

- Testler gerçek Supabase DB'sine dokunmuyor; `tests/conftest.py`'deki
  `db_session` fixture'ı her test için izole bir SQLite in-memory DB
  kuruyor (`StaticPool` ile tek bağlantı üzerinden).
- `client` fixture'ı FastAPI'nin `get_db` ve `get_notification_sender`
  dependency'lerini bu izole DB ve `FakeNotificationSender` ile override
  ediyor — böylece router testleri de gerçek altyapıya dokunmadan
  çalışıyor.
- Her yeni servis fonksiyonu için hem servis seviyesinde (unit) hem de
  ilgili router için entegrasyon testi yazılıyor.
- `pytest --cov=app --cov-report=term-missing` ile kapsam kontrol
  edilebilir; hedef ~%95+ (framework plumbing — `if __name__`, gerçek
  `get_db` gibi — hariç).

## Loglama

- `app/core/logging.py`'deki `configure_logging()` uygulama başlarken
  çağrılıyor, seviye `LOG_LEVEL` config'inden okunuyor.
- `print()` kullanılmıyor, `logging.getLogger(__name__)` kullanılıyor.
- Her satır loglanmıyor; kritik iş olayları (kullanıcı kaydı, eşleşme
  oluşması gibi) INFO seviyesinde loglanıyor.

## CORS

- İzin verilen origin'ler `CORS_ALLOWED_ORIGINS` config değerinden
  (virgülle ayrılmış string) okunuyor, kod içinde hardcode edilmiyor.

## Rate limiting

- Swipe günlük limitinin dışında, genel API seviyesinde de istek sınırı
  var: `app/core/rate_limit.py`'deki `slowapi` tabanlı `Limiter`, IP
  bazlı (`get_remote_address`) çalışıyor.
- `slowapi` üçüncü parti kütüphane olarak eklendi — IP/kullanıcı bazlı
  pencereli sayaç mantığını sıfırdan yazıp test etmek yerine olgun, test
  edilmiş bir kütüphane kullanmak daha güvenli.
- Varsayılan limit tüm route'lara otomatik uygulanıyor
  (`RATE_LIMIT_DEFAULT_PER_MINUTE`, config'te `default_limits` ile).
  `/auth/register` ve `/auth/login` brute-force'a karşı daha sıkı bir
  limitle (`RATE_LIMIT_AUTH_PER_MINUTE`) `@limiter.limit(...)` ile
  override ediliyor.
- Limit aşıldığında `429 Too Many Requests` dönüyor.
- Testlerde `tests/conftest.py`'deki `_reset_rate_limiter` (autouse)
  fixture'ı her testten önce sayaçları sıfırlıyor — aksi halde tüm test
  oturumu boyunca aynı IP anahtarı üzerinden sayaçlar birikip ilgisiz
  testleri kırardı. Limit değeri, testte `RATE_LIMIT_AUTH_PER_MINUTE`
  env değişkeni + `get_settings.cache_clear()` ile geçici olarak
  düşürülüp doğrulanabiliyor (`tests/test_rate_limit.py`).

## Blok sonrası geriye dönük filtreleme

- Karar: bloklu taraflar arası mesaj geçmişine erişim **tamamen
  kesiliyor** (salt-okunur değil).
- `matching_service.list_matches_for_user`, `safety_service.blocked_user_ids`
  ile taraflar arasında blok varsa eşleşmeyi listeden çıkarıyor (blok
  kaydı silinmiyor, sadece görünürlük kesiliyor — rapor/moderasyon
  geçmişi bozulmuyor).
- `message_service._get_match_for_participant`, iki taraf arasında blok
  varsa `BlockedParticipantError` fırlatıyor; bu hem mesaj gönderme hem
  de mesaj listeleme için geçerli. Router (`app/routers/messages.py`)
  bunu `403`'e çeviriyor.

## Mesaj "okundu" işaretleme

- `PATCH /matches/{match_id}/messages/read` — eşleşmedeki, mevcut
  kullanıcının **almış olduğu** tüm okunmamış mesajları toplu olarak
  `is_read = True` yapar (tekil mesaj bazlı değil). Etkilenen mesaj
  sayısını `{"count": int}` olarak döner.
- `message_service.mark_messages_as_read`, `_get_match_for_participant`
  üzerinden aynı `MatchNotFoundError` / `NotMatchParticipantError` /
  `BlockedParticipantError` kontrollerini kullanır.

## Moderasyon akışı (rapor durumu güncelleme)

- Moderatör rolü basit bir alanla tanımlandı: `User.is_staff: bool`
  (`app/core/deps.py::get_current_staff_user` dependency'si bunu
  zorunlu kılıyor). Ayrı bir rol/izin tablosu yok — MVP kapsamında
  yeterli, ihtiyaç artarsa genişletilir. `is_staff`'ı `True` yapan bir
  API endpoint'i yok (kasıtlı — bu alan şimdilik DB üzerinden elle
  yönetiliyor).
- `PATCH /reports/{report_id}` (sadece staff) — `safety_service.
  update_report_status` ile raporun `status` alanını günceller.
  Rapor yoksa `ReportNotFoundError` → `404`. Staff olmayan kullanıcı
  için `403`.

## Unblock

- `DELETE /users/{user_id}/block` — bloğu kaldırır, `204 No Content`
  döner. Blok kaydı yoksa `safety_service.unblock_user` `BlockNotFoundError`
  fırlatır, router bunu `404`'e çevirir.

## Etkinlik ingestion (scraper entegrasyonu)

- Ayrı bir `findyourbuddy-scraper` reposu, etkinlikleri **REST API
  üzerinden** gönderiyor — DB'ye doğrudan yazmıyor.
- `Event.creator_id` **nullable** yapıldı: scraper kaynaklı etkinliklerin
  gerçek bir sahibi yok, yapay bir "system user" icat etmek yerine bu
  daha dürüst bir model. Manuel oluşturulan etkinliklerde (`POST
  /events/`, JWT auth) `creator_id` her zaman dolu.
- `Event.source` / `Event.external_id` **nullable** — manuel oluşturulan
  etkinliklerde bu alanlar boş kalır; `(source, external_id)` unique
  constraint Postgres'te NULL/NULL çiftlerini birbirinden ayrı saydığı
  için manuel etkinlikler bu kısıtla çakışmıyor.
- `source` alanı kasıtlı olarak sabit bir enum/Literal ile
  sınırlanmadı: yeni bir scraper kaynağı eklemek backend'de kod/migration
  değişikliği gerektirmemeli (categories'in aksine, source'un kapalı bir
  kümesi yok).
- **Auth:** kullanıcı JWT'sinden tamamen ayrı, basit bir servis-to-servis
  anahtarı. `app/core/deps.py::require_scraper_api_key`,
  `X-Scraper-Api-Key` header'ını `SCRAPER_API_KEY` (config, zorunlu) ile
  karşılaştırır. `POST /internal/events/ingest` sadece bu dependency ile
  korunuyor, `get_current_user` ile karışmıyor.
- **İzin verilen kategoriler** config-driven:
  `ALLOWED_EVENT_CATEGORIES` — frontend'deki `src/constants/categories.ts`
  ile birebir aynı liste (`running, coffee, concert, climbing, hiking,
  cycling, yoga, boardgames, football, party, other`). Bu liste sadece
  ingestion'da zorunlu; manuel `POST /events/` kategori kısıtına tabi
  değil (mevcut davranış korundu, testler `category="sports"` gibi
  keyfi değerler kullanıyor).
- `event_ingestion_service.ingest_events`, `(source, external_id)`
  eşleşen kayıt varsa günceller (upsert), yoksa oluşturur. Geçersiz
  kategorili bir kayıt sadece `skipped` sayılır ve `errors`'a eklenir —
  tek bir hatalı kayıt batch'in geri kalanını düşürmez.

## Dağıtım

- `Dockerfile`: `python:3.13-slim`, sadece `app/`, `alembic/`,
  `alembic.ini` kopyalanıyor (`.env`, `venv`, `.git` image'a hiç
  girmiyor). `.dockerignore` da aynı sebeple mevcut.
- Migration'lar image build sürecinde değil, deploy sırasında ayrıca
  `alembic upgrade head` ile çalıştırılmalı (Dockerfile'a otomatik
  migration adımı eklenmedi).
