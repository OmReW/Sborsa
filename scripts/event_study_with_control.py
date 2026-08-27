import sys
import random
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = Path(__file__).resolve().parent.parent

# 1. BIST100 Fiyat Verisi
df = yf.download("XU100.IS", start="2002-01-01", end="2026-08-27", progress=False)
if isinstance(df.columns, pd.MultiIndex):
    prices = df["Close"]["XU100.IS"]
else:
    prices = df["Close"]
prices.index = pd.to_datetime(prices.index).tz_localize(None)

# 2. Gerçek Olaylar Verisi
event_df = pd.read_csv(BASE_DIR / "scripts" / "event_study_results.csv", encoding="utf-8-sig")
event_dates = set(pd.to_datetime(event_df["date"]).dt.date)

# 3. Kontrol Grubu: Olay tarihlerinin +-5 gün dışındaki işlem günleri
valid_dates = [d.date() for d in prices.loc["2010-01-01":"2026-06-01"].index]
excluded = set()
for ed in event_dates:
    for offset in range(-5, 6):
        excluded.add(ed + timedelta(days=offset))

candidate_dates = [d for d in valid_dates if d not in excluded]

# Sabit seed ile 210 rastgele tarih seç
random.seed(42)
control_sample = random.sample(candidate_dates, min(210, len(candidate_dates)))

control_results = []
for cd in control_sample:
    cd_ts = pd.Timestamp(cd)
    pre_df = prices[prices.index <= cd_ts]
    post_df = prices[prices.index >= cd_ts]
    if len(pre_df) < 25 or len(post_df) < 25:
        continue
    p_t0 = float(post_df.iloc[0])
    p_t_minus_1 = float(pre_df.iloc[-2]) if len(pre_df) >= 2 else float(pre_df.iloc[-1])
    lookback_idx = max(0, len(pre_df) - 22)
    p_pre_30 = float(pre_df.iloc[lookback_idx])
    p_t_plus_1 = float(post_df.iloc[1]) if len(post_df) >= 2 else p_t0
    p_t_plus_5 = float(post_df.iloc[5])
    p_post_30 = float(post_df.iloc[22])

    pre_30d = ((p_t0 - p_pre_30) / p_pre_30) * 100.0
    jump = ((p_t_plus_1 - p_t_minus_1) / p_t_minus_1) * 100.0
    post_5d = ((p_t_plus_5 - p_t0) / p_t0) * 100.0
    post_30d = ((p_post_30 - p_t0) / p_t0) * 100.0

    control_results.append({
        "date": str(cd),
        "pre_30d_return_pct": pre_30d,
        "event_jump_pct": jump,
        "post_5d_return_pct": post_5d,
        "post_30d_return_pct": post_30d,
    })

ctrl_df = pd.DataFrame(control_results)
ctrl_pre = ctrl_df["pre_30d_return_pct"].mean()
ctrl_jump = ctrl_df["event_jump_pct"].mean()
ctrl_5d = ctrl_df["post_5d_return_pct"].mean()
ctrl_30d = ctrl_df["post_30d_return_pct"].mean()

print(f"\n{'='*120}")
print(f"🔬 BIST100 MAKRO OLAY ETKİ ÇALIŞMASI: GERÇEK OLAYLAR vs. RASTGELE KONTROL GRUBU (N=210)")
print(f"{'='*120}\n")

print(f"📌 BIST100 BAZ / KONTROL GRUBU ORTALAMALARI (N={len(ctrl_df)} Rastgele Tarih, 2010-2026):")
print(f"   • Öncesi 30G Doğal Piyasa Getirisi : %{ctrl_pre:+.2f}")
print(f"   • Doğal Günlük Fiyat Değişimi      : %{ctrl_jump:+.2f}")
print(f"   • Sonrası 5G Doğal Piyasa Getirisi : %{ctrl_5d:+.2f}")
print(f"   • Sonrası 30G Doğal Piyasa Getirisi: %{ctrl_30d:+.2f}")
print(f"{'-'*120}\n")

