import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, Request, Query
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse

# Proje kök dizinini sys.path'e ekle
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from storage.db import db
from config.settings import settings

app = FastAPI(title="Borsa-AI Dashboard", version="2.0.0")

# Şablon yöneticisi
templates = Jinja2Templates(directory=str(BASE_DIR / "dashboard" / "templates"))


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """
    Ana Dashboard Sayfası: Bildirimler, AI Önerileri, Paper Trading Günlüğü ve Portföy Simülasyonu.
    """
    stats = db.get_stats()
    paper_stats = db.get_paper_trades_stats()
    portfolio_summary = db.get_portfolio_summary()
    recent_notifications = db.get_recent_notifications(limit=25)
    recent_recommendations = db.get_recent_recommendations(limit=25)
    paper_trades = db.get_all_paper_trades(limit=50)

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "stats": stats,
            "paper_stats": paper_stats,
            "portfolio": portfolio_summary,
            "notifications": recent_notifications,
            "recommendations": recent_recommendations,
            "paper_trades": paper_trades,
            "watchlist": settings.watchlist,
            "model_name": settings.OLLAMA_MODEL,
        },
    )


@app.get("/api/portfolio-summary")
async def get_portfolio_summary():
    """Portföy simülasyonu, açık/kapalı pozisyonlar ve BIST100 kıyaslama API'si."""
    return JSONResponse(db.get_portfolio_summary())


@app.get("/api/system-state")
async def get_system_state():
    """Sistem çalışma süresi ve canlılık durumu API'si."""
    return JSONResponse(db.get_system_state())


@app.get("/api/stats")
async def get_stats():
    """Genel sistem istatistikleri API'si."""
    return JSONResponse(db.get_stats())


@app.get("/api/paper-trades/stats")
async def get_paper_trades_stats():
    """Paper trading istatistik özeti API'si."""
    return JSONResponse(db.get_paper_trades_stats())


@app.get("/api/paper-trades")
async def get_paper_trades(limit: int = Query(default=50, ge=1, le=200)):
    """Tüm paper trading kayıtları API'si."""
    return JSONResponse(db.get_all_paper_trades(limit=limit))


@app.get("/api/paper-trades/{trade_id}")
async def get_paper_trade_detail(trade_id: int):
    """Tek bir paper trade işleminin tam detay API'si."""
    detail = db.get_paper_trade_detail(trade_id)
    if not detail:
        return JSONResponse({"error": "İşlem bulunamadı"}, status_code=404)
    return JSONResponse(detail)


@app.get("/api/recommendations")
async def get_recommendations(
    limit: int = Query(default=50, ge=1, le=200),
    filter_type: Optional[str] = Query(default=None, pattern="^(AL|SAT|NÖTR)$"),
):
    """Yapay zeka analiz önerileri API'si."""
    recs = db.get_recent_recommendations(limit=limit, recommendation_filter=filter_type)
    return JSONResponse(recs)


def parse_flexible_datetime(raw_date: Optional[str]) -> Optional[datetime]:
    """Farklı formatlardaki tarih dizgilerini güvenle datetime nesnesine dönüştürür."""
    if not raw_date or not str(raw_date).strip():
        return None
    cleaned = str(raw_date).strip().split()[0]
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%Y/%m/%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            pass
    return None


@app.get("/api/chart-data/{stock_code}")
async def get_chart_data(
    stock_code: str,
    from_date: Optional[str] = Query(default=None),
    entry_price: Optional[float] = Query(default=None),
):
    """
    Belirtilen hissenin bildirim tarihi etrafındaki ~15-20 iş günlük fiyat grafiği verisini döner.
    """
    import yfinance as yf
    import pandas as pd
    from datetime import timedelta
    from config.logger import get_logger

    logger = get_logger("dashboard_chart")
    clean_ticker = stock_code.split(",")[0].strip().upper()
    yf_symbol = f"{clean_ticker}.IS"

    try:
        base_dt = parse_flexible_datetime(from_date)
        if base_dt:
            start_d = base_dt - timedelta(days=12)
            end_d = base_dt + timedelta(days=25)
            logger.info(
                f"[ChartData] {yf_symbol} için tarihsel veri çekiliyor: "
                f"Start={start_d.strftime('%Y-%m-%d')}, End={end_d.strftime('%Y-%m-%d')} (Baz Tarih={from_date})"
            )
            df = yf.download(
                yf_symbol,
                start=start_d.strftime("%Y-%m-%d"),
                end=end_d.strftime("%Y-%m-%d"),
                progress=False,
            )
        else:
            logger.info(f"[ChartData] {yf_symbol} için son 1 aylık güncel veri çekiliyor.")
            tk = yf.Ticker(yf_symbol)
            df = tk.history(period="1mo")

        if df is None or df.empty:
            logger.warning(f"[ChartData] {yf_symbol} için yfinance boş DataFrame döndü.")
            return JSONResponse({"dates": [], "prices": [], "error": "Fiyat verisi bulunamadı"})

        df = df.sort_index()
        dates_list = [d.strftime("%d.%m.%Y") for d in df.index]

        col_name = "Close"
        if isinstance(df.columns, pd.MultiIndex):
            prices_series = df[col_name][yf_symbol] if yf_symbol in df[col_name] else df[col_name].iloc[:, 0]
        else:
            prices_series = df[col_name]

        prices_list = [round(float(p), 2) for p in prices_series]

        logger.info(f"[ChartData] {yf_symbol} için {len(prices_list)} adet fiyat noktası başarıyla hazırlandı.")
        return JSONResponse({
            "stock_code": clean_ticker,
            "dates": dates_list,
            "prices": prices_list,
            "entry_date": from_date,
            "entry_price": entry_price,
        })

    except Exception as e:
        logger.error(f"[ChartData] {yf_symbol} fiyat grafiği çekilirken hata oluştu: {e}", exc_info=True)
        return JSONResponse({"dates": [], "prices": [], "error": str(e)})


