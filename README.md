# Borsa-AI: KAP Bildirim Toplama ve Kayıt Sistemi

Borsa İstanbul (KAP - Kamuyu Aydınlatma Platformu) ve 3. parti finansal veri kaynaklarından bildirimleri periyodik olarak toplayan, SQLite veritabanına mükerrer kaydı engelleyerek (idempotent) kaydeden ve canlı gösterge paneli (dashboard) ile izleme imkanı sunan Python altyapısıdır.

> [!NOTE]
> Bu aşamada sistem sadece **veri toplama (ingestion)** ve **veritabanına kayıt (storage)** işlemlerini gerçekleştirir. Alım-satım mantığı, broker bağlantıları veya LLM entegrasyonu içermez; ancak ileride eklenecek analiz ve karar modülleri için `is_processed` kuyruk yapısıyla tam uyumludur.

---

## 📁 Proje Yapısı

```text
borsa-ai/
├── config/
│   ├── settings.py           # Merkezi ayarlar (URL, çekme sıklığı, timeout, header'lar)
│   └── logger.py             # Zaman damgalı, konsol + dönen dosya loglayıcı (RotatingFileHandler)
├── ingestion/
│   ├── models.py             # Pydantic KapNotification veri modeli
│   └── kap_feed.py           # JSON/RSS esnek ayrıştırıcı, regex hisse tespit motoru, 403/429 hata koruması
├── storage/
│   └── db.py                 # SQLite veritabanı, UNIQUE constraint, indeksler, batch kayıt ve kuyruk
├── dashboard/
│   ├── app.py                # FastAPI web sunucusu ve REST API uçları
│   └── templates/
│       └── index.html        # Modern koyu tema (dark mode) canlı bildirim takip tablosu
├── logs/
│   └── borsa_ai.log          # Çalışma anında otomatik üretilen zaman damgalı loglar
├── tests/
│   ├── test_ingestion.py     # Regex hisse tespiti, JSON/XML parser ve çökme koruması testleri
│   └── test_storage.py       # SQLite veritabanı, mükerrer kayıt engelleme ve kuyruk testleri
├── main.py                   # Asyncio periyodik ana döngü ve Graceful Shutdown (Ctrl+C)
├── requirements.txt          # Gerekli Python bağımlılıkları
└── README.md                 # Proje dokümantasyonu
```

---

## ⚙️ Kurulum

Python 3.10 veya üzeri gereklidir.

```bash
# 1. Sanal ortam oluşturma ve etkinleştirme
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux / macOS

# 2. Bağımlılıkları yükleme (pykap ve diğer kütüphaneler)
pip install -r requirements.txt
```

---

## 🚀 Çalıştırma

### 1. Ana Veri Toplama Servisini Başlatma (main.py)
```bash
python main.py
```
- Takip listesindeki (BIST 30 / BIST 100) şirketlerin bildirimlerini `pykap` üzerinden çeker.
- Yeni bildirimleri `storage/borsa.db` içine idempotent olarak kaydeder.
- `logs/borsa_ai.log` dosyasına ve konsola işlem özetini yazar.
- `Ctrl+C` basıldığında temiz ve güvenli bir şekilde kapanır (`Graceful Shutdown`).

### 2. Canlı Takip Panelini Başlatma (Dashboard)
```bash
uvicorn dashboard.app:app --port 8000
```
Tarayıcınızdan `http://localhost:8000` adresine giderek gelen bildirimleri, şirket dağılımlarını ve sistem istatistiklerini izleyebilirsiniz.

---

## 🔧 Yapılandırma

`config/settings.py` dosyası üzerinden parametreler özelleştirilebilir veya ortam değişkeni (`.env`) olarak tanımlanabilir:

| Parametre | Varsayılan Değer | Açıklama |
|---|---|---|
| `WATCHLIST` | `THYAO,GARAN,ASELS,...` (BIST 30) | Takip edilecek hisse kodları listesi |
| `FETCH_INTERVAL_SECONDS` | `60` | Çekme periyodu (saniye) |
| `DB_PATH` | `storage/borsa.db` | SQLite veritabanı dosya yolu |
| `LOG_LEVEL` | `INFO` | Log seviyesi (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

> [!TIP]
> **KAP Endpoint Doğrulaması Hakkında Not:**
> KAP'ın doğrudan web arayüzü (`kap.org.tr/tr/bildirim-sorgu`) üzerinde tarayıcı Network sekmesinden tespit edeceğiniz güncel JSON endpoint'ini veya Foreks / Matriks gibi sağlayıcılardan temin edeceğiniz yapılandırılmış veri köprüsünü `KAP_ENDPOINT_URL` alanına yazmanız yeterlidir. Modül, hem JSON hem de RSS/XML formatlarını otomatik tanır.

---

## 🛡️ Hata Toleransı ve Güvenlik Önlemleri

1. **Bot / Rate-Limit Koruması (HTTP 403 / 429)**: KAP veya WAF kaynaklı engeller algılandığında sistem çökmez; özel `[BOT_BLOCKED]` veya `[RATE_LIMIT]` uyarısı loglayarak bir sonraki periyoda kadar bekler.
2. **Mükerrer Kayıt Engelleme (Idempotent)**: Bildirim kimliği (ID) veya içerik karması (MD5 hash) birincil anahtar (Primary Key) olarak kullanılır. Aynı bildirim defalarca çekilse dahi `INSERT OR IGNORE` sayesinde veritabanında tek bir kez tutulur.
3. **Regex Tabanlı Hisse Tespiti**: `[THYAO]`, `(GARAN, AKBNK)`, `EREGL - Finansal Rapor` ve `BIMAS.E` gibi çoklu BIST hisse kodu formatlarını otomatik olarak ayrıştırır.

---

## 🧪 Testleri Çalıştırma

Tüm birim ve entegrasyon testlerini çalıştırmak için:

```bash
pytest -v
```
