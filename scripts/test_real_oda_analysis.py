import asyncio
import json
import sys
from pathlib import Path

# Proje kök dizinini sys.path'e ekle
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Windows konsol UTF-8 ayarı
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from ingestion.models import KapNotification
from ingestion.analyzer import KAPAnalyzer
from storage.db import DatabaseManager


async def run_real_oda_test():
    db = DatabaseManager()
    analyzer = KAPAnalyzer()

    # 7 Adet Gerçek KAP ÖDA (Özel Durum Açıklaması) Bildirimi
    real_oda_notifications = [
        KapNotification(
            id="ODA-609961",
            disclosure_index=609961,
            stock_code="TCELL",
            stock_codes="TCELL",
            company_name="TURKCELL İLETİŞİM HİZMETLERİ A.Ş.",
            title="Özel Durum Açıklaması (Genel)",
            subject="Özel Durum Açıklaması (Genel)",
            disclosure_class="ODA",
            disclosure_type="ODA",
            publish_date="31.05.2017 14:59:13",
            summary="ABD sermaye piyasası mevzuatı uyarınca, Securities and Exchange Commision'a (SEC) yapılan açıklama",
            link="https://www.kap.org.tr/tr/Bildirim/609961",
            is_processed=False,
        ),
        KapNotification(
            id="ODA-609572",
            disclosure_index=609572,
            stock_code="TCELL",
            stock_codes="TCELL",
            company_name="TURKCELL İLETİŞİM HİZMETLERİ A.Ş.",
            title="Özel Durum Açıklaması (Genel)",
            subject="Özel Durum Açıklaması (Genel)",
            disclosure_class="ODA",
            disclosure_type="ODA",
            publish_date="29.05.2017 15:04:15",
            summary="Swap işlemleri yeniden yapılandırma",
            link="https://www.kap.org.tr/tr/Bildirim/609572",
            is_processed=False,
        ),
        KapNotification(
            id="ODA-609551",
            disclosure_index=609551,
            stock_code="SISE",
            stock_codes="SISE",
            company_name="TÜRKİYE ŞİŞE VE CAM FABRİKALARI A.Ş.",
            title="Sermaye Artırımı - Azaltımı İşlemlerine İlişkin Bildirim",
            subject="Sermaye Artırımı - Azaltımı İşlemlerine İlişkin Bildirim",
            disclosure_class="ODA",
            disclosure_type="CA",
            publish_date="29.05.2017 14:04:54",
            summary="Sermaye Artırımına İlişkin Yönetim Kurulu Kararı",
            link="https://www.kap.org.tr/tr/Bildirim/609551",
            is_processed=False,
        ),
        KapNotification(
            id="ODA-609529",
            disclosure_index=609529,
            stock_code="TCELL",
            stock_codes="TCELL",
            company_name="TURKCELL İLETİŞİM HİZMETLERİ A.Ş.",
            title="Genel Kurul İşlemlerine İlişkin Bildirim",
            subject="Genel Kurul İşlemlerine İlişkin Bildirim",
            disclosure_class="ODA",
            disclosure_type="CA",
            publish_date="29.05.2017 13:06:43",
            summary="Olağan Genel Kurul Toplantısı Sonucu hk.",
            link="https://www.kap.org.tr/tr/Bildirim/609529",
            is_processed=False,
        ),
        KapNotification(
            id="ODA-609520",
            disclosure_index=609520,
            stock_code="AKBNK",
            stock_codes="AKBNK",
            company_name="AKBANK T.A.Ş.",
            title="Pay Dışında Sermaye Piyasası Aracı İşlemlerine İlişkin Bildirim (Faiz İçeren)",
            subject="Pay Dışında Sermaye Piyasası Aracı İşlemlerine İlişkin Bildirim (Faiz İçeren)",
            disclosure_class="ODA",
            disclosure_type="CA",
            publish_date="29.05.2017 11:29:19",
            summary="Nitelikli Yatırımcılara Finansman Bonosu İhracının Tamamlanması Hk.",
            link="https://www.kap.org.tr/tr/Bildirim/609520",
            is_processed=False,
        ),
        KapNotification(
            id="ODA-609473",
            disclosure_index=609473,
            stock_code="KCHOL",
            stock_codes="KCHOL",
            company_name="KOÇ HOLDİNG A.Ş.",
            title="Kredi Derecelendirmesi",
            subject="Kredi Derecelendirmesi",
            disclosure_class="ODA",
            disclosure_type="ODA",
            publish_date="26.05.2017 19:39:30",
            summary="Kredi Derecelendirme Notu",
            link="https://www.kap.org.tr/tr/Bildirim/609473",
            is_processed=False,
        ),
        KapNotification(
            id="ODA-609431",
            disclosure_index=609431,
            stock_code="EREGL",
            stock_codes="EREGL",
            company_name="EREĞLİ DEMİR VE ÇELİK FABRİKALARI T.A.Ş.",
            title="Kurumsal Yönetim İlkelerine Uyum Derecelendirmesi",
            subject="Kurumsal Yönetim İlkelerine Uyum Derecelendirmesi",
            disclosure_class="ODA",
            disclosure_type="ODA",
            publish_date="26.05.2017 18:12:57",
            summary="Kurumsal Yönetim İlkelerine Uyum Derecelendirme Sözleşmesi'nin Yenilenmesi",
            link="https://www.kap.org.tr/tr/Bildirim/609431",
            is_processed=False,
        ),
    ]

    # 1. Bildirimleri kaydet
    for notif in real_oda_notifications:
        db.save_notification(notif)
        # Yeniden analize sokabilmek için is_processed = 0 yap
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE kap_notifications SET is_processed = 0, recommendation = NULL WHERE id = ?;", (notif.id,))

    # 2. LLM Analizini Çalıştır
    analyzed_list = []
    for notif in real_oda_notifications:
        res = await analyzer.analyze_notification(notif)
        if res:
            db.save_analysis_result(
                notification_id=notif.id,
                recommendation=res["recommendation"],
                reasoning=res["reasoning"],
                confidence=res["confidence"],
            )
            analyzed_list.append({
                "id": notif.id,
                "stock_code": notif.stock_code,
                "title": notif.title,
                "summary": notif.summary,
                "publish_date": notif.publish_date,
                "recommendation": res["recommendation"],
                "confidence": res["confidence"],
                "reasoning": res["reasoning"],
            })

    # 3. Ham Çıktıyı Yazdır
    print("=" * 95)
    print("GERÇEK 7 ÖDA BİLDİRİMİ İÇİN YEREL LLM ANALİZ VE ÖNERİ SONUÇLARI (HAM ÇIKTI)")
    print("=" * 95)

    for i, item in enumerate(analyzed_list, 1):
        print(f"\n--- [KAYIT #{i}] {item['stock_code']} ({item['publish_date']}) ---")
        print(f"Başlık     : {item['title']}")
        print(f"Özet       : {item['summary']}")
        print(f"Öneri      : {item['recommendation']}")
        print(f"Güven      : {item['confidence']}/5")
        print(f"Gerekçe    : {item['reasoning']}")

    # Dağılım
    recs = [item["recommendation"] for item in analyzed_list]
    print("\n" + "=" * 95)
    print("📊 ÖNERİ DAĞILIMI:")
    print(f"- Toplam İncelenen: {len(analyzed_list)}")
    print(f"- AL   : {recs.count('AL')} adet")
    print(f"- SAT  : {recs.count('SAT')} adet")
    print(f"- NÖTR : {recs.count('NÖTR')} adet")
    print("=" * 95)


if __name__ == "__main__":
    asyncio.run(run_real_oda_test())
