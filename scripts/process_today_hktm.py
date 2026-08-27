import asyncio
import json
import sys
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
from storage.db import DatabaseManager

db = DatabaseManager()
analyzer = KAPAnalyzer()


async def process_hktm():
    print("=" * 85)
    print("📥 Bugünün (27.08.2026) Canlı HKTM Bildirimi Analiz Ediliyor...")
    print("=" * 85)

    # Bugünün gerçek KAP verisi
    hktm_notif = KapNotification(
        id="ODA-1655241",
        disclosure_index=1655241,
        stock_code="HKTM",
        stock_codes="HKTM",
        company_name="HİDROPAR HAREKET KONTROL TEKNOLOJİLERİ MERKEZİ SANAYİ VE TİCARET A.Ş.",
        title="Özel Durum Açıklaması (Genel)",
        subject="Özel Durum Açıklaması (Genel)",
        disclosure_class="ODA",
        disclosure_type="ODA",
        publish_date="27.08.2026 00:00:28",
        summary="Şirket Çoğunluk Paylarının Satışının Tamamlanması ",
        link="https://www.kap.org.tr/tr/Bildirim/1655241",
        is_processed=False,
    )

    # 1. DB'ye kaydet
    db.save_notification(hktm_notif)

    # 2. LLM Analizi
    res = await analyzer.analyze_notification(hktm_notif)
    if res:
        db.save_analysis_result(
            notification_id=hktm_notif.id,
            recommendation=res["recommendation"],
            reasoning=res["reasoning"],
            confidence=res["confidence"],
        )

    # 3. Paper Trading Kaydını DB'den Çek ve Göster
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM paper_trades WHERE notification_id = 'ODA-1655241';
            """
        )
        row = cursor.fetchone()

    print("\n" + "=" * 85)
    print("📋 PAPER TRADES TABLOSUNDAKİ BUGÜNE AİT GERÇEK KAYIT (HAM DB ÇIKTISI)")
    print("=" * 85)

    if row:
        trade = dict(row)
        for k, v in trade.items():
            print(f"{k:<18}: {v}")
    else:
        print("Paper trade kaydı bulunamadı (Öneri NÖTR çıkmış olabilir).")


if __name__ == "__main__":
    asyncio.run(process_hktm())
