# FindYourBuddy — Proje Durumu ve Yapılacaklar (Roadmap)

## 📌 Tamamlanan Son Geliştirmeler & Güvenlik
- [x] **Prompt Injection Koruması**: LLM moderasyon ve AI eşleşme uç noktalarında `sanitize_prompt_input` ile komut enjeksiyonu filtreleri aktif edildi.
- [x] **Biyometrik Veri Açık Rızası (KVKK)**: Profil selfie doğrulaması (Mavi Tik) için açık rıza metni `LegalScreen.tsx` (KVKK Aydınlatma Metni) içerisine eklendi.
- [x] **Ödeme Güvenliği**: İyzico ödeme dönüşlerinde (`credits/callback` ve `purchase/callback`) ödenen tutar (`paidPrice`) ile sunucudaki ürün fiyatı karşılaştırması ve idempotency kontrolleri doğrulandı.
- [x] **CORS Güvenliği**: Production ortamında `findyourbuddy.dev` alan adlarına katı regex kısıtlaması getirildi, yerel geliştirme IP'leri korundu.
- [x] **Sesli Tanıtım Oynatıcı**: `VoiceNotePlayer` bileşeni `expo-audio` ve HTML5 Audio desteğiyle canlı ses oynatır hale getirildi.
- [x] **Zodyak Uyumu Hesaplama**: `RecommendationService` ve AI öneri algoritması Ateş/Toprak/Hava/Su element sinerjisini %100 DRY matrisle hesaplar.
- [x] **Terminoloji Senkronizasyonu**: Arayüzdeki "Bilet" ifadeleri "Katılım Ücreti / Harcama" diline çevrildi.
- [x] **Rate Limiter — Gerçek IP**: `key_func=get_remote_address` tüm kullanıcıları aynı bucket'a düşürüyordu; `X-Forwarded-For` okuyarak gerçek client IP'ye göre limit uygulanır hale getirildi (mobil buton donması sorununun kök nedeni).
- [x] **Askıya Alınmış Hesap Hatası**: Suspend edilmiş kullanıcılar artık `401 "Invalid credentials"` yerine `403 "Hesabınız askıya alınmıştır."` alıyor (`AccountInactiveError`).
- [x] **Token Invalidation**: Trust skoru düşüp otomatik suspend olan kullanıcıların mevcut JWT token'ları `token_version` artırılarak anında geçersiz kılınıyor.
- [x] **XSS Koruması**: `purchase/callback` hata mesajları `escape()` ile sanitize edildi.
- [x] **Kod Kalitesi — Backend**: Inline importlar dosya başına taşındı; `.first() is not None` ve `.count()` kontrolleri `EXISTS` sorgusuyla değiştirildi; `list_matches_for_user` DB seviyesinde pagination + blok filtresi uyguluyor; `datetime.utcnow()` tüm test dosyalarında `datetime.now(timezone.utc)` ile değiştirildi. Tüm testler 298/298 geçiyor.
- [x] **Kod Kalitesi — Frontend**: 9 dosyada fonksiyon/tip tanımlarından sonra gelen misplaced importlar doğru yere taşındı; `MessagesScreen`'deki `as any` cast kaldırılarak tip güvenliği sağlandı.
- [x] **Scraping — İlk Çalıştırma Gecikmesi**: APScheduler `interval` trigger'ı başlangıçta tam interval süresi bekleyerek ilk scraping'i 6 saat erteliyordu; `next_run_time=datetime.now()` ile servis açılışında hemen çalışır hale getirildi.
- [x] **Scraping — Inline Import**: `normalizer.py` içindeki `import html/re` fonksiyon bloğu içinden dosya başına taşındı.
- [x] **Medya Depolama — S3MediaStorage**: `S3MediaStorage` sınıfı hem AWS S3 hem Cloudflare R2 için tamamen yazıldı; `boto3` inline import dosya başına alındı. Production'a geçmek için yalnızca `.env` değişkenleri ayarlanmalı.

---

## 🔮 Canlıya Geçiş (Production) Öncesi Yapılacaklar

### 1. Hukuk & Sözleşme Onayları (Hukuk Danışmanı)
- [ ] `LegalScreen.tsx` içindeki Kullanım Şartları ve KVKK Aydınlatma Metninin canlıya çıkış öncesinde nihai hukuk danışmanınca imzalanması.

### 2. Canlı API Anahtarları ve Ortam Değişkenleri
- [ ] Demo / Staging ortamından Production ortamına geçilirken `.env` içindeki `OPENAI_API_KEY`, `NOVITA_API_KEY` ve `IYZICO_API_KEY` değerlerinin canlı anahtarlarla güncellenmesi.

### 3. Medya Depolama — Production Ortam Değişkenleri
- [ ] `.env` dosyasına aşağıdaki değişkenlerin eklenmesi (kod hazır, sadece config gerekiyor):
  ```
  MEDIA_STORAGE_BACKEND=s3
  S3_BUCKET_NAME=...
  S3_REGION=auto                              # R2 için; AWS S3 için us-east-1 vb.
  S3_ENDPOINT_URL=https://<id>.r2.cloudflarestorage.com   # Sadece R2; AWS için boş bırak
  S3_ACCESS_KEY_ID=...
  S3_SECRET_ACCESS_KEY=...
  S3_PUBLIC_URL_BASE=https://...              # CDN veya bucket public URL
  ```
