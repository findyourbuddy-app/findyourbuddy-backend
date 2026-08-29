# FindYourBuddy — Mimari Genel Bakış

Etkinlik bazlı arkadaş/aktivite eşleştirme platformu. Bu doküman dört repoyu,
aralarındaki veri akışını ve kritik iş kurallarını özetler. Repoya özgü kurulum
adımları için ilgili repo `README.md`'sine, alınan tekil teknik kararlar için
[`tech-kararlari.md`](tech-kararlari.md)'ye, yol haritası için
[`yapilacaklar.md`](yapilacaklar.md)'ye bakın.

---

## 1. Bileşenler

| Repo | Teknoloji | Rol |
|---|---|---|
| **findyourbuddy-backend** | FastAPI · SQLAlchemy 2.0 · Postgres (Supabase) · Alembic · slowapi · APScheduler | Ana REST API, iş mantığı, ödeme (iyzico), AI (Novita), medya (S3/R2) |
| **findyourbuddy-frontend** | Expo (React Native + TS, SDK 57) · Firebase (Auth + Firestore) | Mobil istemci (iOS/Android/web) |
| **findyourbuddy-scraping** | Python · httpx · APScheduler · tenacity | Bağımsız servis — dış kaynaklardan (etkinlik.io) etkinlik çekip backend'e besler |
| **findyourbuddy-monitoring** | Prometheus · Grafana · Loki · Promtail | Metrik, log, canlı dashboard, maliyet takibi |

### Veri akışı

```
etkinlik.io API ──> scraping ──POST /internal/events/ingest──> backend ──> Postgres
                                                                  │
mobil istemci ──REST (JWT)──> backend <────────────────────────────┘
     │
     └──Firebase Auth (giriş) + Firestore (realtime sohbet kopyası)
```

- **Postgres = tek doğ­ruluk kaynağı.** Sohbet mesajları Postgres'e yazılır,
  ayrıca best-effort olarak Firestore'a relay edilir (istemci realtime dinlesin
  diye). Firestore düşerse mesaj kaybolmaz.
- Scraping servisi **backend DB'sine dokunmaz**, yalnızca `/internal/*`
  endpoint'lerini (X-Scraper-Api-Key ile) kullanır.

---

## 2. Kimlik doğrulama

- **Giriş:** Firebase Auth (e-posta/şifre, telefon, Google). Backend
  `POST /auth/firebase-login` ile Firebase token'ı doğrulayıp kendi JWT'sini
  (access + refresh) verir.
- Klasik e-posta/şifre kaydı da var (`POST /auth/register`).
- **Refresh token rotasyonu** + `user.token_version` — trust skoru düşüp
  otomatik askıya alınan kullanıcının mevcut JWT'leri anında geçersiz olur.
- **RLS:** Postgres RLS etkin ama bağlanan rol `rolbypassrls=true` olduğundan
  tüm yetkilendirme FastAPI katmanında (`get_current_user`, sahiplik kontrolleri).

---

## 3. Datetime sözleşmesi ⚠️

**Backend, tarih/saatleri `Z`/offset OLMADAN UTC olarak serialize eder.** Postgres
kolonları `TIMESTAMP WITHOUT TIME ZONE`.

- Backend içinde her zaman `app.core.datetime_utils.utcnow()` (naive UTC) kullanılır.
- Frontend `src/utils/date.ts` `parseApiDate()` — tz işareti yoksa string'e `Z`
  ekler (UTC varsayar), sonra cihaz yerel saatine çevirir. **Her `starts_at`
  kullanımı `parseApiDate` ya da `formatEventDate`'ten geçmeli** — ham
  `new Date(...)` naive string'i yerel sanar ve saati kaydırır.
- **Etkinlik oluşturma:** `CreateEventScreen` `startsAt.toISOString()` gönderir
  (gerçek UTC anı). `EventCreate` / `EventIngestPayload` şemalarında validator
  offset'li değeri UTC'ye çevirip tzinfo'yu düşürür.
