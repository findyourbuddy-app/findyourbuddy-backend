# Tech Kararları

Bu dosya, `findyourbuddy-backend` geliştirilirken alınan teknik kararları ve
uyulması gereken standartları belgeler. Yeni bir özellik eklerken burayla
çelişen bir şey yapıyorsanız ya kararı burada güncelleyin ya da mevcut
standarda uyun.

## Stack

- **Framework:** FastAPI
- **ORM:** SQLAlchemy 2.0 (`Mapped[...]` / `mapped_column` stili, `DeclarativeBase`)
- **Veritabanı:** PostgreSQL (Supabase üzerinde barındırılıyor)
- **Migration:** Alembic, `alembic/env.py` içinde `sqlalchemy.url` doğrudan
  `app.config.get_settings()`'ten okunuyor — `alembic.ini`'ye URL yazılmıyor
- **Bağımlılık yönetimi:** pip + `requirements.txt`, tüm paketler pinlenmiş
  sürümle (`==`)
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

## Ertelenen kararlar

- **Rate limiting** (swipe dışında genel API seviyesinde): trafik
  arttıkça değerlendirilecek, şu an eklenmedi.
- **Blok sonrası geriye dönük filtreleme:** bir kullanıcı engellendiğinde
  yeni swipe/eşleşme akışından hemen filtreleniyor, ama blok öncesinde
  zaten oluşmuş eşleşme/mesajlar geriye dönük gizlenmiyor. İstenirse
  ayrıca ele alınmalı.
- **Mesaj "okundu" işaretleme:** `Message.is_read` alanı modelde var ama
  bunu güncelleyen bir endpoint henüz yok.

## Dağıtım

- `Dockerfile`: `python:3.13-slim`, sadece `app/`, `alembic/`,
  `alembic.ini` kopyalanıyor (`.env`, `venv`, `.git` image'a hiç
  girmiyor). `.dockerignore` da aynı sebeple mevcut.
- Migration'lar image build sürecinde değil, deploy sırasında ayrıca
  `alembic upgrade head` ile çalıştırılmalı (Dockerfile'a otomatik
  migration adımı eklenmedi).
