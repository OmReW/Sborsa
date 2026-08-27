import sqlite3
import json
import sys
from pathlib import Path
import pandas as pd

# Windows konsol UTF-8 ayarı
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "storage" / "borsa.db"
CSV_PATH = BASE_DIR / "scripts" / "backtest_results.csv"

def inspect_content():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # =========================================================================
    # 1. Backtest'te kullanılan 30 kaydın summary ve raw_content alanları
    # =========================================================================
    print("=" * 90)
    print("1. BACKTEST'TE KULLANILAN 30 KAYDIN HAM 'summary' VE 'raw_content' ALANLARI")
    print("=" * 90)

    if CSV_PATH.exists():
        df_csv = pd.read_csv(CSV_PATH)
        for idx, row in df_csv.iterrows():
            sc = row["stock_code"]
            dt = row["date"]
            title = row["title"]
            
            # DB'den tam kaydı çek
            cursor.execute(
                """
                SELECT id, stock_code, title, publish_date, summary, raw_content 
                FROM kap_notifications 
                WHERE stock_code = ? AND publish_date LIKE ? AND id NOT LIKE 'TEST-%'
                LIMIT 1;
                """,
                (sc, f"%{dt.split('-')[0]}%"),
            )
            db_row = cursor.fetchone()
            
            summary_val = db_row["summary"] if db_row else "(DB Kaydı Bulunamadı)"
            raw_val = db_row["raw_content"] if db_row else "(DB Kaydı Bulunamadı)"

            print(f"\n--- ÖRNEK #{idx+1} | {sc} | {dt} ---")
            print(f"BAŞLIK     : {title}")
            print(f"SUMMARY    : {repr(summary_val)}")
            print(f"RAW_CONTENT: {raw_val}")

    # =========================================================================
    # 2. Veritabanındaki tüm 1500+ kaydın içerik uzunluğu analizi
    # =========================================================================
    print("\n" + "=" * 90)
    print("2. TÜM VERİTABANINDAKİ (1508 KAYIT) İÇERİK UZUNLUĞU VE DOLULUK ANALİZİ")
    print("=" * 90)

    cursor.execute("SELECT COUNT(*) FROM kap_notifications WHERE id NOT LIKE 'TEST-%';")
    total_non_test = cursor.fetchone()[0]

    # summary uzunlukları
    cursor.execute("SELECT COUNT(*) FROM kap_notifications WHERE id NOT LIKE 'TEST-%' AND (summary IS NULL OR summary = '' OR TRIM(summary) = '');")
    empty_summary_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM kap_notifications WHERE id NOT LIKE 'TEST-%' AND LENGTH(TRIM(summary)) > 0 AND LENGTH(TRIM(summary)) <= 20;")
    short_summary_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM kap_notifications WHERE id NOT LIKE 'TEST-%' AND LENGTH(TRIM(summary)) > 20 AND LENGTH(TRIM(summary)) <= 100;")
    med_summary_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM kap_notifications WHERE id NOT LIKE 'TEST-%' AND LENGTH(TRIM(summary)) > 100;")
    long_summary_count = cursor.fetchone()[0]

    print(f"Toplam İncelenen Kayıt Sayısı : {total_non_test}")
    print(f"- summary alanı tamamen BOŞ olanlar         : {empty_summary_count}")
    print(f"- summary alanı 1 - 20 karakter olanlar     : {short_summary_count} (örn: 'Faaliyet Raporu')")
    print(f"- summary alanı 21 - 100 karakter olanlar   : {med_summary_count} (örn: '01.01.2016-31.03.2016 Dönemi Raporu')")
    print(f"- summary alanı 100 karakterden UZUN olanlar: {long_summary_count}")

    # Örnek uzun summary kayıtları (varsa)
    cursor.execute(
        """
        SELECT stock_code, publish_date, title, summary 
        FROM kap_notifications 
        WHERE id NOT LIKE 'TEST-%' AND LENGTH(TRIM(summary)) > 50
        LIMIT 5;
        """
    )
    long_samples = cursor.fetchall()
    print(f"\n--- 50 Karakterden Uzun En Dolu 5 Kayıt Örneği ---")
    if long_samples:
        for r in long_samples:
            print(f"[{r['stock_code']}] ({r['publish_date']}) {r['title']}: {repr(r['summary'])}")
    else:
        print("50 karakterden uzun kayıt bulunamadı.")

    conn.close()

if __name__ == "__main__":
    inspect_content()
