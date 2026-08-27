import asyncio
import json
import re
import sys
from pathlib import Path
import requests

# Proje kök dizinini sys.path'e ekle
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Windows konsol UTF-8 ayarı
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from ingestion.models import KapNotification
from ingestion.analyzer import KAPAnalyzer


def search_real_negative_odas():
    url = "https://www.kap.org.tr/tr/api/disclosure/members/byCriteria"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.kap.org.tr/tr/bildirim-sorgu",
        "Origin": "https://www.kap.org.tr",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
    }

    # Farklı dönemlerden (2020 pandemi üretim duruşları, 2018 kur şoku, 2023) geniş tarama
    search_windows = [
        ("2020-03-15", "2020-04-15"),  # Pandemi üretim duruşları ve kriz açıklamaları
        ("2018-08-01", "2018-08-31"),  # 2018 kur şoku / kredi notu / borç yapılandırma
        ("2023-02-06", "2023-02-28"),  # Deprem ve operasyonel duruşlar
    ]

    negative_keywords = [
        "durdur", "ara verme", "duruş", "dava", "iptal", "fesih", 
        "not indir", "düşür", "ceza", "haciz", "olumsuz", "zarar", "gecikme"
    ]

    all_negative = []

    for from_d, to_d in search_windows:
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
                for it in items:
                    summary = (it.get("summary") or "").lower()
                    subject = (it.get("subject") or "").lower()
                    text = f"{subject} {summary}"

                    if any(kw in text for kw in negative_keywords):
                        stock = it.get("stockCodes") or "GENEL"
                        if stock and len(stock) <= 10 and it.get("summary") and len(it.get("summary", "").strip()) > 20:
                            all_negative.append(it)
        except Exception as e:
            print(f"Tarama hatası ({from_d} - {to_d}): {e}")

    return all_negative


async def run_negative_test():
    print("KAP'tan gerçek olumsuz nitelikli ÖDA bildirimleri taranıyor...")
    negatives = search_real_negative_odas()
    print(f"Bulunan Olumsuz Nitelikli Bildirim Sayısı: {len(negatives)}\n")

    # 5 Tane net, farklı şirketlerden olumsuz olay seçelim
    selected_5 = []
    seen_stocks = set()
    for item in negatives:
        st = item.get("stockCodes")
        if st not in seen_stocks:
            selected_5.append(item)
            seen_stocks.add(st)
        if len(selected_5) >= 5:
            break

    analyzer = KAPAnalyzer()
    analyzed_results = []

    for notif_data in selected_5:
        disc_idx = notif_data.get("disclosureIndex")
        stock = notif_data.get("stockCodes")
        title = notif_data.get("subject") or "Özel Durum Açıklaması"
        summary = notif_data.get("summary") or ""
        pub_date = notif_data.get("publishDate")
        company = notif_data.get("kapTitle")

        notif = KapNotification(
            id=f"NEG-{disc_idx}",
            disclosure_index=disc_idx,
            stock_code=stock,
            stock_codes=stock,
            company_name=company,
            title=title,
            subject=title,
            publish_date=pub_date,
            summary=summary,
            link=f"https://www.kap.org.tr/tr/Bildirim/{disc_idx}",
            is_processed=False,
        )

        res = await analyzer.analyze_notification(notif)
        if res:
            analyzed_results.append({
                "stock_code": stock,
                "company_name": company,
                "publish_date": pub_date,
                "title": title,
                "summary": summary,
                "disclosure_index": disc_idx,
                "recommendation": res["recommendation"],
                "confidence": res["confidence"],
                "reasoning": res["reasoning"],
            })

    print("=" * 95)
    print("GERÇEK 5 OLUMSUZ ÖDA BİLDİRİMİ İÇİN YEREL LLM ANALİZ VE ÖNERİ SONUÇLARI (HAM ÇIKTI)")
    print("=" * 95)

    for i, res in enumerate(analyzed_results, 1):
        print(f"\n--- [KAYIT #{i}] {res['stock_code']} ({res['publish_date']}) ---")
        print(f"Şirket     : {res['company_name']}")
        print(f"Başlık     : {res['title']}")
        print(f"Özet       : {res['summary']}")
        print(f"KAP Linki  : https://www.kap.org.tr/tr/Bildirim/{res['disclosure_index']}")
        print(f"Öneri      : {res['recommendation']}")
        print(f"Güven      : {res['confidence']}/5")
        print(f"Gerekçe    : {res['reasoning']}")

    recs = [r["recommendation"] for r in analyzed_results]
    print("\n" + "=" * 95)
    print("📊 ÖNERİ DAĞILIMI:")
    print(f"- Toplam İncelenen: {len(analyzed_results)}")
    print(f"- AL   : {recs.count('AL')} adet")
    print(f"- SAT  : {recs.count('SAT')} adet")
    print(f"- NÖTR : {recs.count('NÖTR')} adet")
    print("=" * 95)


if __name__ == "__main__":
    asyncio.run(run_negative_test())
