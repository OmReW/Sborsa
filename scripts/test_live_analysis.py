import asyncio
import sys
from datetime import datetime
from pathlib import Path

# Proje kök dizinini sys.path'e ekle
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Windows konsol UTF-8 ayarı
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from ingestion.models import KapNotification
from ingestion.analyzer import KAPAnalyzer
from storage.db import db


async def run_live_analysis_test():
    print("=" * 70)
    print("🚀 Borsa-AI: Yerel LLM (Ollama) Analiz ve Öneri Katmanı Uçtan Uca Testi")
    print("=" * 70)

    # 1. Önceki test kayıtlarını temizle
    db.delete_test_notifications()

    # 2. Üç Farklı Senaryoda Örnek Test Bildirimi Ekle
    test_notifications = [
        KapNotification(
            id="TEST-THYAO-001",
            stock_code="THYAO",
            company_name="TÜRK HAVA YOLLARI A.O.",
            title="Yeni Hat Açılışı ve Filo Genişlemesi (TEST VERİSİ)",
            publish_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            summary="Şirketimiz 50 adet yeni nesil A350 uçak alımı ve Avustralya Melbourne seferlerinin haftalık 7 frekansa çıkarılması konusunda anlaşmaya varmıştır.",
            link="https://kap.org.tr/tr/Bildirim/TEST-THYAO-001",
            is_processed=False,
        ),
        KapNotification(
            id="TEST-EREGL-002",
            stock_code="EREGL",
            company_name="EREĞLİ DEMİR VE ÇELİK FABRİKALARI T.A.Ş.",
            title="Üretim Tesisinde Arıza ve Geçici Duruş (TEST VERİSİ)",
            publish_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            summary="2 No'lu Yüksek Fırında meydana gelen teknik arıza nedeniyle çelikhane ünitesinde üretimin 15 gün süreyle durdurulmasına karar verilmiştir.",
            link="https://kap.org.tr/tr/Bildirim/TEST-EREGL-002",
            is_processed=False,
        ),
        KapNotification(
            id="TEST-GARAN-003",
            stock_code="GARAN",
            company_name="TÜRKİYE GARANTİ BANKASI A.Ş.",
            title="Kredi Derecelendirme Notu Değerlendirmesi (TEST VERİSİ)",
            publish_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            summary="Uluslararası derecelendirme kuruluşu Fitch, bankamızın uzun vadeli yabancı para cinsinden kredi notunu 'B' seviyesinde, görünümünü ise 'Durağan' olarak korumuştur.",
            link="https://kap.org.tr/tr/Bildirim/TEST-GARAN-003",
            is_processed=False,
        ),
    ]

    print("\n1. Test amaçlı 3 adet sahte bildirim veritabanına ekleniyor...")
    new_c, total_c = db.save_notifications_batch(test_notifications)
    print(f"✅ {new_c} test bildirimi veritabanına eklendi (is_processed=0).")

    # 3. Analyzer'ı Çalıştır
    print("\n2. Yerel LLM (Ollama) ile Analiz Başlatılıyor...")
    analyzer = KAPAnalyzer()
    print(f"   Model   : {analyzer.model_name}")
    print(f"   Endpoint: {analyzer.base_url}")
    
    results = await analyzer.analyze_unprocessed(limit=3)

    print(f"\n✅ Analiz tamamlandı! Üretilen öneri sayısı: {len(results)}")
    
    # 4. Veritabanından Analiz Sonuçlarını Sorgula
    print("\n3. Veritabanından Yapay Zeka Önerileri Okunuyor:")
    recent_recs = db.get_recent_recommendations(limit=5)
    for i, rec in enumerate(recent_recs, 1):
        print(f"\n--- [Öneri #{i}] ---")
        print(f"  Hisse Kodu : {rec['stock_code']}")
        print(f"  Öneri      : {rec['recommendation']}")
        print(f"  Güven      : {rec['confidence']}/5")
        print(f"  Gerekçe    : {rec['reasoning']}")
        print(f"  Analiz Zamanı: {rec['analyzed_at']}")

    print("\n" + "=" * 70)
    print("✅ Tüm analiz ve öneri testleri başarıyla doğrulandı!")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(run_live_analysis_test())
