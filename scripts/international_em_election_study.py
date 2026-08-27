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

# --------------------------------------------------------------------------
# GELİŞMEKTE OLAN PİYASALAR (EM) 2004 - 2024 SEÇİM VERİTABANI
# --------------------------------------------------------------------------
EM_ELECTIONS = [
    # 🇧🇷 Brezilya (Bovespa - ^BVSP)
    {"country": "Brezilya", "ticker": "^BVSP", "date": "2006-10-01", "title": "2006 Brezilya Genel Seçimleri (1. Tur)"},
    {"country": "Brezilya", "ticker": "^BVSP", "date": "2006-10-29", "title": "2006 Brezilya Başkanlık (2. Tur - Lula)"},
    {"country": "Brezilya", "ticker": "^BVSP", "date": "2010-10-03", "title": "2010 Brezilya Genel Seçimleri (1. Tur)"},
    {"country": "Brezilya", "ticker": "^BVSP", "date": "2010-10-31", "title": "2010 Brezilya Başkanlık (2. Tur - Rousseff)"},
    {"country": "Brezilya", "ticker": "^BVSP", "date": "2014-10-05", "title": "2014 Brezilya Genel Seçimleri (1. Tur)"},
    {"country": "Brezilya", "ticker": "^BVSP", "date": "2014-10-26", "title": "2014 Brezilya Başkanlık (2. Tur - Rousseff)"},
    {"country": "Brezilya", "ticker": "^BVSP", "date": "2018-10-07", "title": "2018 Brezilya Genel Seçimleri (1. Tur)"},
    {"country": "Brezilya", "ticker": "^BVSP", "date": "2018-10-28", "title": "2018 Brezilya Başkanlık (2. Tur - Bolsonaro)"},
    {"country": "Brezilya", "ticker": "^BVSP", "date": "2022-10-02", "title": "2022 Brezilya Genel Seçimleri (1. Tur)"},
    {"country": "Brezilya", "ticker": "^BVSP", "date": "2022-10-30", "title": "2022 Brezilya Başkanlık (2. Tur - Lula)"},
    
    # 🇲🇽 Meksika (IPC Mexico - ^MXX)
    {"country": "Meksika", "ticker": "^MXX", "date": "2006-07-02", "title": "2006 Meksika Genel Seçimleri (Calderon)"},
    {"country": "Meksika", "ticker": "^MXX", "date": "2012-07-01", "title": "2012 Meksika Genel Seçimleri (Pena Nieto)"},
    {"country": "Meksika", "ticker": "^MXX", "date": "2018-07-01", "title": "2018 Meksika Genel Seçimleri (AMLO)"},
    {"country": "Meksika", "ticker": "^MXX", "date": "2024-06-02", "title": "2024 Meksika Genel Seçimleri (Sheinbaum)"},

    # 🇿🇦 Güney Afrika (FTSE/JSE All Share - ^J203.JO)
    {"country": "Güney Afrika", "ticker": "^J203.JO", "date": "2004-04-14", "title": "2004 Güney Afrika Genel Seçimleri"},
    {"country": "Güney Afrika", "ticker": "^J203.JO", "date": "2009-04-22", "title": "2009 Güney Afrika Genel Seçimleri (Zuma)"},
    {"country": "Güney Afrika", "ticker": "^J203.JO", "date": "2014-05-07", "title": "2014 Güney Afrika Genel Seçimleri (Zuma)"},
    {"country": "Güney Afrika", "ticker": "^J203.JO", "date": "2019-05-08", "title": "2019 Güney Afrika Genel Seçimleri (Ramaphosa)"},
    {"country": "Güney Afrika", "ticker": "^J203.JO", "date": "2024-05-29", "title": "2024 Güney Afrika Genel Seçimleri (Koalisyon)"},

    # 🇮🇳 Hindistan (BSE Sensex - ^BSESN)
    {"country": "Hindistan", "ticker": "^BSESN", "date": "2004-05-13", "title": "2004 Hindistan Genel Seçimleri (Singh)"},
    {"country": "Hindistan", "ticker": "^BSESN", "date": "2009-05-16", "title": "2009 Hindistan Genel Seçimleri (UPA II)"},
    {"country": "Hindistan", "ticker": "^BSESN", "date": "2014-05-16", "title": "2014 Hindistan Genel Seçimleri (Modi I)"},
    {"country": "Hindistan", "ticker": "^BSESN", "date": "2019-05-23", "title": "2019 Hindistan Genel Seçimleri (Modi II)"},
    {"country": "Hindistan", "ticker": "^BSESN", "date": "2024-06-04", "title": "2024 Hindistan Genel Seçimleri (Modi III)"},
]


