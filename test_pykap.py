import traceback
import sys
from datetime import datetime, timedelta

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

def test_pykap():
    print("=" * 60)
    print("TEST: pykap Kütüphanesi Testi Başlatılıyor")
    print("=" * 60)
    
    # 1. Import Testi
    try:
        import pykap
        from pykap import BISTCompany, get_bist_companies
        print("✅ [1/4] pykap başarıyla import edildi.")
    except Exception as e:
        print(f"❌ [1/4] pykap import hatası: {e}")
        traceback.print_exc()
        return

    # 2. Şirket Listesi Testi
    try:
        print("\n--- BIST Şirket Listesi Çekme Denemesi (get_bist_companies) ---")
        companies = get_bist_companies()
        print(f"✅ [2/4] Şirket listesi alındı: {type(companies)}, Adet: {len(companies) if hasattr(companies, '__len__') else 'N/A'}")
        if hasattr(companies, "head"):
            print("Örnek şirketler:\n", companies.head(3))
        elif isinstance(companies, list) and len(companies) > 0:
            print("Örnek şirketler:", companies[:3])
    except Exception as e:
        print(f"⚠️ [2/4] get_bist_companies çağrısında hata: {e}")
        traceback.print_exc()

    # 3. BISTCompany ile Canlı Bildirim / Duyuru Çekme Testi (THYAO & GARAN)
    test_tickers = ["THYAO", "GARAN", "ASELS"]
    today = datetime.today()
    from_date = (today - timedelta(days=30)).strftime("%Y-%m-%d")
    to_date = today.strftime("%Y-%m-%d")

    for ticker in test_tickers:
        print(f"\n--- {ticker} için pykap.BISTCompany Testi (Tarih: {from_date} -> {to_date}) ---")
        try:
            comp = BISTCompany(ticker=ticker)
            print(f"BISTCompany('{ticker}') nesnesi oluşturuldu: {comp}")
            
            # 1. get_disclosures (Özel Durum Açıklamaları - ODA, Finansal Rapor - FR)
            for dtype in ["ODA", "FR", "FAR", "DG"]:
                print(f"-> {ticker}.get_disclosures(disclosure_type='{dtype}') çağrılıyor...")
                try:
                    disc_list = comp.get_disclosures(disclosure_type=dtype)
                    print(f"  ✅ Dönen adet ({dtype}): {len(disc_list) if disc_list else 0}")
                    if disc_list and len(disc_list) > 0:
                        print(f"  Örnek [{dtype}]:", disc_list[0])
                except Exception as e:
                    print(f"  ❌ {dtype} çekme hatası: {e}")

            # 2. get_historical_disclosure_list
            print(f"-> {ticker}.get_historical_disclosure_list() çağrılıyor...")
            try:
                hist = comp.get_historical_disclosure_list(fromdate=today.date() - timedelta(days=60), todate=today.date())
                print(f"  ✅ Tarihsel liste döndü: {len(hist) if hist else 0} adet")
                if hist and len(hist) > 0:
                    print("  Örnek tarihsel kayıt:", hist[0])
            except Exception as e:
                print(f"  ❌ get_historical_disclosure_list hatası: {e}")

        except Exception as e:
            print(f"❌ {ticker} bildirim çekme hatası: {type(e).__name__}: {e}")
            print("--- TAM STACK TRACE ---")
            traceback.print_exc()

        # get_expected_disclosure_list denemesi
        try:
            print(f"-> {ticker}.get_expected_disclosure_list() çağrılıyor...")
            expected = comp.get_expected_disclosure_list()
            print(f"Beklenen bildirimler: {expected}")
        except Exception as e:
            print(f"get_expected_disclosure_list hatası: {e}")

if __name__ == "__main__":
    test_pykap()