@app.get("/api/fundamentals/{stock_code}")
async def get_fundamentals(stock_code: str):
    """
    Belirtilen BIST hissesinin F/K, PD/DD, Piyasa Değeri ve son bilanço dönemi temel verilerini döner.
    """
    import borsapy as bp
    from config.logger import get_logger

    logger = get_logger("dashboard_fundamentals")
    clean_ticker = stock_code.split(",")[0].strip().upper()

    try:
        ticker = bp.Ticker(clean_ticker)
        fast_info = ticker.fast_info.todict() if hasattr(ticker.fast_info, "todict") else {}

        # Son Bilanço Dönemi ve Bilanço Özeti
        latest_period = None
        balance_summary = {}
        try:
            bs = ticker.balance_sheet
            if bs is not None and not bs.empty:
                latest_period = str(bs.columns[0])
                for idx in bs.index:
                    clean_idx = idx.strip()
                    if clean_idx in ("Dönem Net Kar/Zararı", "Net Dönem Karı/Zararı", "Dönem Net Karı/Zararı"):
                        balance_summary["net_profit"] = float(bs.iloc[bs.index.get_loc(idx), 0])
                    elif clean_idx in ("TOPLAM KAYNAKLAR", "Toplam Varlıklar", "TOPLAM VARLIKLAR"):
                        balance_summary["total_assets"] = float(bs.iloc[bs.index.get_loc(idx), 0])
                    elif clean_idx in ("Özkaynaklar", "TOPLAM ÖZKAYNAKLAR", "Öz Sermaye"):
                        balance_summary["total_equity"] = float(bs.iloc[bs.index.get_loc(idx), 0])
        except Exception as b_err:
            logger.debug(f"{clean_ticker} bilanço özeti ayrıştırılamadı: {b_err}")

        # Piyasa Değeri Formatı (Milyar / Milyon TL)
        mcap = fast_info.get("market_cap")
        if not mcap and fast_info.get("shares") and fast_info.get("last_price"):
            mcap = float(fast_info["shares"]) * float(fast_info["last_price"])
        if not mcap:
            try:
                import yfinance as yf
                yf_mcap = getattr(yf.Ticker(f"{clean_ticker}.IS").fast_info, "market_cap", None)
                if yf_mcap:
                    mcap = float(yf_mcap)
            except Exception:
                pass

        mcap_formatted = None
        if mcap:
            if mcap >= 1_000_000_000:
                mcap_formatted = f"₺{mcap / 1_000_000_000:.2f} Mr"
            elif mcap >= 1_000_000:
                mcap_formatted = f"₺{mcap / 1_000_000:.2f} Mn"
            else:
                mcap_formatted = f"₺{mcap:,.0f}"

        res_data = {
            "stock_code": clean_ticker,
            "pe_ratio": fast_info.get("pe_ratio"),
            "pb_ratio": fast_info.get("pb_ratio"),
            "market_cap": mcap,
            "market_cap_formatted": mcap_formatted,
            "free_float": fast_info.get("free_float"),
            "foreign_ratio": fast_info.get("foreign_ratio"),
            "last_price": fast_info.get("last_price"),
            "year_high": fast_info.get("year_high"),
            "year_low": fast_info.get("year_low"),
            "latest_balance_period": latest_period or "Bilinmiyor",
            "balance_summary": balance_summary,
            "currency": fast_info.get("currency", "TRY"),
            "status": "success",
        }
        return JSONResponse(res_data)

    except Exception as e:
        logger.error(f"[Fundamentals] {clean_ticker} temel analiz verisi çekilirken hata: {e}", exc_info=True)
        return JSONResponse({
            "stock_code": clean_ticker,
            "error": "Temel analiz verisi çekilemedi",
            "status": "error",
        })


@app.get("/api/notifications")
async def get_notifications(
    limit: int = Query(default=50, ge=1, le=200),
    stock_code: Optional[str] = None,
):
    """KAP bildirimleri API'si."""
    notifs = db.get_recent_notifications(limit=limit, stock_code=stock_code)
    return JSONResponse(notifs)


@app.post("/api/portfolio/reset")
async def reset_portfolio():
    """
    Portföy simülasyonunu ve paper trading günlüğünü sıfırlar (100.000 TL başlangıç kasası).
    """
    result = db.reset_paper_trading_simulation()
    return JSONResponse(result)

