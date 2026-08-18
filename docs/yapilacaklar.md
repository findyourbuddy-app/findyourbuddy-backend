# FindYourBuddy Backend — Yapılacaklar Listesi

Bu doküman, mevcut `findyourbuddy-backend` reposunun incelenmesi sonucu
belirlenen görevleri içerir. Her görev; neden gerekli olduğu, hangi
katmanları etkilediği, atılacak adımlar ve kabul kriterleri (test
beklentisi) ile birlikte verilmiştir.

Öncelik sırası: **P0** (davranışı/güvenliği doğrudan etkiler) →
**P1** (belgelenmiş eksik, ürün akışını tamamlar) → **P2** (temizlik /
iyileştirme).

---

## 1. [TAMAMLANDI] Bağımlılık yönetimini pip+requirements.txt'ten uv'ye taşı

> Bu görev tamamlandı: `requirements.txt` yok, `pyproject.toml` + `uv.lock`
> var, Docker build'i de `uv sync --frozen --no-dev` kullanıyor. Aşağıdaki
> adımlar arşiv amaçlı bırakıldı.

### Neden
Proje standardı Poetry veya uv olacak şekilde belirlendi; pip +
`requirements.txt` artık kullanılmayacak. Mevcut repo şu an
`requirements.txt` + pinlenmiş sürümlerle çalışıyor ve bu, daha önce
`docs/tech-kararlari.md` içinde "resmi karar" olarak yazılmıştı. Bu görev
hem kodu hem de dokümantasyonu yeni standarda taşır.

### Adımlar
1. `uv init` ile proje kökünde `pyproject.toml` oluştur (paket adı,
   Python sürümü — mevcut ortamla aynı sürüm kullanılmalı).
2. `requirements.txt`'teki tüm bağımlılıkları aynı pinlenmiş sürümlerle
   `uv add <paket>==<sürüm>` komutuyla ekle (fastapi, uvicorn[standard],
   sqlalchemy, alembic, psycopg2-binary, pydantic, pydantic-settings,
   email-validator, python-jose[cryptography], passlib[bcrypt], bcrypt,
   python-multipart, python-dotenv).
3. Test/dev bağımlılıklarını (`pytest`, `pytest-cov`, `httpx`) `uv add
   --dev` ile ayrı gruba ekle.
4. `uv.lock` dosyasının commit'lendiğinden emin ol.
5. `requirements.txt` dosyasını sil.
6. `README.md`'deki kurulum adımlarını güncelle:
   - `python -m venv env` + `pip install -r requirements.txt` bloğunu
     `uv sync` ile değiştir.
   - Çalıştırma komutunu `uv run uvicorn app.main:app --reload` olacak
     şekilde güncelle.
   - Migration ve test komutlarını da `uv run alembic upgrade head` /
     `uv run pytest` şeklinde güncelle.
7. CI varsa (GitHub Actions vb.) pip adımlarını `uv sync` ile değiştir.
8. `docs/tech-kararlari.md`'deki "Bağımlılık yönetimi: pip +
   requirements.txt..." satırını "uv, `pyproject.toml` + `uv.lock`,
   sürümler `uv.lock` üzerinden sabitleniyor" şeklinde güncelle.

### Kabul kriterleri
- Temiz bir ortamda `uv sync && uv run pytest` başarıyla çalışıyor.
- `requirements.txt` repoda kalmıyor.
- README ve `docs/tech-kararlari.md` yeni akışı doğru anlatıyor.

---

## 2. [P1] Genel API seviyesinde rate limiting

### Neden
Şu an sadece swipe endpoint'i için günlük limit var
(`DAILY_SWIPE_LIMIT`). Diğer endpoint'ler (auth, events, messages vb.)
herhangi bir istek sınırına tabi değil. `docs/tech-kararlari.md` bunu
"ertelenen karar" olarak işaretlemişti.

### Tasarım önerisi
- Basit, IP + user bazlı bir sliding-window/token-bucket rate limiter.
  Dış servise bağımlılık istemiyorsak `slowapi` (Starlette/FastAPI için
  yaygın kullanılan bir rate-limit kütüphanesi) eklenebilir — üçüncü
  parti kütüphane eklenirken proje kuralına göre neden gerekli olduğu
  kısaca not düşülmeli: "IP/kullanıcı bazlı pencereli sayaç mantığını
  sıfırdan yazıp test etmek yerine olgun, test edilmiş bir kütüphane
  kullanmak daha güvenli."
