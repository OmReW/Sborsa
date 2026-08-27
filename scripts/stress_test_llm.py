import asyncio
import json
import sys
from pathlib import Path
import httpx

# Proje kök dizinini sys.path'e ekle
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Windows konsol UTF-8 ayarı
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from config.settings import settings
from ingestion.models import KapNotification
from ingestion.analyzer import KAPAnalyzer


async def query_ollama_raw(analyzer: KAPAnalyzer, notif: KapNotification) -> str:
    prompt = analyzer._build_prompt(notif)
    payload = {
        "model": analyzer.model_name,
        "prompt": prompt,
        "stream": False,
        "format": "json",
    }
    api_url = f"{analyzer.base_url}/api/generate"
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(api_url, json=payload)
        res_json = response.json()
        return res_json.get("response", "")


async def run_stress_tests():
    analyzer = KAPAnalyzer()

    # =========================================================================
    # TEST 1: ÇELİŞKİLİ SENARYO (Gelir Artışı + Yüksek Borçlanma/Kur Zararı)
    # =========================================================================
    print("=" * 80)
    print("TEST 1: ÇELİŞKİLİ SENARYO (GELİR ARTIŞI + KUR VE BORÇLANMA ZARARI)")
    print("=" * 80)
    
    t1_notif = KapNotification(
        id="STRESS-T1",
        stock_code="SISE",
        title="2026 Yılı 6 Aylık Finansal Sonuçlar ve Değerlendirme",
        publish_date="2026-08-26 18:30:00",
        summary="Şirketimizin 2026 ilk yarıyıl satış gelirleri bir önceki yılın aynı dönemine göre %65 artışla 45 Milyar TL'ye ulaşmıştır. Ancak döviz kurlarındaki dalgalanma kaynaklı net finansman giderleri ve artan kısa vadeli borçlanma faiz yükü sebebiyle dönem net kârı %70 azalarak 1.2 Milyar TL olarak gerçekleşmiştir.",
    )
    print("GÖNDERİLEN GİRDİ:")
    print(f"Şirket: {t1_notif.stock_code}")
    print(f"Başlık: {t1_notif.title}")
    print(f"Özet  : {t1_notif.summary}")
    print("\nHAM MODEL ÇIKTISI:")
    t1_raw = await query_ollama_raw(analyzer, t1_notif)
    print(t1_raw)
    print()

    # =========================================================================
    # TEST 2: NÖTR / PROSEDÜREL SENARYOLAR (Rutin İdari Bildirimler)
    # =========================================================================
    print("=" * 80)
    print("TEST 2: NÖTR / PROSEDÜREL SENARYOLAR (3 FARKLI RUTİN BİLDİRİM)")
    print("=" * 80)

    t2_cases = [
        KapNotification(
            id="STRESS-T2-1",
            stock_code="AKBNK",
            title="Olağan Genel Kurul Toplantısına Davet ve Bilgilendirme Dokümanı",
            publish_date="2026-08-26 14:00:00",
            summary="Bankamızın 2025 yılı faaliyet dönemine ilişkin Olağan Genel Kurul Toplantısı 25 Eylül 2026 tarihinde Genel Müdürlük adresinde yapılacaktır.",
        ),
        KapNotification(
            id="STRESS-T2-2",
            stock_code="KCHOL",
            title="İmza Sirküleri ve Yetki Dağılımı Güncellemesi",
            publish_date="2026-08-26 15:30:00",
            summary="Şirketimiz Finans Direktörlüğü bünyesinde görev değişimi nedeniyle C grubu imza yetkilisinin yetkisi iptal edilmiş, yerine yeni atanan müdüre aynı grup yetki verilmiştir.",
        ),
        KapNotification(
            id="STRESS-T2-3",
            stock_code="TCELL",
            title="Bağımsız Yönetim Kurulu Üyeliği Aday Listesi",
            publish_date="2026-08-26 16:45:00",
            summary="Kurumsal Yönetim Komitesi'nin değerlendirmesi sonucunda Genel Kurul onayına sunulacak Bağımsız Yönetim Kurulu Üye Aday Listesi belirlenmiştir.",
        ),
    ]

    for idx, c in enumerate(t2_cases, 1):
        print(f"\n--- TEST 2.{idx}: {c.stock_code} - {c.title} ---")
        print(f"Özet: {c.summary}")
        print("HAM MODEL ÇIKTISI:")
        raw_out = await query_ollama_raw(analyzer, c)
        print(raw_out)

    # =========================================================================
    # TEST 3: EKSİK / BELİRSİZ VERİ SENARYOSU (Neredeyse Sıfır Bilgi)
    # =========================================================================
    print("\n" + "=" * 80)
    print("TEST 3: EKSİK / BELİRSİZ VERİ SENARYOSU")
    print("=" * 80)

    t3_cases = [
        KapNotification(
            id="STRESS-T3-1",
            stock_code="PETKM",
            title="Finansal Rapor",
            publish_date="2026-08-26 17:00:00",
            summary="",
        ),
        KapNotification(
            id="STRESS-T3-2",
            stock_code="BIMAS",
            title="Düzeltme Bildirimi",
            publish_date="2026-08-26 17:15:00",
            summary="Maddi hata düzeltmesi.",
        ),
    ]

    for idx, c in enumerate(t3_cases, 1):
        print(f"\n--- TEST 3.{idx}: {c.stock_code} - {c.title} ---")
        print(f"Özet: '{c.summary}'")
        print("HAM MODEL ÇIKTISI:")
        raw_out = await query_ollama_raw(analyzer, c)
        print(raw_out)

    # =========================================================================
    # TEST 4: TUTARLILIK / DETERMINIZM TESTİ (Aynı Bildirim 3 Kez Art Arda)
    # =========================================================================
    print("\n" + "=" * 80)
    print("TEST 4: TUTARLILIK TESTİ (AYNI BİLDİRİM 3 KEZ ART ARDA)")
    print("=" * 80)

    t4_notif = KapNotification(
        id="STRESS-T4",
        stock_code="FROTO",
        title="Yeni Elektrikli Ticari Araç Yatırımı ve Teşvik Kararı",
        publish_date="2026-08-26 11:00:00",
        summary="Şirketimiz Kocaeli fabrikasında 500 Milyon Euro tutarında yeni nesil elektrikli araç üretim hattı yatırımı kararı almış olup proje bazlı devlet yatırım teşvik belgesi onaylanmıştır.",
    )
    print("GÖNDERİLEN GİRDİ:")
    print(f"Şirket: {t4_notif.stock_code}")
    print(f"Başlık: {t4_notif.title}")
    print(f"Özet  : {t4_notif.summary}")

    for run_idx in range(1, 4):
        print(f"\n--- ÇALIŞTIRMA #{run_idx} ---")
        raw_out = await query_ollama_raw(analyzer, t4_notif)
        print(raw_out)

    print("\n" + "=" * 80)
    print("TESTLER TAMAMLANDI")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_stress_tests())