# Kategori bazlı fark tablosu
categories = sorted(list(event_df["category"].unique()))
faiz_all_df = event_df[event_df["category"].str.startswith("FAİZ_")]

print(f"{'Kategori':<20} | {'N':<6} | {'Metrik':<16} | {'Gerçek Olay':>12} | {'Kontrol Grubu':>13} | {'Gerçek Fark (Δ)':>15} | {'Etki / Anlamlılık'}")
print("=" * 120)

for cat in categories:
    sub = event_df[event_df["category"] == cat]
    n_count = len(sub)
    mean_pre = sub["pre_30d_return_pct"].mean()
    mean_jump = sub["event_jump_pct"].mean()
    mean_5d = sub["post_5d_return_pct"].mean()
    mean_30d = sub["post_30d_return_pct"].mean()

    diff_pre = mean_pre - ctrl_pre
    diff_jump = mean_jump - ctrl_jump
    diff_5d = mean_5d - ctrl_5d
    diff_30d = mean_30d - ctrl_30d

    def assess_impact(diff):
        if abs(diff) < 0.75:
            return "Özel Etki Yok (Trendle Uyumlu)"
        elif diff > 0:
            return f"Pozitif Ayrışma (+%{diff:.2f})"
        else:
            return f"Negatif Baskı (%{diff:.2f})"

    print(f"{cat:<20} | {n_count:<6} | Öncesi 30G       | %{mean_pre:>10.2f} | %{ctrl_pre:>11.2f} | %{diff_pre:>13.2f} | {assess_impact(diff_pre)}")
    print(f"{'':<20} | {'':<6} | Olay Günü Tepki  | %{mean_jump:>10.2f} | %{ctrl_jump:>11.2f} | %{diff_jump:>13.2f} | {assess_impact(diff_jump)}")
    print(f"{'':<20} | {'':<6} | Sonrası 5G       | %{mean_5d:>10.2f} | %{ctrl_5d:>11.2f} | %{diff_5d:>13.2f} | {assess_impact(diff_5d)}")
    print(f"{'':<20} | {'':<6} | Sonrası 30G      | %{mean_30d:>10.2f} | %{ctrl_30d:>11.2f} | %{diff_30d:>13.2f} | {assess_impact(diff_30d)}")
    print("-" * 120)

# Tüm Faiz Kararları Toplamı
if not faiz_all_df.empty:
    n_faiz = len(faiz_all_df)
    m_pre = faiz_all_df["pre_30d_return_pct"].mean()
    m_jump = faiz_all_df["event_jump_pct"].mean()
    m_5d = faiz_all_df["post_5d_return_pct"].mean()
    m_30d = faiz_all_df["post_30d_return_pct"].mean()
    d_pre = m_pre - ctrl_pre
    d_jump = m_jump - ctrl_jump
    d_5d = m_5d - ctrl_5d
    d_30d = m_30d - ctrl_30d

    print(f"{'TÜM FAİZ KARARLARI':<20} | {n_faiz:<6} | Öncesi 30G       | %{m_pre:>10.2f} | %{ctrl_pre:>11.2f} | %{d_pre:>13.2f} | {assess_impact(d_pre)}")
    print(f"{'':<20} | {'':<6} | Olay Günü Tepki  | %{m_jump:>10.2f} | %{ctrl_jump:>11.2f} | %{d_jump:>13.2f} | {assess_impact(d_jump)}")
    print(f"{'':<20} | {'':<6} | Sonrası 5G       | %{m_5d:>10.2f} | %{ctrl_5d:>11.2f} | %{d_5d:>13.2f} | {assess_impact(d_5d)}")
    print(f"{'':<20} | {'':<6} | Sonrası 30G      | %{m_30d:>10.2f} | %{ctrl_30d:>11.2f} | %{d_30d:>13.2f} | {assess_impact(d_30d)}")
    print("=" * 120)
