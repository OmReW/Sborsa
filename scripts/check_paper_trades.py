import asyncio
import sys
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import yfinance as yf

# Proje kök dizinini sys.path'e ekle
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Windows konsol UTF-8 ayarı
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from config.logger import get_logger
from ingestion.market_calendar import (
    is_bist_trading_day,
    count_bist_trading_days,
    get_next_bist_trading_day,
    fetch_bist_price_safe,
)
from storage.db import DatabaseManager

logger = get_logger("paper_trades_checker")


def parse_date_safe(date_val: Any) -> Optional[date]:
    """Tarih dizgisini veya nesnesini date nesnesine çevirir."""
    if isinstance(date_val, datetime):
        return date_val.date()
    if isinstance(date_val, date):
        return date_val
    if isinstance(date_val, str):
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d.%m.%Y %H:%M:%S", "%d.%m.%Y"):
            try:
                return datetime.strptime(date_val.strip(), fmt).date()
            except ValueError:
                pass
    return None


def get_historical_price_on_trading_day(
    ticker: str, start_trade_date: date, trading_days_offset: int
) -> Optional[float]:
    """
    start_trade_date gününden sonraki N'inci işlem günündeki kapanış fiyatını çeker.
    """
    clean_ticker = ticker.split(",")[0].strip().upper()
    yf_symbol = f"{clean_ticker}.IS"

    # Tarih penceresi
    start_d = start_trade_date - timedelta(days=2)
    end_d = start_trade_date + timedelta(days=trading_days_offset * 3 + 10)

    try:
        df = yf.download(
            yf_symbol,
            start=start_d.strftime("%Y-%m-%d"),
            end=end_d.strftime("%Y-%m-%d"),
            progress=False,
        )
        if df.empty:
            return None

        df = df.sort_index()
        start_ts = pd.Timestamp(start_trade_date)
        valid_df = df[df.index >= start_ts]

        if len(valid_df) <= trading_days_offset:
            return None

        target_row = valid_df.iloc[trading_days_offset]
        col_name = "Close"
        if isinstance(target_row.name, tuple) or isinstance(df.columns, pd.MultiIndex):
            price_val = target_row[col_name][yf_symbol] if yf_symbol in target_row[col_name] else target_row[col_name].iloc[0]
        else:
            price_val = target_row[col_name]

        return float(price_val) if price_val > 0 else None

    except Exception as e:
        logger.debug(f"{ticker} için fiyat çekilemedi: {e}")
        return None


def calculate_outcome_and_pnl(
    recommendation: str,
    entry_price: float,
    exit_price: float,
    position_size: float = 10000.0,
) -> Tuple[str, float, float]:
    """
    Öneri ve fiyat hareketine göre DOĞRU/YANLIŞ sonucunu, getiri yüzdesini ve simüle P&L (TL) tutarını hesaplar.
    
    Kural:
    - AL (Long): Fiyat artarsa kâr, düşerse zarar.
      ret = (exit - entry) / entry
      pnl = position_size * ret
    - SAT (Short): Fiyat düşerse kâr, artarsa zarar.
      ret = (exit - entry) / entry
      pnl = position_size * (-ret)  [Ters çevrilmiş P&L]
    """
    if entry_price <= 0 or exit_price <= 0:
        return "BEKLEMEDE", 0.0, 0.0

    raw_ret = (exit_price - entry_price) / entry_price
    ret_pct = raw_ret * 100.0
    rec = recommendation.strip().upper()

    if rec == "AL":
        outcome = "DOĞRU" if raw_ret > 0 else "YANLIŞ"
        pnl = position_size * raw_ret
    elif rec == "SAT":
        outcome = "DOĞRU" if raw_ret < 0 else "YANLIŞ"
        pnl = position_size * (-raw_ret)  # Düşüş kâra dönüşür
    else:
        outcome = "DOĞRU" if abs(raw_ret) <= 0.01 else "YANLIŞ"
        pnl = 0.0

    return outcome, round(ret_pct, 2), round(pnl, 2)


def evaluate_outcome(recommendation: str, entry_price: float, exit_price: float) -> str:
    """Geriye dönük uyumluluk için sonuç belirleyici."""
    outcome, _, _ = calculate_outcome_and_pnl(recommendation, entry_price, exit_price)
    return outcome


