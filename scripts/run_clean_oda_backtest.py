import asyncio
import csv
import json
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List

import pandas as pd
import yfinance as yf

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

TICKER_MAP = {
    "GARAN, TGB": "GARAN",
    "ISATR, ISBTR, ISCTR, ISKUR, TIB": "ISCTR",
    "YKB, YKBNK": "YKBNK",
}

ACTIVE_BIST_TICKERS = {
    "THYAO", "GARAN", "ASELS", "EREGL", "BIMAS",
    "KCHOL", "SISE", "AKBNK", "TUPRS", "FROTO",
    "SAHOL", "ISCTR", "YKBNK", "PGSUS", "PETKM",
    "TCELL", "ENKAI", "EKGYO", "TOASO", "ARCLK"
}

# Rapor niteliğindeki kelimeler (hariç tutulacak)
EXCLUDED_KEYWORDS = [
    "faaliyet raporu", "finansal rapor", "uyum raporu", 
    "sorumluluk beyanı", "denetim raporu", "kurumsal yönetim ilkeleri"
]


def parse_notification_date(date_str: str) -> Optional[datetime]:
    date_str = date_str.strip()
    for fmt in ("%d.%m.%Y %H:%M:%S", "%d.%m.%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            pass
    return None


def get_price_returns_1d_5d(ticker: str, pub_date: datetime) -> Optional[Dict[str, float]]:
    clean_ticker = TICKER_MAP.get(ticker, ticker).split(",")[0].strip().upper()
    yf_symbol = f"{clean_ticker}.IS"

    start_dt = pub_date - timedelta(days=3)
    end_dt = pub_date + timedelta(days=20)

    try:
        df = yf.download(
            yf_symbol,
            start=start_dt.strftime("%Y-%m-%d"),
            end=end_dt.strftime("%Y-%m-%d"),
            progress=False,
        )
        if df.empty or len(df) < 7:
            return None

        df = df.sort_index()

        if isinstance(df.columns, pd.MultiIndex):
            close_series = df["Close"][yf_symbol] if yf_symbol in df["Close"] else df["Close"].iloc[:, 0]
        else:
            close_series = df["Close"]

        pub_ts = pd.Timestamp(pub_date.date())
        valid_dates = close_series[close_series.index >= pub_ts]

        if len(valid_dates) < 6:
            return None

        p0 = float(valid_dates.iloc[0])
        p1 = float(valid_dates.iloc[1])
        p5 = float(valid_dates.iloc[5])

        if p0 <= 0:
            return None

        ret_1d = ((p1 - p0) / p0) * 100.0
        ret_5d = ((p5 - p0) / p0) * 100.0

        return {
            "p0": p0,
            "p1": p1,
            "p5": p5,
            "ret_1d": ret_1d,
            "ret_5d": ret_5d,
        }
    except Exception:
        return None


async def run_clean_backtest():
    print("=" * 125)
    print("🎯 Borsa-AI: Saf Olay Bazlı ÖDA (Özel Durum Açıklaması) Backtest Analizi (N=50)")
    print("   [Tüm Faaliyet/Finansal Raporları Hariç Tutulmuş Temiz Veri Seti]")
    print("=" * 125)

    db = DatabaseManager()
    analyzer = KAPAnalyzer()

    # 1. Veritabanından sadece olay bazlı gerçek ÖDA kayıtlarını çek
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, disclosure_index, stock_code, stock_codes, company_name,
                   title, subject, disclosure_class, publish_date, summary, link
            FROM kap_notifications 
            WHERE disclosure_class = 'ODA' 
              AND LENGTH(TRIM(summary)) >= 15
              AND id NOT LIKE 'TEST-%';
            """
        )
        rows = cursor.fetchall()

    pure_event_odas: List[KapNotification] = []
    for r in rows:
        sc = r["stock_code"]
        clean_sc = TICKER_MAP.get(sc, sc).split(",")[0].strip().upper()
        title_lower = (r["title"] or "").lower()
        summary_lower = (r["summary"] or "").lower()
        subject_lower = (r["subject"] or "").lower()
        full_text = f"{title_lower} {summary_lower} {subject_lower}"

        # Faaliyet ve finansal rapor türevlerini ele
        if any(kw in full_text for kw in EXCLUDED_KEYWORDS):
            continue

        if clean_sc in ACTIVE_BIST_TICKERS:
            dt = parse_notification_date(r["publish_date"])
            if dt and 2016 <= dt.year <= 2023:
                pure_event_odas.append(
                    KapNotification(
                        id=r["id"],
                        disclosure_index=r["disclosure_index"],
                        stock_code=clean_sc,
                        stock_codes=r["stock_codes"],
                        company_name=r["company_name"],
                        title=r["title"],
                        subject=r["subject"],
                        disclosure_class="ODA",
                        publish_date=r["publish_date"],
                        summary=r["summary"],
                        link=r["link"],
                    )
                )

    print(f"Toplam Saf Olay Bazlı ÖDA Bildirimi Sayısı: {len(pure_event_odas)}")

    # Sabit seed (42) ile tekrarlanabilir 50 örnek seç
    random.seed(42)
    random.shuffle(pure_event_odas)

    selected_sample: List[KapNotification] = []
    for notif in pure_event_odas:
        pub_dt = parse_notification_date(notif.publish_date)
        prices = get_price_returns_1d_5d(notif.stock_code, pub_dt)
        if prices:
            selected_sample.append(notif)
        if len(selected_sample) >= 50:
            break

    print(f"Seçilen Nihai Örneklem Boyutu: {len(selected_sample)} adet (Sabit Seed = 42)\n")

    results: List[Dict[str, Any]] = []
    print("🧠 Yerel LLM (ozel-qwen:latest) ile 50 Saf ÖDA Bildirimi Analiz Ediliyor...")

    for i, notif in enumerate(selected_sample, 1):
        pub_dt = parse_notification_date(notif.publish_date)
        prices = get_price_returns_1d_5d(notif.stock_code, pub_dt)
        if not prices:
            continue

        analysis = await analyzer.analyze_notification(notif)
        if not analysis:
            continue

        rec = analysis["recommendation"]
        conf = analysis["confidence"]
        reasoning = analysis["reasoning"]

        ret_1d = prices["ret_1d"]
        ret_5d = prices["ret_5d"]

        dir_1d = "YÜKSELDİ" if ret_1d > 1.0 else ("DÜŞTÜ" if ret_1d < -1.0 else "YATAY")
        if rec == "AL" and ret_1d > 0:
            res_1d = "DOĞRU"
        elif rec == "SAT" and ret_1d < 0:
            res_1d = "DOĞRU"
        elif rec == "NÖTR" and dir_1d == "YATAY":
            res_1d = "DOĞRU"
        else:
            res_1d = "YANLIŞ"

        dir_5d = "YÜKSELDİ" if ret_5d > 1.0 else ("DÜŞTÜ" if ret_5d < -1.0 else "YATAY")
        if rec == "AL" and ret_5d > 0:
            res_5d = "DOĞRU"
        elif rec == "SAT" and ret_5d < 0:
            res_5d = "DOĞRU"
        elif rec == "NÖTR" and dir_5d == "YATAY":
            res_5d = "DOĞRU"
        else:
            res_5d = "YANLIŞ"

        results.append({
            "no": len(results) + 1,
            "stock_code": notif.stock_code,
            "date": pub_dt.strftime("%Y-%m-%d"),
            "disclosure_class": notif.disclosure_class,
            "title": notif.title[:30] + ("..." if len(notif.title) > 30 else ""),
            "summary": notif.summary[:45] + ("..." if len(notif.summary) > 45 else ""),
            "recommendation": rec,
            "confidence": conf,
            "ret_1d": ret_1d,
            "dir_1d": dir_1d,
            "res_1d": res_1d,
            "ret_5d": ret_5d,
            "dir_5d": dir_5d,
            "res_5d": res_5d,
            "reasoning": reasoning,
            "link": notif.link,
        })

        print(f"[{len(results)}/50] {notif.stock_code} | {pub_dt.strftime('%Y-%m-%d')} | ÖDA | Öneri: {rec} (Güven: {conf}/5) -> 1G: {ret_1d:+.2f}% | 5G: {ret_5d:+.2f}%")

        if len(results) >= 50:
            break

    # CSV Kaydet
    csv_path = BASE_DIR / "scripts" / "backtest_results.csv"
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "no", "stock_code", "date", "disclosure_class", "title", "summary",
            "recommendation", "confidence", "ret_1d", "dir_1d", "res_1d",
            "ret_5d", "dir_5d", "res_5d", "reasoning", "link"
        ])
        writer.writeheader()
        writer.writerows(results)

    # TABLO ÇIKTISI
    print("\n" + "=" * 135)
    print(f"{'#':<3} | {'Hisse':<6} | {'Tarih':<10} | {'Sınıf':<5} | {'Öneri':<5} | {'Güven':<5} | {'1G Değ.':<9} | {'1G Sonuç':<8} | {'5G Değ.':<9} | {'5G Sonuç':<8} | {'Özet / Başlık':<35}")
    print("-" * 135)

    for r in results:
        ret1_str = f"{r['ret_1d']:+.2f}%"
        ret5_str = f"{r['ret_5d']:+.2f}%"
        print(f"{r['no']:<3} | {r['stock_code']:<6} | {r['date']:<10} | {r['disclosure_class']:<5} | {r['recommendation']:<5} | {r['confidence']:<5} | {ret1_str:<9} | {r['res_1d']:<8} | {ret5_str:<9} | {r['res_5d']:<8} | {r['summary']:<35}")

    print("=" * 135)

    # ÖZET İSTATİSTİKLER
    total_count = len(results)
    correct_1d = sum(1 for r in results if r["res_1d"] == "DOĞRU")
    hit_1d = (correct_1d / total_count * 100) if total_count > 0 else 0

    correct_5d = sum(1 for r in results if r["res_5d"] == "DOĞRU")
    hit_5d = (correct_5d / total_count * 100) if total_count > 0 else 0

    al_list = [r for r in results if r["recommendation"] == "AL"]
    sat_list = [r for r in results if r["recommendation"] == "SAT"]
    notr_list = [r for r in results if r["recommendation"] == "NÖTR"]

    al_1d_cor = sum(1 for r in al_list if r["res_1d"] == "DOĞRU")
    al_5d_cor = sum(1 for r in al_list if r["res_5d"] == "DOĞRU")

    sat_1d_cor = sum(1 for r in sat_list if r["res_1d"] == "DOĞRU")
    sat_5d_cor = sum(1 for r in sat_list if r["res_5d"] == "DOĞRU")

    notr_1d_cor = sum(1 for r in notr_list if r["res_1d"] == "DOĞRU")
    notr_5d_cor = sum(1 for r in notr_list if r["res_5d"] == "DOĞRU")

    high_conf = [r for r in results if r["confidence"] >= 4]
    low_conf = [r for r in results if r["confidence"] <= 3]

    high_1d_cor = sum(1 for r in high_conf if r["res_1d"] == "DOĞRU")
    high_5d_cor = sum(1 for r in high_conf if r["res_5d"] == "DOĞRU")

    low_1d_cor = sum(1 for r in low_conf if r["res_1d"] == "DOĞRU")
    low_5d_cor = sum(1 for r in low_conf if r["res_5d"] == "DOĞRU")

    print("\n📈 ÖZET İSTATİSTİKLER (SAF OLAY BAZLI ÖDA):")
    print(f"- Toplam Analiz Edilen ÖRNEK SAYISI : {total_count}")
    print()
    print("📊 ÖNERİ DAĞILIMI:")
    print(f"  • AL   Önerisi : {len(al_list)} adet (%{len(al_list)/total_count*100:.1f})")
    print(f"  • SAT  Önerisi : {len(sat_list)} adet (%{len(sat_list)/total_count*100:.1f})")
    print(f"  • NÖTR Önerisi : {len(notr_list)} adet (%{len(notr_list)/total_count*100:.1f})")
    print()
    print("🎯 GENEL İSABET ORANLARI (HIT RATE):")
    print(f"  • 1 Günlük İsabet Oranı : {correct_1d} / {total_count} (%{hit_1d:.1f})")
    print(f"  • 5 Günlük İsabet Oranı : {correct_5d} / {total_count} (%{hit_5d:.1f})")
    print()
    print("🔍 ÖNERİ TÜRÜNE GÖRE İSABET DAĞILIMI:")
    print(f"  • AL Önerileri   -> 1G Doğru: {al_1d_cor}/{len(al_list)} (%{al_1d_cor/max(1,len(al_list))*100:.1f}) | 5G Doğru: {al_5d_cor}/{len(al_list)} (%{al_5d_cor/max(1,len(al_list))*100:.1f})")
    print(f"  • SAT Önerileri  -> 1G Doğru: {sat_1d_cor}/{len(sat_list)} (%{sat_1d_cor/max(1,len(sat_list))*100:.1f}) | 5G Doğru: {sat_5d_cor}/{len(sat_list)} (%{sat_5d_cor/max(1,len(sat_list))*100:.1f})")
    print(f"  • NÖTR Önerileri -> 1G Doğru: {notr_1d_cor}/{len(notr_list)} (%{notr_1d_cor/max(1,len(notr_list))*100:.1f}) | 5G Doğru: {notr_5d_cor}/{len(notr_list)} (%{notr_5d_cor/max(1,len(notr_list))*100:.1f})")
    print()
    print("⭐ GÜVEN SEVİYESİ KALİBRASYON ANALİZİ:")
    print(f"  • YÜKSEK GÜVEN (Güven >= 4) [Toplam {len(high_conf)} adet]:")
    print(f"    - 1 Günlük İsabet : {high_1d_cor} / {len(high_conf)} (%{high_1d_cor/max(1,len(high_conf))*100:.1f})")
    print(f"    - 5 Günlük İsabet : {high_5d_cor} / {len(high_conf)} (%{high_5d_cor/max(1,len(high_conf))*100:.1f})")
    print(f"  • DÜŞÜK GÜVEN (Güven <= 3) [Toplam {len(low_conf)} adet]:")
    print(f"    - 1 Günlük İsabet : {low_1d_cor} / {len(low_conf)} (%{low_1d_cor/max(1,len(low_conf))*100:.1f})")
    print(f"    - 5 Günlük İsabet : {low_5d_cor} / {len(low_conf)} (%{low_5d_cor/max(1,len(low_conf))*100:.1f})")
    print("=" * 135)


if __name__ == "__main__":
    asyncio.run(run_clean_backtest())
