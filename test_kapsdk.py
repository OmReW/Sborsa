import asyncio
import traceback
import sys
from datetime import datetime, timedelta

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

async def test_kapsdk():
    print("=" * 60)
    print("TEST: kap-sdk (kap-tr-sdk) Asenkron Kütüphane Testi")
    print("=" * 60)

    # 1. Import Testi
    try:
        import kap_sdk
        from kap_sdk.kap_client import KapClient
        print("✅ [1/4] kap-sdk başarıyla import edildi.")
    except Exception as e:
        print(f"❌ [1/4] kap-sdk import hatası: {e}")
        traceback.print_exc()
        return

    # 2. KapClient Başlatma Testi
    try:
        client = KapClient()
        print(f"✅ [2/4] KapClient başarıyla başlatıldı: {client}")
    except Exception as e:
        print(f"❌ [2/4] KapClient başlatma hatası: {e}")
        traceback.print_exc()
        return

    # 3. Şirket Listesi Çekme Testi (get_companies)
    try:
        print("\n--- await get_companies() Testi ---")
        companies = await client.get_companies()
        print(f"✅ Şirket listesi alındı! Toplam adet: {len(companies) if companies else 0}")
        if companies and len(companies) > 0:
            print("Örnek ilk şirket:", companies[0])
            thyao = next((c for c in companies if getattr(c, 'code', None) == 'THYAO'), None)
            print("Bulunan THYAO:", thyao)
    except Exception as e:
        print(f"⚠️ get_companies hatası: {e}")
        traceback.print_exc()

    # 4. Canlı Bildirimleri Çekme Testi (get_announcements) - Tüm KAP Akışı
    try:
        today = datetime.today().date()
        from_date = today - timedelta(days=2)
        print(f"\n--- await get_announcements(fromdate={from_date}, todate={today}) Testi ---")
        print(f"-> Son 48 saatteki TÜM KAP BİLDİRİMLERİ çekiliyor...")
        
        announcements = await client.get_announcements(fromdate=from_date, todate=today)
        print(f"✅ [3/4] Canlı Bildirimler Başarıyla Döndü! Toplam adet: {len(announcements) if announcements else 0}")

        if announcements and len(announcements) > 0:
            print("\n--- ÖRNEK HAM VERİ (İlk 3 Kayıt) ---")
            for i, item in enumerate(announcements[:3], 1):
                basic = item.disclosureBasic if hasattr(item, 'disclosureBasic') else None
                detail = item.disclosureDetail if hasattr(item, 'disclosureDetail') else None
                
                print(f"\n[Kayıt #{i}]")
                if basic:
                    print(f"  ID             : {getattr(basic, 'disclosureId', 'N/A')}")
                    print(f"  Index          : {getattr(basic, 'disclosureIndex', 'N/A')}")
                    print(f"  Hisse Kodu     : {getattr(basic, 'stockCode', 'N/A')}")
                    print(f"  İlişkili Hisse : {getattr(basic, 'relatedStocks', 'N/A')}")
                    print(f"  Şirket Unvanı  : {getattr(basic, 'companyTitle', 'N/A')}")
                    print(f"  Başlık / Konu  : {getattr(basic, 'title', 'N/A')}")
                    print(f"  Yayın Tarihi   : {getattr(basic, 'publishDate', 'N/A')}")
                    print(f"  Özet           : {getattr(basic, 'summary', 'N/A')}")
                    print(f"  Kategori       : {getattr(basic, 'disclosureCategory', 'N/A')} / {getattr(basic, 'disclosureClass', 'N/A')}")
                else:
                    print(f"  Ham Veri: {item}")
        else:
            print("⚠️ Bildirim listesi boş döndü.")

    except Exception as e:
        print(f"❌ get_announcements hatası: {type(e).__name__}: {e}")
        print("--- TAM STACK TRACE ---")
        traceback.print_exc()

    # 5. Belirli Bir Şirket İçin Bildirim Çekme Testi (THYAO)
    try:
        print("\n--- Belirli Şirket İçin await get_announcements(company=THYAO) Testi ---")
        thyao_comp = await client.get_company('THYAO')
        print(f"get_company('THYAO') sonucu: {thyao_comp}")
        if thyao_comp:
            thyao_announcements = await client.get_announcements(
                company=thyao_comp, 
                fromdate=today - timedelta(days=30), 
                todate=today
            )
            print(f"✅ THYAO son 30 gün bildirim sayısı: {len(thyao_announcements) if thyao_announcements else 0}")
            if thyao_announcements and len(thyao_announcements) > 0:
                sample = thyao_announcements[0].disclosureBasic
                print(f"Örnek THYAO Bildirimi: {sample.publishDate} | [{sample.stockCode}] {sample.title} - {sample.summary}")
    except Exception as e:
        print(f"⚠️ Şirket bazlı bildirim çekme hatası: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_kapsdk())
