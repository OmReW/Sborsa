import sys
import random
import numpy as np
import pandas as pd
import scipy.stats as stats
import yfinance as yf
from datetime import datetime, timedelta
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = Path(__file__).resolve().parent.parent

# 1. BIST100 ve MSCI EM (EEM) Verisini Çek
print("⏳ BIST100 (XU100.IS) ve MSCI Emerging Markets (EEM) verisi çekiliyor...")
raw_data = yf.download(["XU100.IS", "EEM"], start="2003-04-01", end="2026-08-27", progress=False)

if isinstance(raw_data.columns, pd.MultiIndex):
    xu100 = raw_data["Close"]["XU100.IS"].dropna()
    eem = raw_data["Close"]["EEM"].dropna()
else:
    xu100 = raw_data["Close"]
    eem = raw_data["Close"]

xu100.index = pd.to_datetime(xu100.index).tz_localize(None)
eem.index = pd.to_datetime(eem.index).tz_localize(None)

# Ortak işlem günlerini birleştir
combined = pd.DataFrame({"XU100": xu100, "EEM": eem}).dropna().sort_index()

# 2. Gerçek Olaylar Listesini Yükle
event_df = pd.read_csv(BASE_DIR / "scripts" / "event_study_results.csv", encoding="utf-8-sig")
event_dates = set(pd.to_datetime(event_df["date"]).dt.date)

# 3. Kontrol Grubu: Olayların +-5 gün dışındaki rastgele tarihler
valid_dates = [d.date() for d in combined.loc["2010-01-01":"2026-06-01"].index]
excluded = set()
for ed in event_dates:
    for offset in range(-5, 6):
        excluded.add(ed + timedelta(days=offset))

candidate_dates = [d for d in valid_dates if d not in excluded]
random.seed(42)
control_sample = random.sample(candidate_dates, min(210, len(candidate_dates)))

def calculate_abnormal_metrics(prices_df, target_date):
    t_date = pd.Timestamp(target_date)
    pre = prices_df[prices_df.index <= t_date]
    post = prices_df[prices_df.index >= t_date]
    if len(pre) < 25 or len(post) < 25:
        return None
    
    # T0, T-1, T-22 (30G), T+1, T+5, T+22 (30G)
    p0_x, p0_e = pre["XU100"].iloc[-1], pre["EEM"].iloc[-1]
    p_m1_x, p_m1_e = (pre["XU100"].iloc[-2], pre["EEM"].iloc[-2]) if len(pre) >= 2 else (p0_x, p0_e)
    p_pre30_x, p_pre30_e = pre["XU100"].iloc[-22], pre["EEM"].iloc[-22]
    
    p_p1_x, p_p1_e = post["XU100"].iloc[1], post["EEM"].iloc[1]
    p_p5_x, p_p5_e = post["XU100"].iloc[min(5, len(post)-1)], post["EEM"].iloc[min(5, len(post)-1)]
    p_p30_x, p_p30_e = post["XU100"].iloc[min(22, len(post)-1)], post["EEM"].iloc[min(22, len(post)-1)]

    # XU100 Getirileri (%)
    rx_pre30 = ((p0_x - p_pre30_x) / p_pre30_x) * 100.0
    rx_jump = ((p_p1_x - p_m1_x) / p_m1_x) * 100.0
    rx_post5 = ((p_p5_x - p0_x) / p0_x) * 100.0
    rx_post30 = ((p_p30_x - p0_x) / p0_x) * 100.0

    # EEM (MSCI EM) Getirileri (%)
    re_pre30 = ((p0_e - p_pre30_e) / p_pre30_e) * 100.0
    re_jump = ((p_p1_e - p_m1_e) / p_m1_e) * 100.0
    re_post5 = ((p_p5_e - p0_e) / p0_e) * 100.0
    re_post30 = ((p_p30_e - p0_e) / p0_e) * 100.0

    # Anormal Getiriler (Excess Returns = XU100 - MSCI EM)
    return {
        "ar_pre30": rx_pre30 - re_pre30,
        "ar_jump": rx_jump - re_jump,
        "ar_post5": rx_post5 - re_post5,
        "ar_post30": rx_post30 - re_post30,
    }

# Kontrol Grubu Hesapla
ctrl_list = []
for cd in control_sample:
    m = calculate_abnormal_metrics(combined, cd)
    if m:
        ctrl_list.append(m)
ctrl_df = pd.DataFrame(ctrl_list)

# Gerçek Olaylar Hesapla
event_ar_list = []
for _, row in event_df.iterrows():
    ed_str = row["date"]
    m = calculate_abnormal_metrics(combined, ed_str)
    if m:
        m["category"] = row["category"]
        m["title"] = row["title"]
        m["date"] = ed_str
        event_ar_list.append(m)
event_ar_df = pd.DataFrame(event_ar_list)

print(f"\n{'='*125}")
print("1. BIST100 ANORMAL GETİRİ ANALİZİ (BENCHMARK: MSCI EMERGING MARKETS - EEM)")
print(f"Metodoloji: Anormal Getiri (AR) = R_XU100 - R_MSCI_EM | Kontrol Grubu N={len(ctrl_df)}")
print(f"{'='*125}\n")

metrics = [
    ("ar_pre30", "Öncesi 30G AR"),
    ("ar_jump", "Olay Günü AR (Tepki)"),
    ("ar_post5", "Sonrası 5G AR"),
    ("ar_post30", "Sonrası 30G AR"),
]

cat_order = ["SEÇİM", "FAİZ_ARTISI", "FAİZ_INDIRIMI", "FAİZ_SABİT", "POLİTİKA_ŞOKU", "REFERANDUM", "TÜM_FAİZ_KARARLARI"]

print(f"{'Kategori':<20} | {'N':<4} | {'Metrik':<20} | {'Olay Anormal G.':>16} | {'Kontrol AR':>12} | {'Fark (Δ)':>10} | {'t-test p':>9} | {'MWU p':>9} | {'Sonuç'}")
print("=" * 125)

for cat in cat_order:
    if cat == "TÜM_FAİZ_KARARLARI":
        sub = event_ar_df[event_ar_df["category"].str.startswith("FAİZ_")]
    else:
        sub = event_ar_df[event_ar_df["category"] == cat]
    
    n_c = len(sub)
    for idx, (m_col, m_label) in enumerate(metrics):
        v_e = sub[m_col].dropna().values
        v_c = ctrl_df[m_col].dropna().values
        if len(v_e) == 0:
            continue
        m_e = float(np.mean(v_e))
        m_c = float(np.mean(v_c))
        diff = m_e - m_c
        t_stat, p_ttest = stats.ttest_ind(v_e, v_c, equal_var=False)
        u_stat, p_mwu = stats.mannwhitneyu(v_e, v_c, alternative="two-sided")
        is_sig = p_mwu < 0.05
        sig_str = "✅ ANLAMLI (p<0.05)" if is_sig else "❌ Anlamsız (Rastlantı)"
        
        prefix = f"{cat:<20} | {n_c:<4}" if idx == 0 else f"{'':<20} | {'':<4}"
        print(f"{prefix} | {m_label:<20} | %{m_e:>14.2f} | %{m_c:>10.2f} | %{diff:>8.2f} | {p_ttest:>9.4f} | {p_mwu:>9.4f} | {sig_str}")
    print("-" * 125)
