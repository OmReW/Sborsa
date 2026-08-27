from datetime import datetime, date, time, timedelta
from typing import Optional, Tuple, Set, Dict, Any
import pandas as pd
import yfinance as yf

# Borsa İstanbul (BIST) Sabit ve Dini Resmi Tatilleri (2016 - 2027)
BIST_HOLIDAYS_SET: Set[str] = {
    # 2016
    "2016-01-01", "2016-04-23", "2016-05-01", "2016-05-19", "2016-07-05", "2016-07-06", "2016-07-07",
    "2016-07-15", "2016-08-30", "2016-09-12", "2016-09-13", "2016-09-14", "2016-09-15", "2016-10-29",
    # 2017
    "2017-01-01", "2017-04-23", "2017-05-01", "2017-05-19", "2017-06-25", "2017-06-26", "2017-06-27",
    "2017-07-15", "2017-08-30", "2017-09-01", "2017-09-02", "2017-09-03", "2017-09-04", "2017-10-29",
    # 2018
    "2018-01-01", "2018-04-23", "2018-05-01", "2018-05-19", "2018-06-14", "2018-06-15", "2018-06-16",
    "2018-07-15", "2018-08-20", "2018-08-21", "2018-08-22", "2018-08-23", "2018-08-24", "2018-08-30", "2018-10-29",
    # 2019
    "2019-01-01", "2019-04-23", "2019-05-01", "2019-05-19", "2019-06-04", "2019-06-05", "2019-06-06",
    "2019-07-15", "2019-08-11", "2019-08-12", "2019-08-13", "2019-08-14", "2019-08-30", "2019-10-29",
    # 2020
    "2020-01-01", "2020-04-23", "2020-05-01", "2020-05-19", "2020-05-24", "2020-05-25", "2020-05-26",
    "2020-07-15", "2020-07-31", "2020-08-01", "2020-08-02", "2020-08-03", "2020-08-30", "2020-10-29",
    # 2021
    "2021-01-01", "2021-04-23", "2021-05-01", "2021-05-12", "2021-05-13", "2021-05-14", "2021-05-19",
    "2021-07-15", "2021-07-19", "2021-07-20", "2021-07-21", "2021-07-22", "2021-07-23", "2021-08-30", "2021-10-29",
    # 2022
    "2022-01-01", "2022-04-23", "2022-05-01", "2022-05-02", "2022-05-03", "2022-05-04", "2022-05-19",
    "2022-07-08", "2022-07-09", "2022-07-10", "2022-07-11", "2022-07-12", "2022-07-15", "2022-08-30", "2022-10-29",
    # 2023
    "2023-01-01", "2023-04-20", "2023-04-21", "2023-04-22", "2023-04-23", "2023-05-01", "2023-05-19",
    "2023-06-27", "2023-06-28", "2023-06-29", "2023-06-30", "2023-07-01", "2023-07-15", "2023-08-30", "2023-10-29",
    # 2024
    "2024-01-01", "2024-04-09", "2024-04-10", "2024-04-11", "2024-04-12", "2024-04-23", "2024-05-01", "2024-05-19",
    "2024-06-15", "2024-06-16", "2024-06-17", "2024-06-18", "2024-06-19", "2024-07-15", "2024-08-30", "2024-10-29",
    # 2025
    "2025-01-01", "2025-03-29", "2025-03-30", "2025-03-31", "2025-04-01", "2025-04-23", "2025-05-01", "2025-05-19",
    "2025-06-05", "2025-06-06", "2025-06-07", "2025-06-08", "2025-06-09", "2025-07-15", "2025-08-30", "2025-10-29",
    # 2026
    "2026-01-01", "2026-03-19", "2026-03-20", "2026-03-21", "2026-03-22", "2026-04-23", "2026-05-01", "2026-05-19",
    "2026-05-26", "2026-05-27", "2026-05-28", "2026-05-29", "2026-07-15", "2026-08-30", "2026-10-29",
}

MARKET_OPEN_TIME = time(9, 55)
MARKET_CLOSE_TIME = time(18, 10)


def is_bist_trading_day(target_date: date) -> bool:
    """
    Belirtilen tarihin Borsa İstanbul işlem günü olup olmadığını kontrol eder.
    Hafta sonu (Cumartesi, Pazar) ve resmi tatilleri eler.
    """
    if target_date.weekday() >= 5:  # Cumartesi = 5, Pazar = 6
        return False
    date_str = target_date.strftime("%Y-%m-%d")
    return date_str not in BIST_HOLIDAYS_SET


