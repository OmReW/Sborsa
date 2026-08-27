import sys
import os
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
import pandas as pd
import yfinance as yf

# Proje kök dizini
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from ingestion.macro_calendar import (
    TURKEY_ELECTIONS,
    TCMB_PPK_ALL_MEETINGS,
    TURKEY_POLICY_SHOCKS,
)
from config.logger import get_logger

logger = get_logger("event_study")


def run_event_study(ticker: str = "XU100.IS") -> pd.DataFrame:
    """
    2002'den bugüne tüm seçim/referandumlar ile 2010'dan bugüne tüm TCMB PPK
    faiz kararlarının BIST100 endeksi üzerindeki etkisini hesaplar.
    """
    events_pool = TURKEY_ELECTIONS + TCMB_PPK_ALL_MEETINGS + TURKEY_POLICY_SHOCKS
    events_pool.sort(key=lambda x: x["date"])

    print(f"\n{'='*85}")
    print(f"🏛️ GENİŞLETİLMİŞ BIST100 (XU100) MAKRO OLAY ETKİ ÇALIŞMASI (EVENT STUDY)")
    print(f"Toplam Olay Havuzu: {len(events_pool)} Adet (TCMB PPK Kararları + Seçimler + Şoklar)")
    print(f"{'='*85}\n")

    print("⏳ BIST100 (XU100.IS) 2002-2026 tüm tarihsel verisi yfinance'tan tek seferde çekiliyor...")
    full_df = yf.download(ticker, start="2002-01-01", end=datetime.now().strftime("%Y-%m-%d"), progress=False)
    if full_df.empty:
        print("❌ XU100 verisi çekilemedi!")
        return pd.DataFrame()

    full_df = full_df.sort_index()

    # Sütun düzeltme (MultiIndex koruması)
    col_name = "Close"
    if isinstance(full_df.columns, pd.MultiIndex):
        prices = full_df[col_name][ticker] if ticker in full_df[col_name] else full_df[col_name].iloc[:, 0]
    else:
        prices = full_df[col_name]

    # Timestamp index formatını normalize et
    prices.index = pd.to_datetime(prices.index).tz_localize(None)

    results = []

    for ev in events_pool:
        ev_date_str = ev["date"]
        ev_title = ev["title"]
        ev_cat = ev["category"]
        ev_desc = ev.get("description", "")

        try:
            ev_dt = datetime.strptime(ev_date_str, "%Y-%m-%d")
            ev_ts = pd.Timestamp(ev_dt)

            pre_df = prices[prices.index <= ev_ts]
            post_df = prices[prices.index >= ev_ts]

            # En az 10 günlük veri penceresi olmalı
            if len(pre_df) < 5 or len(post_df) < 2:
                continue

            # Olay anı fiyatı (T0)
            t0_idx = post_df.index[0]
            p_t0 = float(post_df.loc[t0_idx])

            # Olaydan 1 gün önceki işlem günü (T-1)
            p_t_minus_1 = float(pre_df.iloc[-2]) if len(pre_df) >= 2 else float(pre_df.iloc[-1])

            # Olaydan ~20-22 işlem günü (1 takvim ayı) önceki fiyat (T-30)
            lookback_idx = max(0, len(pre_df) - 22)
            p_pre_30 = float(pre_df.iloc[lookback_idx])

            # Olaydan 1 gün sonraki fiyat (T+1)
            p_t_plus_1 = float(post_df.iloc[1]) if len(post_df) >= 2 else p_t0

            # Olaydan 5 işlem günü sonraki fiyat (T+5)
            p_t_plus_5 = float(post_df.iloc[min(5, len(post_df) - 1)])

            # Olaydan ~20-22 işlem günü (1 takvim ayı) sonraki fiyat (T+30)
            lookahead_idx = min(len(post_df) - 1, 22)
            p_post_30 = float(post_df.iloc[lookahead_idx])

            # Getiri hesaplamaları (%)
            pre_30d_return = ((p_t0 - p_pre_30) / p_pre_30) * 100.0 if p_pre_30 > 0 else 0.0
            event_day_jump = ((p_t_plus_1 - p_t_minus_1) / p_t_minus_1) * 100.0 if p_t_minus_1 > 0 else 0.0
            post_5d_return = ((p_t_plus_5 - p_t0) / p_t0) * 100.0 if p_t0 > 0 else 0.0
            post_30d_return = ((p_post_30 - p_t0) / p_t0) * 100.0 if p_t0 > 0 else 0.0

            results.append({
                "date": ev_date_str,
                "category": ev_cat,
                "title": ev_title,
                "description": ev_desc,
                "price_pre_30d": round(p_pre_30, 2),
                "price_event_t0": round(p_t0, 2),
                "price_post_5d": round(p_t_plus_5, 2),
                "price_post_30d": round(p_post_30, 2),
                "pre_30d_return_pct": round(pre_30d_return, 2),
                "event_jump_pct": round(event_day_jump, 2),
                "post_5d_return_pct": round(post_5d_return, 2),
                "post_30d_return_pct": round(post_30d_return, 2),
            })

        except Exception as e:
            logger.debug(f"[EventStudy] {ev_title} ({ev_date_str}) hesaplanamadı: {e}")

    results_df = pd.DataFrame(results)

    # CSV olarak kaydet
    out_csv = BASE_DIR / "scripts" / "event_study_results.csv"
    results_df.to_csv(out_csv, index=False, encoding="utf-8-sig")
    logger.info(f"Event Study sonuçları kaydedildi ({len(results_df)} olay): {out_csv}")

    # Kategori Bazlı Ortalama İstatistikler & Örneklem Sayıları (N)
    print(f"\n📊 KATEGORİ BAZLI XU100 GETİRİ PERFORMANSI (Toplam N={len(results_df)} Olay):")
    print("-" * 115)
    print(f"{'Kategori':<22} | {'Örneklem (N)':<12} | {'Öncesi 30G':>12} | {'Olay Günü (Tepki)':>18} | {'Sonrası 5G':>12} | {'Sonrası 30G':>13}")
    print("-" * 115)

    # Faiz Kararlarını Tek Bir Başlıkta da Göster
    faiz_all_df = results_df[results_df["category"].str.startswith("FAİZ_")]
    
    categories = list(results_df["category"].unique())
    categories.sort()

    for cat in categories:
        sub = results_df[results_df["category"] == cat]
        n_count = len(sub)
        mean_pre = sub["pre_30d_return_pct"].mean()
        mean_jump = sub["event_jump_pct"].mean()
        mean_5d = sub["post_5d_return_pct"].mean()
        mean_30d = sub["post_30d_return_pct"].mean()

        print(
            f"{cat:<22} | N = {n_count:<8} | "
            f"%{mean_pre:>10.2f} | "
            f"%{mean_jump:>16.2f} | "
            f"%{mean_5d:>10.2f} | "
            f"%{mean_30d:>11.2f}"
        )

    print("-" * 115)
    if not faiz_all_df.empty:
        n_faiz = len(faiz_all_df)
        print(
            f"{'TOPLAM TÜM FAİZ KARARLARI':<22} | N = {n_faiz:<8} | "
            f"%{faiz_all_df['pre_30d_return_pct'].mean():>10.2f} | "
            f"%{faiz_all_df['event_jump_pct'].mean():>16.2f} | "
            f"%{faiz_all_df['post_5d_return_pct'].mean():>10.2f} | "
            f"%{faiz_all_df['post_30d_return_pct'].mean():>11.2f}"
        )
        print("-" * 115)

    return results_df


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    run_event_study()
