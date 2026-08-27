import sys
import traceback
from datetime import datetime, timedelta
import pandas as pd
import yfinance as yf

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

def test_chart_fetch(stock_code: str, from_date_raw: str):
    print("=" * 80)
    print(f"🔍 Teşhis Başlatılıyor: Hisse={stock_code}, Ham Tarih='{from_date_raw}'")
    print("=" * 80)

    clean_ticker = stock_code.split(",")[0].strip().upper()
    yf_symbol = f"{clean_ticker}.IS"
    print(f"1. Ticker Sembolü: {yf_symbol}")

    # Tarih ayrıştırma
    base_dt = None
    date_part = from_date_raw.strip().split()[0] if from_date_raw else ""
    print(f"2. Ayrıştırılacak Tarih Parçası: '{date_part}'")

    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%Y/%m/%d", "%d/%m/%Y"):
        try:
            base_dt = datetime.strptime(date_part, fmt)
            print(f"   ✓ Başarılı Format: '{fmt}' -> {base_dt.strftime('%Y-%m-%d')}")
            break
        except ValueError as ve:
            print(f"   ✗ '{fmt}' Hatası: {ve}")

    if not base_dt:
        print("   ⚠️ Hiçbir format uymadı! datetime.now() fallback'i yapılıyor...")
        base_dt = datetime.now()

    start_d = base_dt - timedelta(days=10)
    end_d = base_dt + timedelta(days=25)
    print(f"3. yfinance Sorgu Penceresi: Start='{start_d.strftime('%Y-%m-%d')}', End='{end_d.strftime('%Y-%m-%d')}'")

    print("4. yfinance İsteği Atılıyor...")
    df = yf.download(
        yf_symbol,
        start=start_d.strftime("%Y-%m-%d"),
        end=end_d.strftime("%Y-%m-%d"),
        progress=False,
    )

    print(f"5. Gelen DataFrame Boyutu: {df.shape}")
    if df.empty:
        print("   ❌ DataFrame BOŞ döndü!")
    else:
        print(f"   ✓ {len(df)} adet işlem günü fiyatı başarıyla alındı.")
        print(f"   İlk Tarih: {df.index[0].strftime('%Y-%m-%d')}, Son Tarih: {df.index[-1].strftime('%Y-%m-%d')}")
        print("   Fiyat Örneği:")
        print(df.tail(3))

if __name__ == "__main__":
    # Test 1: DD.MM.YYYY formatında gelen tarih (Örn. 26.05.2023)
    test_chart_fetch("EKGYO", "26.05.2023 19:20:30")
    print("\n")
    # Test 2: YYYY-MM-DD formatında gelen tarih (Örn. 2023-05-26)
    test_chart_fetch("EKGYO", "2023-05-26")