def get_next_bist_trading_day(start_date: date) -> date:
    """
    Belirtilen tarihten sonraki ilk BIST işlem gününü döner.
    """
    cur = start_date + timedelta(days=1)
    while not is_bist_trading_day(cur):
        cur += timedelta(days=1)
    return cur


def count_bist_trading_days(start_date: date, end_date: date) -> int:
    """
    İki tarih arasındaki toplam BIST işlem günü sayısını hesaplar.
    """
    if start_date >= end_date:
        return 0
    cur = start_date + timedelta(days=1)
    trading_days = 0
    while cur <= end_date:
        if is_bist_trading_day(cur):
            trading_days += 1
        cur += timedelta(days=1)
    return trading_days


def get_effective_entry_details(pub_dt: datetime) -> Tuple[date, bool, str]:
    """
    Bildirim tarihine ve saatine göre geçerli işlem gününü ve notu hesaplar.
    
    Kural:
    - Bildirim işlem saatlerinde (10:00 - 18:00) ve işlem gününde gelmişse:
      İşlem Günü = O Gün (Anlık piyasa fiyatı ile giriş)
    - Bildirim 18:00'dan sonra, hafta sonu veya tatilde gelmişse:
      İşlem Günü = Bir sonraki BIST işlem günü (Açılış/ilk seans fiyatı ile giriş)
    """
    pub_date = pub_dt.date()
    pub_time = pub_dt.time()

    if is_bist_trading_day(pub_date) and MARKET_OPEN_TIME <= pub_time <= MARKET_CLOSE_TIME:
        return pub_date, False, "Seans İçi (Anlık Piyasa Fiyatı)"
    
    # Kapanış sonrası veya tatil günü
    if is_bist_trading_day(pub_date) and pub_time < MARKET_OPEN_TIME:
        # Aynı gün açılışı beklenir
        return pub_date, True, "Seans Öncesi (Aynı Gün Açılış Fiyatı)"
    else:
        # 18:00 sonrası veya tatil -> Ertesi işlem günü açılışı
        next_trading_day = get_next_bist_trading_day(pub_date)
        return next_trading_day, True, f"Kapanış Sonrası ({next_trading_day.strftime('%d.%m.%Y')} Açılış Fiyatı)"


def fetch_bist_price_safe(
    ticker: str,
    target_dt: Optional[datetime] = None,
    is_opening: bool = False,
) -> Optional[float]:
    """
    yfinance üzerinden BIST hisse fiyatını güvenli şekilde çeker.
    
    - target_dt None ise: En güncel anlık son fiyatı çeker.
    - target_dt belirtilmişse: O tarihteki 'Open' (is_opening=True) veya 'Close' fiyatını çeker.
    """
    clean_ticker = ticker.split(",")[0].strip().upper()
    yf_symbol = f"{clean_ticker}.IS"

    try:
        if target_dt is None:
            # Anlık son fiyat
            tk = yf.Ticker(yf_symbol)
            fast_info = getattr(tk, "fast_info", None)
            if fast_info and hasattr(fast_info, "last_price") and fast_info.last_price:
                return float(fast_info.last_price)
            
            hist = tk.history(period="5d")
            if not hist.empty:
                return float(hist["Close"].iloc[-1])
            return None

        # Tarihsel gün fiyatı
        start_d = target_dt.date() - timedelta(days=3)
        end_d = target_dt.date() + timedelta(days=5)

        df = yf.download(
            yf_symbol,
            start=start_d.strftime("%Y-%m-%d"),
            end=end_d.strftime("%Y-%m-%d"),
            progress=False,
        )
        if df.empty:
            return None

        df = df.sort_index()
        target_ts = pd.Timestamp(target_dt.date())
        matched = df[df.index >= target_ts]

        if matched.empty:
            return None

        col_name = "Open" if is_opening else "Close"
        if isinstance(matched.columns, pd.MultiIndex):
            price_val = matched[col_name][yf_symbol].iloc[0] if yf_symbol in matched[col_name] else matched[col_name].iloc[0, 0]
        else:
            price_val = matched[col_name].iloc[0]

        return float(price_val) if price_val > 0 else None

    except Exception:
        return None
