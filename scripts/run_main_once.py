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

from main import Application
from storage.db import DatabaseManager

db = DatabaseManager()


async def run_live_cycle():
    print("=" * 80)
    print("🚀 main.py Canlı Döngü Çalıştırması (1 Döngü)")
    print("=" * 80)

    app = Application()
    
    # 1 Döngü çalıştır ve durdur
    task = asyncio.create_task(app.run())
    await asyncio.sleep(5.0)
    app.stop()
    await task

    print("\n" + "=" * 80)
    print("📊 Canlı Döngü Sonrası Veritabanı ve Paper Trading Durumu:")
    print("=" * 80)

    stats = db.get_stats()
    pt_stats = db.get_paper_trades_stats()
    print(f"- Toplam Bildirim Sayısı      : {stats['total_notifications']}")
    print(f"- İşlenmemiş Bildirim Sayısı  : {stats['unprocessed_notifications']}")
    print(f"- Analiz Edilmiş Bildirim     : {stats['analyzed_notifications']}")
    print(f"- Paper Trading Toplam İşlem  : {pt_stats['total_trades']}")
    print(f"- Paper Trading 1G İsabet     : %{pt_stats['hit_rate_1d']}")
    print(f"- Paper Trading 5G İsabet     : %{pt_stats['hit_rate_5d']}")

    # Son Eklenen Paper Trades
    trades = db.get_all_paper_trades(limit=5)
    print("\n--- Son 5 Paper Trading Kaydı ---")
    for t in trades:
        print(f"[{t['id']}] {t['stock_code']} | {t['recommendation']} (Güven: {t['confidence']}/5) | Giriş: ₺{t['entry_price'] or 0:.2f} ({t['entry_note']}) | Tarih: {t['recommended_at']}")


if __name__ == "__main__":
    asyncio.run(run_live_cycle())
