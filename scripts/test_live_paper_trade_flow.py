import asyncio
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
from scripts.check_paper_trades import run_paper_trades_check

db = DatabaseManager()
analyzer = KAPAnalyzer()


async def run_test():
    print("=" * 85)
    print("🧪 Paper Trading Gerçek Akış Testi Başlatılıyor...")
    print("=" * 85)

    # 2 Adet Gerçek Haber Nitelikli Bildirim (1 AL Katalizörü, 1 SAT Katalizörü)
    test_notifications = [
        KapNotification(
            id="LIVE-PT-THYAO-01",
            disclosure_index=700101,
            stock_code="THYAO",
            stock_codes="THYAO",
            company_name="TÜRK HAVA YOLLARI A.O.",
            title="Pay Geri Alım İşlemleri",
            subject="Pay Geri Alım İşlemleri",
            disclosure_class="ODA",
            publish_date="2023-05-15 17:45:00",  # Seans içi
            summary="Şirketimiz Yönetim Kurulu kararı uyarınca 500.000 adet pay geri alımı gerçekleştirilmiştir.",
            link="https://www.kap.org.tr/tr/Bildirim/700101",
            is_processed=False,
        ),
        KapNotification(
            id="LIVE-PT-ARCLK-02",
            disclosure_index=700102,
            stock_code="ARCLK",
            stock_codes="ARCLK",
            company_name="ARÇELİK A.Ş.",
            title="Faaliyetlerin Kısmen veya Tamamen Durdurulması",
            subject="Faaliyetlerin Kısmen veya Tamamen Durdurulması",
            disclosure_class="ODA",
            publish_date="2020-04-15 19:25:00",  # Kapanış sonrası (18:00+)
            summary="Bazı ülkelerdeki fabrikalarda üretime 2 hafta süreyle ara verilmesine karar verilmiştir.",
            link="https://www.kap.org.tr/tr/Bildirim/700102",
            is_processed=False,
        ),
    ]

    # 1. DB'ye kaydet
    for notif in test_notifications:
        db.save_notification(notif)
        # Yeniden analize hazırla
        with db.get_connection() as conn:
            conn.cursor().execute("UPDATE kap_notifications SET is_processed = 0 WHERE id = ?;", (notif.id,))

    print("1. Bildirimler veritabanına eklendi.")

    # 2. Analyzer çalıştır (AL ve SAT çıkınca otomatik paper_trades kaydı açacak)
    print("\n2. Yerel LLM Analizi çalıştırılıyor...")
    for notif in test_notifications:
        res = await analyzer.analyze_notification(notif)
        if res:
            db.save_analysis_result(
                notification_id=notif.id,
                recommendation=res["recommendation"],
                reasoning=res["reasoning"],
                confidence=res["confidence"],
            )

    # 3. Paper Trading Kayıtlarını Kontrol Et
    print("\n3. Paper Trading Günlüğü Kayıtları:")
    trades = db.get_all_paper_trades(limit=10)
    for t in trades:
        print(
            f"-> #{t['id']} {t['stock_code']} | Öneri: {t['recommendation']} | "
            f"Güven: {t['confidence']}/5 | Giriş: ₺{t['entry_price'] or 0:.2f} ({t['entry_note']}) | "
            f"1G: {t['outcome_1d']} | 5G: {t['outcome_5d']}"
        )

    # 4. Doğrulama scriptini çalıştır
    print("\n4. Paper Trades Doğrulama Motoru (check_paper_trades) tetikleniyor...")
    check_res = run_paper_trades_check()
    print(f"Doğrulama Sonucu: {check_res}")

    # 5. Güncel İstatistikler
    stats = db.get_paper_trades_stats()
    print("\n5. Güncel Paper Trading İstatistikleri:")
    print(f"- Toplam İşlem: {stats['total_trades']}")
    print(f"- 1G İsabet Oranı: %{stats['hit_rate_1d']} ({stats['correct_1d']}/{stats['resolved_1d']})")
    print(f"- 5G İsabet Oranı: %{stats['hit_rate_5d']} ({stats['correct_5d']}/{stats['resolved_5d']})")
    print(f"- Bekleyen İşlemler: {stats['pending_count']}")


if __name__ == "__main__":
    asyncio.run(run_test())