def run_paper_trades_check() -> Dict[str, int]:
    """
    Bekleyen tüm Paper Trade kayıtlarını kontrol eder ve 1G / 5G sonuçlarını ve PnL'lerini günceller.
    """
    from config.settings import settings
    db = DatabaseManager()
    pending_trades = db.get_pending_paper_trades()
    position_size = getattr(settings, "SIMULATED_POSITION_SIZE", 10000.0)

    if not pending_trades:
        logger.info("ℹ️ Kontrol edilecek bekleyen Paper Trade kaydı bulunmuyor.")
        return {"checked_1d": 0, "checked_5d": 0}

    logger.info(f"🔍 {len(pending_trades)} adet bekleyen Paper Trade kaydı kontrol ediliyor...")

    today = date.today()
    updated_1d_count = 0
    updated_5d_count = 0

    for trade in pending_trades:
        trade_id = trade["id"]
        stock = trade["stock_code"]
        rec = trade["recommendation"]
        entry_price = trade["entry_price"]
        entry_dt = parse_date_safe(trade["entry_date"] or trade["recommended_at"])

        if not entry_dt:
            continue

        # Eğer entry_price eksikse şimdi tamamlamaya çalış
        if entry_price is None or entry_price <= 0:
            fetched_entry = fetch_bist_price_safe(stock, datetime.combine(entry_dt, datetime.min.time()))
            if fetched_entry:
                entry_price = fetched_entry
                with db.get_connection() as conn:
                    conn.cursor().execute("UPDATE paper_trades SET entry_price = ? WHERE id = ?;", (entry_price, trade_id))

        if not entry_price or entry_price <= 0:
            continue

        # Geçen BIST işlem günü sayısı
        elapsed_trading_days = count_bist_trading_days(entry_dt, today)

        # 1. 1 GÜNLÜK KONTROL (checked_1d == 0 ve en az 1 işlem günü geçmiş)
        if trade["checked_1d"] == 0 and elapsed_trading_days >= 1:
            p1 = get_historical_price_on_trading_day(stock, entry_dt, trading_days_offset=1)
            if p1 and p1 > 0:
                outcome_1d, ret_1d, pnl_1d = calculate_outcome_and_pnl(rec, entry_price, p1, position_size)
                db.update_paper_trade_1d(trade_id, p1, outcome_1d, pnl_1d)
                updated_1d_count += 1
                logger.info(
                    f"✅ [1G Sonuçlandı] #{trade_id} {stock} {rec} -> "
                    f"Giriş: ₺{entry_price:.2f} | 1G: ₺{p1:.2f} (%{ret_1d:+.2f}) -> {outcome_1d} | PnL: ₺{pnl_1d:+.2f}"
                )

        # 2. 5 GÜNLÜK KONTROL (checked_5d == 0 ve en az 5 işlem günü geçmiş)
        if trade["checked_5d"] == 0 and elapsed_trading_days >= 5:
            p5 = get_historical_price_on_trading_day(stock, entry_dt, trading_days_offset=5)
            if p5 and p5 > 0:
                outcome_5d, ret_5d, pnl_5d = calculate_outcome_and_pnl(rec, entry_price, p5, position_size)
                db.update_paper_trade_5d(trade_id, p5, outcome_5d, pnl_5d)
                updated_5d_count += 1
                logger.info(
                    f"✅ [5G Sonuçlandı] #{trade_id} {stock} {rec} -> "
                    f"Giriş: ₺{entry_price:.2f} | 5G: ₺{p5:.2f} (%{ret_5d:+.2f}) -> {outcome_5d} | PnL: ₺{pnl_5d:+.2f}"
                )

    logger.info(
        f"📊 Paper Trading Doğrulama Tamamlandı. "
        f"Güncellenen: 1G={updated_1d_count}, 5G={updated_5d_count}"
    )
    return {"checked_1d": updated_1d_count, "checked_5d": updated_5d_count}


if __name__ == "__main__":
    print("=" * 80)
    print("📊 Paper Trading Günlüğü Doğrulama Motoru Çalıştırılıyor...")
    print("=" * 80)
    res = run_paper_trades_check()
    print(f"Sonuç: 1 Günlük Güncellenen: {res['checked_1d']}, 5 Günlük Güncellenen: {res['checked_5d']}")
