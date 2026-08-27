import asyncio
import json
from datetime import datetime, date
from typing import List, Optional, Dict, Any
import requests

from config.settings import settings
from config.logger import get_logger
from ingestion.models import KapNotification
from ingestion.rate_limiter import ExponentialBackoffRateLimiter

logger = get_logger("kap_feed")


class KAPFeedFetcher:
    """
    KAP (Kamuyu Aydınlatma Platformu) ÖDA (Özel Durum Açıklaması) ve Bildirim Çekici.
    
    Özellikler:
    - Birincil olarak metin ve haber içeren ÖDA (Özel Durum Açıklamaları) çeker.
    - Tek bir merkezi POST isteği ile tüm BIST bildirimlerini alır (429 engeli riski minimum).
    - Üstel geri çekilme (exponential backoff) ve hata toleransı içerir.
    """

    def __init__(
        self,
        watchlist: Optional[List[str]] = None,
        disclosure_class: str = "ODA",
        request_delay: float = 0.5,
    ):
        # watchlist verilmezse veya ['ALL'] ise tüm BIST taranır
        self.watchlist = watchlist
        self.disclosure_class = disclosure_class
        self.request_delay = request_delay
        self.rate_limiter = ExponentialBackoffRateLimiter(name="KAP")

        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Referer": "https://www.kap.org.tr/tr/bildirim-sorgu",
            "Origin": "https://www.kap.org.tr",
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
        }

    def _map_oda_item(self, item: Dict[str, Any]) -> Optional[KapNotification]:
        """
        KAP byCriteria veya list/main API yanıtını KapNotification modeline eşler.
        """
        try:
            # list/main veya byCriteria format uyumu
            basic = item.get("disclosureBasic") or item
            disc_idx = basic.get("disclosureIndex") or basic.get("disclosureId")
            
            if not disc_idx:
                return None

            stock_codes_raw = str(basic.get("stockCodes") or basic.get("stockCode") or "GENEL").strip()
            # Birincil hisse kodu
            primary_stock = stock_codes_raw.split(",")[0].strip().upper() if stock_codes_raw else "GENEL"

            title = str(basic.get("subject") or basic.get("title") or "KAP Bildirimi").strip()
            subject = str(basic.get("subject") or "").strip()
            company_name = str(basic.get("kapTitle") or basic.get("companyTitle") or "").strip()
            publish_date = str(basic.get("publishDate") or "").strip()
            summary = str(basic.get("summary") or "").strip()

            disc_class = str(basic.get("disclosureClass") or self.disclosure_class).strip().upper()
            disc_type = str(basic.get("disclosureType") or "").strip()
            disc_cat = str(basic.get("disclosureCategory") or "").strip()

            link = f"https://www.kap.org.tr/tr/Bildirim/{disc_idx}"

            return KapNotification(
                id=str(disc_idx),
                disclosure_index=int(disc_idx) if str(disc_idx).isdigit() else None,
                stock_code=primary_stock,
                stock_codes=stock_codes_raw,
                company_name=company_name,
                title=title,
                subject=subject,
                disclosure_class=disc_class,
                disclosure_type=disc_type,
                disclosure_category=disc_cat,
                publish_date=publish_date,
                summary=summary,
                raw_content=json.dumps(item, ensure_ascii=False),
                link=link,
                is_processed=False,
            )
        except Exception as map_err:
            logger.debug(f"KAP verisi eşlenirken hata: {map_err}")
            return None

    def fetch_daily_disclosures_sync(
        self, query_date: Optional[date] = None
    ) -> List[KapNotification]:
        """
        KAP'tan belirtilen tarihin tüm bildirimlerini tek bir POST isteği ile çeker.
        """
        if self.rate_limiter.is_in_cooldown():
            logger.warning(
                f"[KAP][RATE_LIMIT] Güvenlik duvarı soğuma süresinde. "
                f"Kalan süre: {int(self.rate_limiter.remaining_cooldown())} saniye."
            )
            return []

        target_date = query_date or datetime.today().date()
        date_str_dmy = target_date.strftime("%d.%m.%Y")
        date_str_iso = target_date.strftime("%Y-%m-%d")

        url = "https://www.kap.org.tr/tr/api/disclosure/members/byCriteria"
        payload = {
            "fromDate": date_str_iso,
            "toDate": date_str_iso,
            "disclosureClass": self.disclosure_class,
            "subjectList": [],
            "mkkMemberOidList": [],
            "inactiveMkkMemberOidList": [],
            "bdkMemberOidList": [],
            "fromSrc": False,
            "disclosureIndexList": [],
        }

        try:
            response = requests.post(url, json=payload, headers=self.headers, timeout=25)
            
            if response.status_code == 429:
                self.rate_limiter.record_rate_limit()
                return []

            if response.status_code != 200:
                logger.warning(f"KAP API HTTP {response.status_code} yanıtı verdi: {response.text[:150]}")
                return []

            self.rate_limiter.record_success()
            data = response.json()
            
            notifications: List[KapNotification] = []
            for item in data:
                notif = self._map_oda_item(item)
                if notif:
                    # Eğer takip listesi filtresi varsa uygula
                    if self.watchlist and "ALL" not in self.watchlist:
                        # stock_codes içinde watchlist hisselerinden biri var mı
                        matched = any(tick in notif.stock_codes for tick in self.watchlist)
                        if not matched and notif.stock_code not in self.watchlist:
                            continue
                    notifications.append(notif)

            logger.info(f"KAP {self.disclosure_class} taraması başarılı: {len(notifications)} bildirim alındı.")
            return notifications

        except requests.RequestException as req_err:
            logger.warning(f"KAP bağlantı hatası: {req_err}")
            return []

    async def fetch_latest(
        self, stop_event: Optional[asyncio.Event] = None
    ) -> List[KapNotification]:
        """
        Asenkron servis döngüsü için bildirimleri çeker.
        """
        if stop_event and stop_event.is_set():
            return []

        return await asyncio.to_thread(self.fetch_daily_disclosures_sync)
