import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
import requests

# Proje kök dizinini sys.path'e ekle
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Windows konsol UTF-8 ayarı
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from ingestion.models import KapNotification
from storage.db import DatabaseManager

db = DatabaseManager()

TARGET_TICKERS = {
    "THYAO", "GARAN", "ASELS", "EREGL", "BIMAS",
    "KCHOL", "SISE", "AKBNK", "TUPRS", "FROTO",
    "SAHOL", "ISCTR", "YKBNK", "PGSUS", "PETKM",
    "TCELL", "ENKAI", "EKGYO", "TOASO", "ARCLK"
}

# 2016 - 2023 arası farklı dönem pencereleri
WINDOWS = [
    ("2016-04-01", "2016-04-30"),
    ("2017-05-01", "2017-05-31"),
    ("2018-08-01", "2018-08-31"),
    ("2019-10-01", "2019-10-31"),
    ("2020-04-01", "2020-04-30"),
    ("2021-03-01", "2021-03-31"),
    ("2022-06-01", "2022-06-30"),
    ("2023-05-01", "2023-05-31"),
]


def fetch_and_populate_oda():
    url = "https://www.kap.org.tr/tr/api/disclosure/members/byCriteria"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Referer": "https://www.kap.org.tr/tr/bildirim-sorgu",
        "Origin": "https://www.kap.org.tr",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
    }

    all_notifications: List[KapNotification] = []
    print("=" * 80)
    print("📥 KAP'tan 2016-2023 Yılları Arası Gerçek ÖDA Bildirimleri Toplanıyor...")
    print("=" * 80)

    for from_d, to_d in WINDOWS:
        print(f"-> Tarih Aralığı: {from_d} ile {to_d} taranıyor...")
        payload = {
            "fromDate": from_d,
            "toDate": to_d,
            "disclosureClass": "ODA",
            "subjectList": [],
            "mkkMemberOidList": [],
            "inactiveMkkMemberOidList": [],
            "bdkMemberOidList": [],
            "fromSrc": False,
            "disclosureIndexList": [],
        }

        try:
            r = requests.post(url, json=payload, headers=headers, timeout=30)
            if r.status_code == 200:
                items = r.json()
                valid_in_window = 0
                for item in items:
                    stock_raw = str(item.get("stockCodes") or "").strip().upper()
                    summary = str(item.get("summary") or "").strip()
                    disc_idx = item.get("disclosureIndex")

                    # BIST hedef hisselerimizden biri mi ve summary dolu mu?
                    matched = any(t in stock_raw for t in TARGET_TICKERS)
                    if matched and disc_idx and len(summary) >= 15:
                        primary_stock = stock_raw.split(",")[0].strip()
                        if primary_stock in TARGET_TICKERS:
                            notif = KapNotification(
                                id=f"ODA-{disc_idx}",
                                disclosure_index=disc_idx,
                                stock_code=primary_stock,
                                stock_codes=stock_raw,
                                company_name=str(item.get("kapTitle") or ""),
                                title=str(item.get("subject") or "Özel Durum Açıklaması"),
                                subject=str(item.get("subject") or ""),
                                disclosure_class="ODA",
                                disclosure_type=str(item.get("disclosureType") or ""),
                                publish_date=str(item.get("publishDate") or ""),
                                summary=summary,
                                raw_content=json.dumps(item, ensure_ascii=False),
                                link=f"https://www.kap.org.tr/tr/Bildirim/{disc_idx}",
                                is_processed=False,
                            )
                            all_notifications.append(notif)
                            valid_in_window += 1

                print(f"   ✅ Bu pencereden {valid_in_window} adet kaliteli ÖDA bildirimi alındı.")
            elif r.status_code == 429:
                print(f"   ⚠️ Rate limit alındı, 10s bekleniyor...")
                time.sleep(10)
            else:
                print(f"   ⚠️ HTTP {r.status_code}: {r.text[:100]}")

            # Nazik bekleme
            time.sleep(1.0)

        except Exception as e:
            print(f"   ❌ İstek hatası: {e}")

    # Veritabanına kaydet
    print(f"\nToplam Toplanan Kaliteli ÖDA Bildirimi: {len(all_notifications)}")
    inserted, total = db.save_notifications_batch(all_notifications)
    print(f"✅ {inserted} adet YENİ ÖDA bildirimi veritabanına kaydedildi.")

    # Veritabanı toplam ÖDA durumu
    with db.get_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM kap_notifications WHERE disclosure_class = 'ODA';")
        oda_total = c.fetchone()[0]
        print(f"📊 Veritabanındaki Toplam ÖDA Bildirimi Sayısı: {oda_total}")


if __name__ == "__main__":
    fetch_and_populate_oda()