- **Scraper:** etkinlik.io `start_r001` alanı zaten UTC ISO'dur; `_parse_starts_at`
  yine de aware→UTC / naive→İstanbul(UTC+3) normalizasyonu yapar.

---

## 4. Eşleşme algoritması (`matching_service._calculate_score`)

`try_create_match` — iki kullanıcı da birbirini (aynı `event_id` kapsamında)
LIKE/SUPER_LIKE'ladıysa `Match` oluşur. Öneri sıralaması (`RecommendationService`)
şu ağırlıklı skoru kullanır, `total_weight`'e bölünüp normalize edilir:

| Bileşen | Ağırlık | Kaynak |
|---|---|---|
| Ortak ilgi/hobi | `match_common_interest_weight` (0.60) | interests + hobbies örtüşmesi |
| Mesafe | `match_distance_weight` (0.40) | haversine, `match_max_distance_km` içinde |
| Zodyak sinerjisi | 0.15 | Ateş/Toprak/Hava/Su matrisi (aynı=1.0, uyumlu=0.85, diğer=0.50) |
| Ortak dil | 0.15 | `languages_spoken` kesişimi |
| Aradığı ilişki türü | 0.20 | `looking_for` uyumu |
| Akademik | 0.15 | aynı üniversite / sınıf yakınlığı |
| Dünya görüşü | 0.10 | `political_views` + `beliefs` |

Sonuç **trust boost** ile çarpılır: `clamp(0.8, 1.2, trust_score / 65)` — 65
nötr (doğrulanmış temiz kullanıcı), yüksek trust öneriyi öne çeker.

Spotlight (boost) satın alan ve premium kullanıcılar aday listesinde en üste
sıralanır (`list_swipe_candidates`).

---

## 5. Swipe kotası

| Kullanıcı | Günlük beğeni | Günlük süper beğeni |
|---|---|---|
| Ücretsiz | `daily_swipe_limit` (10) + satın alınan `bonus_swipe_credits` | `daily_super_like_limit` (1) + `extra_super_likes` |
| Premium | sınırsız | `premium_daily_super_like_limit` (5) + `extra_super_likes` |

- Sayım sorgu bazlı: `_swipes_made_today` / `_likes_made_today`, gün başlangıcı
  `daily_quota_reset_hour_utc` (21 UTC = **00:00 Türkiye**). Otomatik yenilenir,
  ayrı bir job gerekmez. `GET /swipes/quota` `resets_at` alanını döner.
- PASS ücretsiz ve sınırsız; yalnız LIKE/SUPER_LIKE sayılır. Süper beğeni bir
  normal beğeni hakkı da tüketir.
- **Aday eleme global:** bir kişiyi bir yerde (genel gezinme / herhangi etkinlik)
  kaydırdıysan hiçbir destede tekrar görünmez. Havuz tükenince deste boş kalır
  (eskiden kaydırılmışları geri döndüren "recycle" kaldırıldı).
- Frontend: kota sunucudan tek doğ­ruluk olarak alınır; swipe'ta optimistik `+1`,
  swipe reddedilirse (`429/409/403/ağ hatası`) bump geri alınır. `reconcileQuota`
  600 ms debounce'lu — hızlı kaydırmada tek refetch.

---

## 6. Trust score (`trust_service.compute_trust_score`)

**0-100 arası, gerçek sinyallerden her seferinde yeniden hesaplanan** bir değer
(çalışan bir toplam DEĞİL — sürüklenmez, sınırlıdır, telafi edilebilir).

| Bileşen | Katkı |
|---|---|
| Taban | +30 |
| Foto (selfie) doğrulama · telefon · e-posta | +25 · +8 · +5 |
| Etkinliğe gitme oranı (RSVP → check-in) | 0..+15 |
| Ev sahibi olarak alınan ortalama puan (≥2 puan) | ±12 |
| Doğrulanmış gerçek buluşmalar | 0..+8 (2/adet) |
| Sebepsiz gelmeme (no-show) | 0..−20 (5/adet) |
| Şikayet (incelenen −10 / bekleyen −3) | 0..−30 |
| Engellenme | 0..−10 (2/adet) |

