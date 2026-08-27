import asyncio
import signal
import sys
from datetime import datetime
from pathlib import Path

# Proje kök dizinini sys.path'e ekle
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from config.settings import settings
from config.logger import get_logger
from ingestion import KAPFeedFetcher, KAPAnalyzer
from scripts.check_paper_trades import run_paper_trades_check
from storage.db import db

logger = get_logger("main")


class Application:
    """
    Borsa-AI Ana Servis Yöneticisi.
    KAP bildirimlerini çeker, kaydeder, yerel LLM ile analiz eder
    ve Paper Trading günlüğünü periyodik olarak doğrular.
    """

    def __init__(self, fetcher=None, analyzer=None):
        self.stop_event = asyncio.Event()
        self.fetcher = fetcher or KAPFeedFetcher(
            watchlist=settings.watchlist,
            disclosure_class="ODA",
        )
        self.analyzer = analyzer or KAPAnalyzer()
        self.last_paper_check_time = None

    @property
    def is_running(self) -> bool:
        return not self.stop_event.is_set()

    def handle_signal(self):
        logger.info("Durdurma sinyali alındı. Servisler nazikçe kapatılıyor...")
        self.stop_event.set()

    def stop(self):
        self.handle_signal()

    async def start(self):
        await self.run()

    async def run(self):
        logger.info("=" * 65)
        logger.info("🚀 Borsa-AI: KAP Analiz & Paper Trading Servisi Başlatılıyor...")
        watchlist_display = ', '.join(settings.watchlist) if settings.watchlist else "TÜM BIST (Tüm Piyasa)"
        logger.info(f"Takip Edilen Hisseler : {watchlist_display}")
        logger.info(f"Veri Kaynağı Sınıfı   : {self.fetcher.disclosure_class} (Özel Durum Açıklamaları)")
        logger.info(f"Yerel LLM Modeli      : {self.analyzer.model_name} ({self.analyzer.base_url})")
        logger.info(f"Veritabanı Yolu       : {settings.DB_PATH}")
        logger.info("=" * 65)

        # Başlangıç DB durumu
        stats = db.get_stats()
        pt_stats = db.get_paper_trades_stats()
        logger.info(
            f"Mevcut DB Durumu: Toplam {stats['total_notifications']} bildirim "
            f"({stats['unprocessed_notifications']} işlenmemiş), {stats['unique_companies_tracked']} şirket."
        )
        logger.info(
            f"Paper Trading Durumu: Toplam {pt_stats['total_trades']} işlem "
            f"({pt_stats['pending_count']} bekleyen)."
        )

        cycle_count = 0

        while not self.stop_event.is_set():
            cycle_count += 1
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # Kalp atışı ve sistem canlılık kaydı
            db.record_heartbeat()
            logger.info(f"\n--- [Döngü #{cycle_count} | {now_str}] KAP & Paper Trading Taraması Başlatılıyor ---")

            try:
                # 1. KAP'tan Canlı ÖDA Bildirimlerini Çek
                notifications = await self.fetcher.fetch_latest(stop_event=self.stop_event)

                if notifications:
                    inserted_count, total_fetched = db.save_notifications_batch(notifications)
                    logger.info(
                        f"📥 {total_fetched} adet bildirim alındı, {inserted_count} adet YENİ bildirim kaydedildi."
                    )
                else:
                    logger.info("ℹ️ KAP kaynağından yeni bildirim dönmedi veya rate-limit soğumasında.")

                # 2. İşlenmemiş Bildirimleri Yerel LLM ile Analiz Et
                analyzed_count = await self.analyzer.analyze_unprocessed(limit=settings.ANALYSIS_BATCH_SIZE)
                if analyzed_count > 0:
                    logger.info(f"🤖 {analyzed_count} adet yeni bildirim analiz edildi.")

                # 3. Paper Trading Günlüğünü Doğrula (yfinance spamini önlemek için en fazla 4 saatte bir çalışır)
                now_dt = datetime.now()
                if (
                    self.last_paper_check_time is None
                    or (now_dt - self.last_paper_check_time).total_seconds() >= 14400
                ):
                    logger.info("🔍 Periyodik Paper Trading doğrulama kontrolü yapılıyor...")
                    pt_check_res = run_paper_trades_check()
                    self.last_paper_check_time = now_dt
                    if pt_check_res["checked_1d"] > 0 or pt_check_res["checked_5d"] > 0:
                        logger.info(
                            f"📊 Paper Trading Güncellendi: 1G={pt_check_res['checked_1d']}, 5G={pt_check_res['checked_5d']}"
                        )

            except Exception as e:
                logger.error(f"Döngü sırasında hata oluştu: {e}", exc_info=True)

            # Bir sonraki döngüye kadar nazik bekleme
            try:
                await asyncio.wait_for(
                    self.stop_event.wait(),
                    timeout=settings.SCRAPE_INTERVAL_SECONDS,
                )
            except asyncio.TimeoutError:
                pass

        logger.info("Servis durduruldu. İyi günler!")


def main():
    app = Application()

    # Windows / Unix sinyal yönetimi
    if sys.platform != "win32":
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, app.handle_signal)

    try:
        asyncio.run(app.run())
    except KeyboardInterrupt:
        logger.info("Kullanıcı tarafından manuel durduruldu (Ctrl+C).")


# Geriye dönük uyumluluk takma adı
BorsaAIService = Application

if __name__ == "__main__":
    main()
