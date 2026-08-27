import pytest
from ingestion.models import KapNotification
from ingestion.kap_feed import KAPFeedFetcher


class TestKAPFeedMapping:
    """KAPFeedFetcher veri eşleme testleri."""

    def test_map_oda_item_success(self):
        fetcher = KAPFeedFetcher(watchlist=["THYAO"])
        sample_item = {
            "title": "Özel Durum Açıklaması",
            "companyTitle": "TÜRK HAVA YOLLARI A.O.",
            "stockCodes": "THYAO",
            "disclosureClass": "ODA",
            "disclosureType": "ODA",
            "publishDate": "15.05.2023 17:45:00",
            "disclosureIndex": 700101,
            "summary": "Pay geri alım işlemleri gerçekleştirilmiştir.",
            "subject": "Pay Geri Alımı",
        }

        notif = fetcher._map_oda_item(sample_item)
        assert notif is not None
        assert notif.stock_code == "THYAO"
        assert notif.disclosure_index == 700101
        assert notif.disclosure_class == "ODA"
        assert "Pay geri alım" in notif.summary
        assert notif.link == "https://www.kap.org.tr/tr/Bildirim/700101"

    def test_map_oda_item_invalid(self):
        fetcher = KAPFeedFetcher()
        # disclosureIndex eksik
        sample_item = {
            "title": "Geçersiz Bildirim",
        }
        notif = fetcher._map_oda_item(sample_item)
        assert notif is None