Ağırlıklar `config.py` `trust_*` ayarlarında. `recompute_trust_score` şu
noktalarda çağrılır: foto doğrulama, check-in, no-show taraması, etkinlik
puanlama, buluşma onayı, şikayet/engelleme, ve her scheduler cleanup turunda.
Trust `< trust_score_suspension_threshold` (15) → 14 gün sonra otomatik askıya.

---

## 7. Etkinlikler

- **Resmi etkinlikler** (`creator_id IS NULL`) — scraper'dan gelir.
- **Kullanıcı etkinlikleri** (`creator_id` dolu) — 1-1 veya grup (`is_group_event`).
  Grup etkinliğinde organizatör onayı → organizatör↔katılımcı `Match` (duyuru
  kanalı). Grup mesajı yalnız organizatör atar, herkese fan-out edilir.
- **Check-in:** GPS (`CHECK_IN_RADIUS_KM` = 1 km) + zaman penceresi (başlangıçtan
  1 sa önce → 8 sa sonra).
- **Süre dolumu:** `event_retention_days` (0.25 = 6 sa) geçmiş VE hiç `Match`
  üretmemiş etkinlikler scheduler tarafından silinir (resmi/kullanıcı/grup ayrımı
  yok). Match'i olan etkinlikler sohbet geçmişi için korunur.
- Bilet **satışı yok** — "Katılım Ücreti / Tahmini Harcama" bilgisi. Bilet alımı
  üçüncü parti (Biletix, Passo) üzerinden.

---

## 8. Scraping servisi

- `EtkinlikIoSource` — etkinlik.io API v2, yalnız fiziksel venue'lu etkinlikler
  (ONLINE atlanır). Koordinat yoksa adres Nominatim ile geocode edilir;
  başarısızsa etkinlik atlanır (küçük şehir sokak adresleri sık başarısız).
- **Artımlı çalışma:** `run_source` önce backend'den `known-ids`'i çeker,
  `fetch_raw_events(known_ids)`'e verir → adapter zaten kayıtlı etkinlikleri
  impression ping / mapping / geocoding'den önce atlar. Restart / saatlik tur
  yalnız yeni etkinlikleri işler.
- AI enrichment (kategori/etiket) opsiyonel: Novita → Gemini → atla. Kredisi
  biterse ingest engellenmez (kategori `map_category`'den gelen kalır).
- `config.json` — kategori eşlemesi + aktif kaynaklar (kod değişmeden).
- ⚠️ `.env` `BACKEND_API_URL` backend'in gerçekten dinlediği portla eşleşmeli
  (`run_server.py` sırayla 8001, 8000, ... dener → genelde **8001**).

---

## 9. Bildirimler

- DB `Notification` satırı + (varsa) Expo push. `push_provider` = `logging`
  ise sadece uygulama içi.
- `notification_type`: `like`, `match`, `message`, `event`, `event_request`,
  `event_response`, `match_feedback`, `verification`, `double_buddy_invite`,
  `double_buddy_accepted`, `double_buddy_rejected`, `event_rejected`.
- Frontend `NotificationsScreen.handlePressNotification` tipe göre yönlendirir;
  `data` alanında hedef id'ler (`event_id`, `match_id`, `other_user_id`, ...).
- Keşfet ekranındaki çan ikonu okunmamış bildirim varsa kırmızı nokta gösterir.

---

## 10. Ödeme

- iyzipay — Premium abonelik, Spotlight boost, ekstra süper beğeni / swipe paketi.
- `apply_purchase` → `user.extra_super_likes` / `bonus_swipe_credits` /
  `boosts_balance` / abonelik. Callback'lerde `paidPrice` == sunucu fiyatı
  kontrolü + idempotency.

---

## 11. Migration notu

Alembic geçmişinde bir merge-point var; DB divergent branch'i "uygulandı" olarak
kaydetmemiş olabilir. `alembic upgrade head` "column already exists" ile
patlarsa `scripts/sync_schema_to_head.py` head-path DDL'i idempotent uygular +
`alembic stamp head` yapar.
