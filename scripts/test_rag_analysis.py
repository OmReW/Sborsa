import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import asyncio
from ingestion.models import KapNotification
from ingestion.analyzer import KAPAnalyzer
from ingestion.analyzer_v2_rag import KAPAnalyzerV2RAG

test_notifications = [
    # 1. Makro / Seçim Odaklı
    KapNotification(
        id="TEST-RAG-1",
        stock_code="EKGYO",
        company_name="Emlak Konut Gayrimenkul Yatırım Ortaklığı A.Ş.",
        title="Seçim Sonrası Yeni Kentsel Dönüşüm ve Kamu Konut Projeleri İhalesi",
        summary="Şirketimiz, yerel seçimlerin ardından Çevre ve Şehircilik Bakanlığı koordinasyonunda başlatılan 15.000 konutluk kentsel dönüşüm projesinde toplam 12.4 Milyar TL bedelli ana yüklenicilik sözleşmesini imzalamıştır.",
        publish_date="2026-08-27 10:30:00",
        disclosure_index=901,
        disclosure_class="ODA",
    ),
    # 2. Faiz / Para Politikası & Bankacılık
    KapNotification(
        id="TEST-RAG-2",
        stock_code="GARAN",
        company_name="Türkiye Garanti Bankası A.Ş.",
        title="TCMB Para Politikası Kararları ve Net Faiz Marjı Güncellemesi",
        summary="TCMB'nin politika faizi ve makroihtiyati sıkılaşma adımları doğrultusunda kredi-mevduat makasında toparlanma gerçekleşmiş, bankamızın yıl sonu net faiz marjı beklentisi 80 baz puan yukarı yönlü revize edilmiştir.",
        publish_date="2026-08-27 11:00:00",
        disclosure_index=902,
        disclosure_class="ODA",
    ),
    # 3. Şirket Özel / İhale & Yeni İş Sözleşmesi (Makrodan bağımsız)
    KapNotification(
        id="TEST-RAG-3",
        stock_code="ASELS",
        company_name="Aselsan Elektronik Sanayi ve Ticaret A.Ş.",
        title="Savunma Sanayii Başkanlığı ile Yeni İş Sözleşmesi İmzalanması",
        summary="Şirketimiz ile Savunma Sanayii Başkanlığı arasında radar ve elektro-optik sistem tedariki kapsamında 85 Milyon USD ve 1.2 Milyar TL tutarında yeni bir yurt içi satış sözleşmesi imzalanmıştır. Teslimatlar 2026-2027 yıllarında tamamlanacaktır.",
        publish_date="2026-08-27 11:15:00",
        disclosure_index=903,
        disclosure_class="ODA",
    ),
    # 4. Çelişkili / Risk & Üretim Duruşu
    KapNotification(
        id="TEST-RAG-4",
        stock_code="PETKM",
        company_name="Petkim Petrokimya Holding A.Ş.",
        title="Etilen Tesisinde Planlı Olmayan Arıza ve Üretim Kısıtlaması",
        summary="Etilen fabrikamızda meydana gelen teknik arıza nedeniyle üretime 21 gün süreyle ara verilmiştir. Söz konusu duruşun ciroya yaklaşık %7.5 negatif etki yapması ve 3. çeyrek kârlılığını baskılaması beklenmektedir.",
        publish_date="2026-08-27 11:30:00",
        disclosure_index=904,
        disclosure_class="ODA",
    ),
    # 5. Rutin / Prosedürel (Genel Kurul)
    KapNotification(
        id="TEST-RAG-5",
        stock_code="THYAO",
        company_name="Türk Hava Yolları A.O.",
        title="Olağan Genel Kurul Toplantısı Çağrısı ve Gündemi",
        summary="Şirketimiz Yönetim Kurulu'nun 27.08.2026 tarihli toplantısında, 2025 yılı faaliyet sonuçlarının görüşüleceği Olağan Genel Kurul Toplantısı'nın 25 Eylül 2026 tarihinde Genel Yönetim Binası'nda yapılmasına karar verilmiştir.",
        publish_date="2026-08-27 11:45:00",
        disclosure_index=905,
        disclosure_class="ODA",
    ),
    # 6. Politika Şoku / Regülasyon & KKM
    KapNotification(
        id="TEST-RAG-6",
        stock_code="ISCTR",
        company_name="Türkiye İş Bankası A.Ş.",
        title="KKM Düzenlemeleri ve TL Mevduata Geçiş Süreci Değerlendirmesi",
        summary="Kur Korumalı Mevduat hesaplarının kademeli olarak azaltılması ve standart TL mevduat payının artırılmasına yönelik regülasyonlar başarıyla yönetilmekte olup, bankamızın TL mevduat payı %62 seviyesine ulaşmıştır. Kısa vadeli mevduat maliyet baskısı sınırlı kalmıştır.",
        publish_date="2026-08-27 12:00:00",
        disclosure_index=906,
        disclosure_class="ODA",
    ),
]


async def run_comparison():
    v1_analyzer = KAPAnalyzer()
    v2_analyzer = KAPAnalyzerV2RAG()

    print("\n" + "=" * 90)
    print("🔬 LLM ANALİZ MOTORU KARŞILAŞTIRMASI: MEVCUT V1 vs. RAG DESTEKLİ V2")
    print("=" * 90)

    for idx, notif in enumerate(test_notifications, 1):
        print(f"\n[{idx}/6] BİLDİRİM: {notif.stock_code} - {notif.title}")
        print(f"📄 İçerik: {notif.summary[:130]}...")

        # 1. V1 Analiz (Senkron Ollama İsteği)
        prompt_v1 = v1_analyzer.build_prompt(notif)
        res_v1_raw = await asyncio.to_thread(
            lambda: v1_analyzer._parse_llm_response(
                import_requests_post(v1_analyzer.base_url, v1_analyzer.model_name, prompt_v1)
            )
        )
        rec_v1 = res_v1_raw.get("recommendation", "NÖTR") if res_v1_raw else "NÖTR"
        conf_v1 = res_v1_raw.get("confidence", "-") if res_v1_raw else "-"
        reason_v1 = res_v1_raw.get("reasoning", "") if res_v1_raw else "Hata"

        # 2. V2 RAG Analiz
        res_v2 = await asyncio.to_thread(lambda: v2_analyzer.analyze_notification_sync(notif))
        rec_v2 = res_v2.get("recommendation", "NÖTR")
        conf_v2 = res_v2.get("confidence", "-")
        reason_v2 = res_v2.get("reasoning", "")
        rag_info = res_v2.get("rag_context", {})

        print("\n" + "-" * 45 + " KARŞILAŞTIRMA " + "-" * 45)
        print(f"🔷 [MEVCUT V1 ANALYZER] -> Öneri: {rec_v1} (Güven: {conf_v1}/5)")
        print(f"   💬 Gerekçe: {reason_v1}")
        print()
        print(f"🔶 [YENİ V2 RAG ANALYZER] -> Öneri: {rec_v2} (Güven: {conf_v2}/5)")
        print(f"   📚 RAG Hafızası: {rag_info.get('matched_category', 'Özel/Şirket İçi')} ({rag_info.get('events_count', 0)} tarihsel olay bağlama eklendi)")
        print(f"   💬 Gerekçe: {reason_v2}")
        print("-" * 90)


def import_requests_post(base_url, model_name, prompt):
    import requests
    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.1, "top_p": 0.9},
    }
    r = requests.post(f"{base_url.rstrip('/')}/api/generate", json=payload, timeout=120)
    return r.json().get("response", "")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    asyncio.run(run_comparison())