def run_international_study():
    tickers = list(set([e["ticker"] for e in EM_ELECTIONS]))
    print(f"⏳ Uluslararası EM endeks verileri indiriliyor ({', '.join(tickers)})...")
    raw_df = yf.download(tickers, start="2003-01-01", end="2026-08-27", progress=False)

    price_dict = {}
    for t in tickers:
        if isinstance(raw_df.columns, pd.MultiIndex):
            s = raw_df["Close"][t].dropna() if t in raw_df["Close"] else pd.Series(dtype=float)
        else:
            s = raw_df["Close"].dropna()
        s.index = pd.to_datetime(s.index).tz_localize(None)
        price_dict[t] = s.sort_index()

    # 1. Gerçek Seçim Olayları Hesaplama
    election_results = []
    for ev in EM_ELECTIONS:
        t = ev["ticker"]
        series = price_dict.get(t)
        if series is None or series.empty:
            continue
        ev_dt = pd.Timestamp(ev["date"])
        pre = series[series.index <= ev_dt]
        post = series[series.index >= ev_dt]
        if len(pre) < 25 or len(post) < 25:
            continue
        
        p0 = float(post.iloc[0])
        p_m1 = float(pre.iloc[-2]) if len(pre) >= 2 else float(pre.iloc[-1])
        p_pre30 = float(pre.iloc[-22])
        p_p1 = float(post.iloc[1]) if len(post) >= 2 else p0
        p_p5 = float(post.iloc[min(5, len(post)-1)])
        p_p30 = float(post.iloc[min(22, len(post)-1)])

        election_results.append({
            "country": ev["country"],
            "ticker": ev["ticker"],
            "date": ev["date"],
            "title": ev["title"],
            "pre_30d": ((p0 - p_pre30) / p_pre30) * 100.0,
            "jump": ((p_p1 - p_m1) / p_m1) * 100.0,
            "post_5d": ((p_p5 - p0) / p0) * 100.0,
            "post_30d": ((p_p30 - p0) / p0) * 100.0,
        })
    el_df = pd.DataFrame(election_results)

    # 2. Uluslararası Kontrol Grubu (Her ülke için seçim dışı rastgele 50'şer tarih = Toplam 200 tarih)
    random.seed(42)
    ctrl_results = []
    for t in tickers:
        series = price_dict.get(t)
        if series is None or series.empty:
            continue
        el_dates = set([pd.Timestamp(e["date"]).date() for e in EM_ELECTIONS if e["ticker"] == t])
        valid = [d.date() for d in series.loc["2004-01-01":"2024-12-31"].index]
        cand = [d for d in valid if all(abs((d - ed).days) > 10 for ed in el_dates)]
        sample = random.sample(cand, min(50, len(cand)))
        for sd in sample:
            ts = pd.Timestamp(sd)
            pre = series[series.index <= ts]
            post = series[series.index >= ts]
            if len(pre) < 25 or len(post) < 25:
                continue
            p0 = float(post.iloc[0])
            p_m1 = float(pre.iloc[-2]) if len(pre) >= 2 else float(pre.iloc[-1])
            p_pre30 = float(pre.iloc[-22])
            p_p1 = float(post.iloc[1]) if len(post) >= 2 else p0
            p_p5 = float(post.iloc[min(5, len(post)-1)])
            p_p30 = float(post.iloc[min(22, len(post)-1)])

            ctrl_results.append({
                "ticker": t,
                "pre_30d": ((p0 - p_pre30) / p_pre30) * 100.0,
                "jump": ((p_p1 - p_m1) / p_m1) * 100.0,
                "post_5d": ((p_p5 - p0) / p0) * 100.0,
                "post_30d": ((p_p30 - p0) / p0) * 100.0,
            })
    ctrl_df = pd.DataFrame(ctrl_results)

    print(f"\n{'='*125}")
    print("2. ULUSLARARASI GELİŞMEKTE OLAN PİYASALAR (EM) SEÇİM ÇALIŞMASI (2004-2024)")
    print(f"Örneklem: Brezilya (BVSP), Meksika (MXX), Güney Afrika (JALSH), Hindistan (Sensex) | Toplam N={len(el_df)} Seçim vs N={len(ctrl_df)} Kontrol")
    print(f"{'='*125}\n")

    metrics = [
        ("pre_30d", "Öncesi 30G"),
        ("jump", "Olay Günü Tepkisi"),
        ("post_5d", "Sonrası 5G"),
        ("post_30d", "Sonrası 30G"),
    ]

    countries = ["Brezilya", "Meksika", "Güney Afrika", "Hindistan", "TÜM_EM_HAVUZU"]

    print(f"{'Ülke / Grup':<18} | {'N':<4} | {'Metrik':<18} | {'Seçim Getirisi':>15} | {'Kontrol Getirisi':>16} | {'Fark (Δ)':>10} | {'t-test p':>9} | {'MWU p':>9} | {'Sonuç'}")
    print("=" * 125)

    for country in countries:
        if country == "TÜM_EM_HAVUZU":
            sub_e = el_df
            sub_c = ctrl_df
        else:
            sub_e = el_df[el_df["country"] == country]
            t = sub_e["ticker"].iloc[0] if not sub_e.empty else ""
            sub_c = ctrl_df[ctrl_df["ticker"] == t]

        n_e = len(sub_e)
        for idx, (m_col, m_label) in enumerate(metrics):
            v_e = sub_e[m_col].dropna().values
            v_c = sub_c[m_col].dropna().values
            if len(v_e) == 0:
                continue
            m_e = float(np.mean(v_e))
            m_c = float(np.mean(v_c))
            diff = m_e - m_c
            t_stat, p_ttest = stats.ttest_ind(v_e, v_c, equal_var=False)
            u_stat, p_mwu = stats.mannwhitneyu(v_e, v_c, alternative="two-sided")
            is_sig = p_mwu < 0.05
            sig_str = "✅ ANLAMLI (p<0.05)" if is_sig else "❌ Anlamsız (Rastlantı)"

            prefix = f"{country:<18} | {n_e:<4}" if idx == 0 else f"{'':<18} | {'':<4}"
            print(f"{prefix} | {m_label:<18} | %{m_e:>13.2f} | %{m_c:>14.2f} | %{diff:>8.2f} | {p_ttest:>9.4f} | {p_mwu:>9.4f} | {sig_str}")
        print("-" * 125)


if __name__ == "__main__":
    run_international_study()
