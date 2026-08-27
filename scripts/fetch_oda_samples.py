import json
import sys
from pathlib import Path
import requests

# Windows konsol UTF-8 ayarı
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def fetch_real_oda_disclosures():
    url = "https://www.kap.org.tr/tr/api/disclosure/members/byCriteria"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Referer": "https://www.kap.org.tr/tr/bildirim-sorgu",
        "Origin": "https://www.kap.org.tr",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
    }

    # BIST 30 şirketlerinin 2017 yılındaki Özel Durum Açıklamaları (ODA)
    payload = {
        "fromDate": "2017-05-01",
        "toDate": "2017-05-31",
        "disclosureClass": "ODA",  # Özel Durum Açıklamaları
        "subjectList": [],
        "mkkMemberOidList": [],
        "inactiveMkkMemberOidList": [],
        "bdkMemberOidList": [],
        "fromSrc": False,
        "disclosureIndexList": [],
    }

    print("KAP 'byCriteria' endpoint'ine ODA (Özel Durum Açıklaması) sorgusu gönderiliyor...")
    response = requests.post(url, json=payload, headers=headers, timeout=30)
    print(f"HTTP Status Code: {response.status_code}")

    if response.status_code != 200:
        print(f"Hata: {response.text[:300]}")
        return

    data = response.json()
    print(f"Toplam Çekilen ODA Bildirim Sayısı: {len(data)}\n")

    # BIST 30 hisselerine ait ve summary alanı dolu (haber niteliğindeki) örnekleri filtrele
    bist_tickers = {"THYAO", "GARAN", "ASELS", "EREGL", "BIMAS", "SISE", "KCHOL", "FROTO", "TUPRS", "PETKM", "TCELL", "AKBNK", "SAHOL"}
    rich_odas = [
        d for d in data 
        if d.get("stockCodes") in bist_tickers and d.get("summary") and len(d.get("summary", "").strip()) > 15
    ]

    print(f"Filtrelenmiş BIST 30 Metin İçeren ÖDA Bildirim Sayısı: {len(rich_odas)}")
    print("=" * 90)
    print("GERÇEK, METİN İÇEREN ÖDA (ÖZEL DURUM AÇIKLAMASI) BİLDİRİM ÖRNEKLERİ (HAM ÇIKTI)")
    print("=" * 90)

    for i, item in enumerate(rich_odas[:8], 1):
        print(f"\n--- ÖRNEK #{i} | Hisse: {item.get('stockCodes')} | Tarih: {item.get('publishDate')} ---")
        print(f"KAP Şirket Unvanı : {item.get('kapTitle')}")
        print(f"Bildirim Konusu   : {item.get('subject')}")
        print(f"Özet / Açıklama   : {item.get('summary')}")
        print(f"Bildirim İndeksi  : {item.get('disclosureIndex')}")
        print(f"KAP Linki         : https://www.kap.org.tr/tr/Bildirim/{item.get('disclosureIndex')}")
        print(f"Ham JSON (Kırpmadan):\n{json.dumps(item, indent=2, ensure_ascii=False)}")


if __name__ == "__main__":
    fetch_real_oda_disclosures()