- Limit değerleri config-driven olmalı:
  - `RATE_LIMIT_DEFAULT_PER_MINUTE` (genel endpoint'ler için)
  - `RATE_LIMIT_AUTH_PER_MINUTE` (login/register — brute-force'a karşı
    daha sıkı bir limit, örn. 5/dakika)
- `app/core/rate_limit.py` içinde bir `Limiter` kurulumu + FastAPI
  middleware/dependency olarak `app/main.py`'a bağlanmalı.
- Limit aşıldığında `429 Too Many Requests` dönmeli (swipe limitiyle
  tutarlı).

### Adımlar
1. `app/config.py`'ye yeni ayarları ekle, `.env.example`'ı güncelle.
2. `app/core/rate_limit.py` oluştur: limiter kurulumu + varsayılan ve
   auth-özel limit tanımları.
3. `app/main.py`'da middleware/exception handler olarak bağla.
4. `app/routers/auth.py`'daki `/login` ve `/register`'a daha sıkı limit
   uygula (decorator veya dependency ile).
5. Diğer router'lara varsayılan limiti uygula.

### Kabul kriterleri
- Belirlenen limitin üzerinde istek atıldığında `429` dönüyor
  (entegrasyon testi ile doğrulanmalı — `TestClient` ile art arda istek
  atıp son isteğin 429 döndüğünü kontrol et).
- Limit değerleri test ortamında config üzerinden override edilebiliyor
  (testlerin yavaş/kırılgan olmaması için düşük bir test limiti
  kullanılmalı).
- Servis katmanına dokunulmuyor; bu tamamen `core`/router seviyesinde
  bir altyapı parçası.

---

## 3. [P1] Blok sonrası geriye dönük filtreleme

### Neden
Bir kullanıcı bloklandığında yeni swipe/eşleşme akışından hemen
filtreleniyor, ama blok öncesinde zaten oluşmuş eşleşmeler ve mesajlar
görünmeye devam ediyor. Bu, güvenlik/mahremiyet açısından bir boşluk.

### Tasarım önerisi
- Blok işlemi geriye dönük olarak **var olan eşleşmeyi silmiyor**,
  bunun yerine mevcut eşleşme/mesajlaşma bu kullanıcı için gizleniyor
  (soft-hide). Böylece rapor/moderasyon geçmişi bozulmuyor.
- `app/services/matching_service.py::list_matches_for_user` ve
  `app/services/message_service.py::list_messages` fonksiyonları,
  taraflar arasında aktif bir blok varsa sonucu filtrelemeli.

### Adımlar
1. `app/services/safety_service.py`'e `is_blocked` zaten var — bu
   fonksiyonu `matching_service.list_matches_for_user` içinde her
   eşleşme için kontrol edecek şekilde kullan (N+1 sorgu riskine karşı,
   kullanıcının tüm blok listesini tek seferde çekip in-memory
   filtrelemek daha uygun — `blocked_user_ids` zaten mevcut).
2. `message_service.list_messages` içinde de aynı kontrolü uygula: eğer
   match'teki karşı taraf bloklanmışsa (ya da bloklamışsa) mesaj listesi
   403 yerine boş/kilitli döndürülebilir — davranış kararı: mesaj
   geçmişine erişim tamamen kesilsin mi yoksa salt-okunur mu kalsın?
   Bu ürün kararı gerektiriyor, varsayım olarak "bloklu taraflar arası
   mesajlaşma geçmişi görüntülenemez" ile ilerlenmesi öneriliyor.
3. Yeni domain exception'a gerek yoksa mevcut `NotMatchParticipantError`
   ile karıştırılmamalı — ayrı bir `BlockedParticipantError` eklenmesi
   daha okunur olur.
4. `app/routers/matches.py` ve `app/routers/messages.py`'da bu yeni
   exception'ı uygun HTTP koduna (403) çevir.

### Kabul kriterleri
- Blok sonrası: bloklayan taraf `GET /matches/` çağırdığında bloklu
  kullanıcıyla olan eşleşme listede görünmüyor.
- Blok sonrası: `GET /matches/{id}/messages/` bloklu taraf için 403
  dönüyor.
- Unit test: `test_matching_service.py`'e blok senaryosu eklenmeli.
- Entegrasyon test: `test_safety_router.py` içine "blok sonrası eşleşme
  gizleniyor" senaryosu eklenmeli.

---

## 4. [P1] Mesaj "okundu" işaretleme endpoint'i

### Neden
`Message.is_read` alanı modelde tanımlı ama bunu güncelleyen bir route
yok. Mobil uygulamada okundu bilgisi kullanışlı bir özellik.

### Tasarım önerisi
- `PATCH /matches/{match_id}/messages/read` — eşleşmedeki, mevcut
  kullanıcının **almış olduğu** (kendi göndermediği) tüm okunmamış
  mesajları `is_read = True` yapar.
- Alternatif: tek mesaj bazlı `PATCH
  /matches/{match_id}/messages/{message_id}/read`. İki tasarımdan
  hangisinin istendiği net değil — toplu mu tekil mi işaretleme
  isteniyor, bu netleştirilmeli. Aşağıdaki adımlar toplu (tüm eşleşme
  için) versiyonu varsayıyor, en yaygın mobil UX deseni bu.

### Adımlar
1. `app/services/message_service.py`'e `mark_messages_as_read(db,
   match_id, reader_id) -> int` (etkilenen satır sayısını döner)
   fonksiyonu ekle. Mevcut `MatchNotFoundError` /
   `NotMatchParticipantError` kontrolleri burada da uygulanmalı.
2. `app/schemas/message.py`'e response için basit bir
   `MessagesMarkedRead(count: int)` şeması ekle (opsiyonel, `204 No
   Content` de tercih edilebilir).
3. `app/routers/messages.py`'e `PATCH /matches/{match_id}/messages/read`
   endpoint'i ekle.

### Kabul kriterleri
- Karşı tarafın gönderdiği okunmamış mesajlar işaretleniyor, kendi
  gönderdiklerimiz etkilenmiyor.
- Eşleşme bulunamazsa 404, katılımcı değilse 403.
- Servis seviyesinde unit test + router entegrasyon testi.

---

## 5. [P2] Moderasyon kelime listesini config'e taşı

### Neden
`app/services/moderation_service.py` içindeki `_BANNED_WORDS =
frozenset({"spam", "scam"})` kod içine gömülü. Proje kuralına göre
kolay değişebilecek her şey config/`.env` üzerinden okunmalı.

### Adımlar
1. `app/config.py`'ye `moderation_banned_words: str = "spam,scam"`
   ekle (virgülle ayrılmış, `CORS_ALLOWED_ORIGINS` ile aynı desende).
2. `moderation_service.py`'de bu string'i `frozenset` haline getiren bir
   yardımcı fonksiyon/`lru_cache`'li getter yaz — `contains_banned_words`
   her çağrıda `get_settings()` üzerinden okumalı, böylece test
   ortamında override edilebilir.
3. `.env.example`'a yeni değişkeni ekle.

### Kabul kriterleri
- Var olan `test_moderation_service.py` (yoksa eklenmeli) testleri config
  değeri değiştirildiğinde farklı kelimelerin yakalandığını doğruluyor.

---

## 6. [P2] Unblock (engeli kaldırma) endpoint'i

### Neden
`block_user` var ama kullanıcı bir engeli geri alamıyor. Küçük ama
gerçek bir ürün eksiği.

### Adımlar
1. `app/services/safety_service.py`'e `unblock_user(db, blocker_id,
   blocked_id)` ekle; blok kaydı yoksa `BlockNotFoundError` fırlat.
2. `app/routers/safety.py`'e `DELETE /users/{user_id}/block` ekle,
   `BlockNotFoundError` → 404.
3. Unit + entegrasyon test ekle (`test_safety_service.py`,
   `test_safety_router.py`).

### Kabul kriterleri
- Engel kaldırıldıktan sonra kullanıcı tekrar swipe candidate
  listesinde görünüyor.
- Var olmayan bir bloğu kaldırmaya çalışmak 404 dönüyor.

---

## 7. [P2] Rapor (Report) durumu güncelleme — moderasyon akışı

### Neden
`ReportStatus` enum'ı (`PENDING` vb.) modelde var ama raporu inceleyip
durumunu değiştiren bir endpoint yok. Şu an raporlar sadece oluşturulup
kayda düşüyor, kimse tarafından işlenemiyor.

### Not
Bu görev bir **admin/moderatör yetkilendirme modeli** gerektiriyor
(şu anki `User` modelinde rol/yetki alanı yok). Bu nedenle bu maddeye
başlamadan önce netleştirilmesi gereken sorular var:
- Moderatör rolü nasıl tanımlanacak? (`User.is_staff` gibi bir alan mı,
  ayrı bir tablo mu?)
- Bu iş MVP kapsamında mı, yoksa şimdilik sadece rapor kaydı tutmak
  yeterli mi?

Bu belirsizlik nedeniyle bu madde **tasarım kararı bekliyor**, aşağıdaki
adımlar sadece bir taslak.

### Taslak adımlar (rol modeli netleşince)
1. `User` modeline `is_staff: Mapped[bool] = mapped_column(default=False)`
   ekle + migration.
2. `app/core/deps.py`'e `get_current_staff_user` dependency'si ekle.
3. `app/services/safety_service.py`'e `update_report_status(db,
   report_id, new_status)` ekle.
4. `app/routers/safety.py`'e `PATCH /reports/{report_id}` (sadece staff)
   ekle.

---

## Özet tablo

| # | Görev | Öncelik | Etkilenen katmanlar |
|---|-------|---------|----------------------|
| 1 | pip → uv geçişi | P0 | proje kökü, README, docs |
| 2 | Genel API rate limiting | P1 | core, main, routers |
| 3 | Blok sonrası geriye dönük filtreleme | P1 | services, routers |
| 4 | Mesaj okundu işaretleme | P1 | services, schemas, routers |
| 5 | Moderasyon kelimeleri → config | P2 | config, services |
| 6 | Unblock endpoint'i | P2 | services, routers |
| 7 | Rapor durumu güncelleme (moderasyon) | P2 | **tasarım kararı bekliyor** |

Her madde tamamlandığında `docs/tech-kararlari.md`'nin ilgili bölümü
(özellikle "Ertelenen kararlar" kısmı) güncellenmeli, artık ertelenmiş
olmayan kararlar oradan çıkarılmalı.
