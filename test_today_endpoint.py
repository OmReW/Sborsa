import sys
import json
import requests
from datetime import datetime

# Windows konsol UTF-8 ayarı
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

def test_kap_daily_endpoint():
    url = "https://www.kap.org.tr/tr/api/disclosure/list/main"
    today_str = datetime.today().strftime("%d.%m.%Y")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Referer": "https://www.kap.org.tr/tr/bildirim-sorgu",
        "Origin": "https://www.kap.org.tr",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
    }
    
    payload = {
        "fromDate": today_str,
        "toDate": today_str,
        "fundTypes": [],
        "memberTypes": ["IGS"],  # BIST İşlem Gören Şirketler
    }

    print(f"URL     : {url}")
    print(f"Tarih   : {today_str}")
    print(f"Payload : {json.dumps(payload)}")
    print("İstek gönderiliyor...")

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=20)
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Başarılı! Toplam Dönen Bildirim Sayısı: {len(data)}")
            if len(data) > 0:
                print("\n--- ÖRNEK İLK 3 HAM BİLDİRİM (JSON) ---")
                print(json.dumps(data[:3], indent=2, ensure_ascii=False))
            else:
                print("ℹ️ Bugün için henüz bildirim dönmedi (Piyasa kapalı veya tatil günü olabilir).")
        else:
            print(f"❌ Hata Kodu: {response.status_code}")
            print(f"Response Body: {response.text[:500]}")

    except Exception as e:
        print(f"❌ İstek Hatası: {e}")

if __name__ == "__main__":
    test_kap_daily_endpoint()
