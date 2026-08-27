import asyncio
import json
import sys
from pathlib import Path

# Proje kök dizinini sys.path'e ekle
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from ingestion.models import KapNotification
from ingestion.analyzer import KAPAnalyzer
from storage.db import DatabaseManager

db = DatabaseManager()
analyzer = KAPAnalyzer()


async def process_live_catalysts():
    print("=" * 85)
    print("📥 Canlı 26-27 Ağustos KAP Bildirimleri Analiz Ediliyor...")
    print("=" * 85)

    notifications = [
        KapNotification(
            id="ODA-1655175",
            disclosure_index=1655175,
            stock_code="EKGYO",
            stock_codes="EKGYO",
            company_name="EMLAK KONUT GAYRİMENKUL YATIRIM ORTAKLIĞI A.Ş.",
            title="Sözleşme İmzalanması",
            subject="Yeni İş İlişkisi / Sözleşme",
            disclosure_class="ODA",
            publish_date="26.08.2026 18:04:44",
            summary="İstanbul Küçükçekmece Halkalı Batı 1. Etap Sözleşme İmzalanması",
            link="https://www.kap.org.tr/tr/Bildirim/1655175",
            is_processed=False,
        ),
        KapNotification(
            id="ODA-1655096",
            disclosure_index=1655096,
            stock_code="FORTE",
            stock_codes="FORTE",
            company_name="FORTE BİLGİ İLETİŞİM TEKNOLOJİLERİ VE SAVUNMA SANAYİ A.Ş.",
            title="Yeni İş İlişkisi",
            subject="Yeni İş İlişkisi",
            disclosure_class="ODA",
            publish_date="26.08.2026 15:05:41",
            summary="Savunma sanayii alanında 15.000.000 USD tutarında yeni sipariş alınması",
            link="https://www.kap.org.tr/tr/Bildirim/1655096",
            is_processed=False,
        ),
    ]

    for notif in notifications:
        db.save_notification(notif)
        res = await analyzer.analyze_notification(notif)
        if res:
            db.save_analysis_result(
                notification_id=notif.id,
                recommendation=res["recommendation"],
                reasoning=res["reasoning"],
                confidence=res["confidence"],
            )

    # Paper Trades listesi
    trades = db.get_all_paper_trades(limit=10)
    print("\n" + "=" * 85)
    print("📋 PAPER TRADES TABLOSUNDAKİ EN YENİ KAYITLAR (HAM DB ÇIKTISI)")
    print("=" * 85)
    for t in trades:
        print(f"[{t['id']}] {t['stock_code']} | Öneri: {t['recommendation']} | Güven: {t['confidence']}/5 | Tarih: {t['recommended_at']} | Giriş: ₺{t['entry_price'] or 0:.2f} ({t['entry_note']})")


if __name__ == "__main__":
    asyncio.run(process_live_catalysts())
