"""
Borsa-AI Uçtan Uca Örnek Test ve Demo Scripti

Bu script:
1. KAP'tan canlı olarak THYAO ve ASELS bildirimlerini çeker.
2. Veritabanına (SQLite) idempotent şekilde kaydeder.
3. Kayıtlı bildirimleri ve istatistikleri ekrana yazdırır.
4. İşlenmemiş kuyruktan bir bildirimi okuyup "işlendi" (is_processed=1) olarak işaretler.
"""

import asyncio
import sys
from pprint import pprint

# Windows konsolu için UTF-8 desteği
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from ingestion.kap_feed import KAPFeedFetcher
from storage.db import DatabaseManager
from config.settings import settings


async def main():
    print("=" * 70)
    print("🚀 Borsa-AI: Uçtan Uca Örnek Çalışma Testi")
    print("=" * 70)

    # 1. Veri çekiciyi sadece 2 hisse ile başlatalım (Hızlı demo için)
    demo_tickers = ["THYAO", "ASELS"]
    print(f"\n1. [{', '.join(demo_tickers)}] için KAP bildirimleri çekiliyor...")
    
    fetcher = KAPFeedFetcher(watchlist=demo_tickers, disclosure_types=["FAR", "KDP"])
    notifications = await fetcher.fetch_latest()
    
    print(f"✅ Toplam {len(notifications)} adet bildirim çekildi.")

    if notifications:
        print("\n--- Çekilen İlk Bildirim Modeli Örneği ---")
        sample = notifications[0]
        pprint({
            "ID": sample.id,
            "Hisse Kodu": sample.stock_code,
            "Şirket": sample.company_name,
            "Başlık": sample.title,
            "Yayın Tarihi": sample.publish_date,
            "Özet": sample.summary[:100] + ("..." if len(sample.summary) > 100 else ""),
            "KAP Linki": sample.link,
            "İşlendi mi": sample.is_processed,
        })

    # 2. SQLite Veritabanına Kaydetme
    print("\n2. Bildirimler SQLite veritabanına kaydediliyor...")
    db = DatabaseManager()  # storage/borsa.db
    new_count, total_count = db.save_notifications_batch(notifications)
    print(f"✅ {total_count} bildirim işlendi -> {new_count} YENİ kayıt eklendi.")

    # 3. İstatistikleri Sorgulama
    stats = db.get_stats()
    print("\n3. Veritabanı Güncel İstatistikleri:")
    pprint(stats)

    # 4. İşlenmemiş Kuyruktan Bildirim Okuma (İleride LLM / Analiz için)
    print("\n4. Kuyruktan İşlenmemiş İlk 3 Bildirim Okunuyor:")
    unprocessed = db.get_unprocessed_notifications(limit=3)
    for i, notif in enumerate(unprocessed, 1):
        print(f"  [{i}] ID: {notif.id} | {notif.stock_code} - {notif.title} ({notif.publish_date})")

    # 5. Bir Bildirimi "İşlendi" Olarak İşaretleme Demo
    if unprocessed:
        target_id = unprocessed[0].id
        print(f"\n5. ID '{target_id}' olan bildirim 'is_processed = 1' olarak güncelleniyor...")
        success = db.mark_as_processed(target_id)
        print(f"✅ Güncelleme başarılı mı: {success}")
        
        # Güncel istatistik
        updated_stats = db.get_stats()
        print(f"📊 Yeni İşlenmemiş Bildirim Sayısı: {updated_stats['unprocessed_notifications']}")

    print("\n" + "=" * 70)
    print("✅ Örnek test başarıyla tamamlandı!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
