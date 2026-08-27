import os
import tempfile
from pathlib import Path
import pytest

from storage.db import DatabaseManager
from ingestion.models import KapNotification


@pytest.fixture
def temp_db():
    """Geçici bir veritabanı dosyası oluşturur ve test bitince siler."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_borsa.db"
        manager = DatabaseManager(db_path=db_path)
        yield manager


class TestDatabaseManager:
    """
    SQLite veritabanı ve idempotent (mükerrer engelleme) kayıt testleri.
    """

    def test_init_db(self, temp_db: DatabaseManager):
        # Tablolar oluşturuldu mu kontrol et
        with temp_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='kap_notifications';"
            )
            assert cursor.fetchone() is not None

    def test_save_single_notification(self, temp_db: DatabaseManager):
        notif = KapNotification(
            id="KAP-001",
            stock_code="THYAO",
            company_name="TÜRK HAVA YOLLARI",
            title="Uçuş Hatları Bildirimi",
            publish_date="2026-08-26 12:00:00",
            summary="Yeni uçuş noktaları eklendi.",
            link="https://kap.org.tr/tr/Bildirim/KAP-001",
        )

        inserted = temp_db.save_notification(notif)
        assert inserted is True

        # Tekrar aynı ID ile kaydetmeye çalışınca False dönmeli (Unique constraint / idempotent)
        inserted_again = temp_db.save_notification(notif)
        assert inserted_again is False

    def test_save_batch_idempotency(self, temp_db: DatabaseManager):
        notifs = [
            KapNotification(
                id="KAP-101",
                stock_code="ASELS",
                title="Sözleşme İmzalanması",
                publish_date="2026-08-26 10:00:00",
            ),
            KapNotification(
                id="KAP-102",
                stock_code="GARAN",
                title="Faiz Oranları Kararı",
                publish_date="2026-08-26 11:00:00",
            ),
        ]

        # 1. Kayıt: 2'si de yeni
        new_count, total = temp_db.save_notifications_batch(notifs)
        assert new_count == 2
        assert total == 2

        # 2. Kayıt (1 yeni + 1 eski)
        mixed_notifs = [
            notifs[0],  # KAP-101 zaten kayıtlı
            KapNotification(
                id="KAP-103",
                stock_code="EREGL",
                title="Üretim Raporu",
                publish_date="2026-08-26 12:00:00",
            ),
        ]
        new_count_mixed, total_mixed = temp_db.save_notifications_batch(mixed_notifs)
        assert new_count_mixed == 1
        assert total_mixed == 2

        # Toplam kayıt sayısı 3 olmalı
        stats = temp_db.get_stats()
        assert stats["total_notifications"] == 3

    def test_unprocessed_queue_and_marking(self, temp_db: DatabaseManager):
        notif = KapNotification(
            id="KAP-201",
            stock_code="KCHOL",
            title="Genel Kurul Kararları",
            publish_date="2026-08-26 14:00:00",
            is_processed=False,
        )
        temp_db.save_notification(notif)

        unprocessed = temp_db.get_unprocessed_notifications()
        assert len(unprocessed) >= 1
        assert unprocessed[0].id == "KAP-201"

        # İşlendi olarak işaretle
        marked = temp_db.mark_as_processed("KAP-201")
        assert marked is True

        # Artık kuyrukta olmamalı
        remaining = temp_db.get_unprocessed_notifications()
        assert not any(n.id == "KAP-201" for n in remaining)
