import os
import pytest
from datetime import datetime, date, time
from pathlib import Path

from ingestion.market_calendar import (
    is_bist_trading_day,
    get_next_bist_trading_day,
    count_bist_trading_days,
    get_effective_entry_details,
)
from scripts.check_paper_trades import evaluate_outcome
from storage.db import DatabaseManager


@pytest.fixture
def temp_db(tmp_path):
    db_file = tmp_path / "test_paper_trade.db"
    db_mgr = DatabaseManager(db_path=db_file)
    return db_mgr


def test_market_calendar_weekends_and_holidays():
    # Cumartesi ve Pazar işlem günü olmamalı
    sat = date(2026, 8, 29)  # Cumartesi
    sun = date(2026, 8, 30)  # Pazar (Ayrıca 30 Ağustos Zafer Bayramı)
    assert not is_bist_trading_day(sat)
    assert not is_bist_trading_day(sun)

    # 23 Nisan 2026 Perşembe resmi tatil
    apr23 = date(2026, 4, 23)
    assert not is_bist_trading_day(apr23)

    # 29 Nisan 2026 Çarşamba normal iş günü
    apr29 = date(2026, 4, 29)
    assert is_bist_trading_day(apr29)


def test_effective_entry_details():
    # 1. Seans içi (Çarşamba saat 14:30) -> Aynı gün anlık fiyat
    dt_intraday = datetime(2026, 4, 29, 14, 30, 0)
    eff_d, is_op, note = get_effective_entry_details(dt_intraday)
    assert eff_d == date(2026, 4, 29)
    assert not is_op

    # 2. Kapanış sonrası (Çarşamba saat 18:30) -> Perşembe açılış
    dt_after_hours = datetime(2026, 4, 29, 18, 30, 0)
    eff_d2, is_op2, note2 = get_effective_entry_details(dt_after_hours)
    assert eff_d2 == date(2026, 4, 30)
    assert is_op2

    # 3. Cuma akşamı saat 19:00 -> Pazartesi açılış
    dt_friday_night = datetime(2026, 5, 8, 19, 0, 0)
    eff_d3, is_op3, note3 = get_effective_entry_details(dt_friday_night)
    assert eff_d3 == date(2026, 5, 11)  # Pazartesi
    assert is_op3


def test_evaluate_outcome():
    # AL önerisi
    assert evaluate_outcome("AL", 100.0, 105.0) == "DOĞRU"
    assert evaluate_outcome("AL", 100.0, 95.0) == "YANLIŞ"

    # SAT önerisi
    assert evaluate_outcome("SAT", 100.0, 95.0) == "DOĞRU"
    assert evaluate_outcome("SAT", 100.0, 105.0) == "YANLIŞ"


def test_calculate_outcome_and_pnl():
    from scripts.check_paper_trades import calculate_outcome_and_pnl

    # 1. AL Pozisyonu (10.000 TL): 100 -> 110 (+%10 => +1.000 TL)
    out1, ret1, pnl1 = calculate_outcome_and_pnl("AL", 100.0, 110.0, position_size=10000.0)
    assert out1 == "DOĞRU"
    assert ret1 == 10.0
    assert pnl1 == 1000.0

    # 2. AL Pozisyonu (10.000 TL): 100 -> 90 (-%10 => -1.000 TL)
    out2, ret2, pnl2 = calculate_outcome_and_pnl("AL", 100.0, 90.0, position_size=10000.0)
    assert out2 == "YANLIŞ"
    assert ret2 == -10.0
    assert pnl2 == -1000.0

    # 3. SAT Pozisyonu (10.000 TL): 100 -> 90 (Fiyat düştü, SAT doğru => +1.000 TL kâr)
    out3, ret3, pnl3 = calculate_outcome_and_pnl("SAT", 100.0, 90.0, position_size=10000.0)
    assert out3 == "DOĞRU"
    assert ret3 == -10.0
    assert pnl3 == 1000.0

    # 4. SAT Pozisyonu (10.000 TL): 100 -> 110 (Fiyat yükseldi, SAT yanlış => -1.000 TL zarar)
    out4, ret4, pnl4 = calculate_outcome_and_pnl("SAT", 100.0, 110.0, position_size=10000.0)
    assert out4 == "YANLIŞ"
    assert ret4 == 10.0
    assert pnl4 == -1000.0


def test_db_paper_trades_crud_and_deduplication(temp_db):
    # 1. İlk kayıt ekleme
    saved = temp_db.save_paper_trade(
        notification_id="NOTIF-101",
        stock_code="THYAO",
        recommendation="AL",
        confidence=4,
        reasoning="Güçlü yolcu trafiği ve kârlılık artışı.",
        entry_price=280.50,
        recommended_at="2026-08-20 14:00:00",
    )
    assert saved is True

    # 2. Mükerrer kayıt engelleme
    saved_duplicate = temp_db.save_paper_trade(
        notification_id="NOTIF-101",
        stock_code="THYAO",
        recommendation="AL",
        confidence=4,
        reasoning="Yeniden ekleme denemesi.",
        entry_price=280.50,
    )
    assert saved_duplicate is False

    # 3. Listeleme ve Detay
    trades = temp_db.get_all_paper_trades()
    assert len(trades) == 1
    assert trades[0]["stock_code"] == "THYAO"
    assert trades[0]["entry_price"] == 280.50

    detail = temp_db.get_paper_trade_detail(trades[0]["id"])
    assert detail is not None
    assert detail["stock_code"] == "THYAO"

    # 4. 1G ve 5G güncelleme (PnL ile)
    trade_id = trades[0]["id"]
    temp_db.update_paper_trade_1d(trade_id, price_1d=292.00, outcome_1d="DOĞRU", pnl_1d=410.0)
    temp_db.update_paper_trade_5d(trade_id, price_5d=305.00, outcome_5d="DOĞRU", pnl_5d=873.4)

    # 5. İstatistikler
    stats = temp_db.get_paper_trades_stats()
    assert stats["total_trades"] == 1
    assert stats["resolved_1d"] == 1
    assert stats["hit_rate_1d"] == 100.0
    assert stats["total_pnl_1d"] == 410.0
    assert stats["hit_rate_5d"] == 100.0
    assert stats["total_pnl_5d"] == 873.4
    assert stats["pending_count"] == 0


def test_portfolio_capacity_limit_and_skipped_trades(temp_db):
    """Maksimum sermaye kapasitesi dolduğunda işlemlerin skipped_trades tablosuna yönlendirilmesini test eder."""
    # 10 adet açık işlem ekle (10 * 10.000 = 100.000 TL sermaye kapasitesini doldur)
    for i in range(10):
        saved = temp_db.save_paper_trade(
            notification_id=f"CAP-TEST-{i}",
            stock_code=f"STK{i}",
            recommendation="AL",
            confidence=4,
            reasoning="Kapasite testi",
            entry_price=100.0,
        )
        assert saved is True

    # 11. işlem sermaye yetersizliği nedeniyle reddedilmeli ve skipped_trades'e kaydedilmeli
    saved_11 = temp_db.save_paper_trade(
        notification_id="CAP-TEST-11",
        stock_code="FORTE",
        recommendation="AL",
        confidence=5,
        reasoning="11. işlem sermaye aşımı",
        entry_price=50.0,
    )
    assert saved_11 is False

    with temp_db.get_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM skipped_trades;")
        skipped_count = c.fetchone()[0]
        assert skipped_count == 1


def test_heartbeat_and_portfolio_summary(temp_db):
    """Heartbeat kaydı ve get_portfolio_summary fonksiyonunu test eder."""
    temp_db.record_heartbeat()
    state = temp_db.get_system_state()
    assert state["is_active"] is True
    assert state["last_heartbeat"] is not None

    summary = temp_db.get_portfolio_summary()
    assert summary["start_capital"] == 100000.0
    assert "current_balance" in summary
    assert "positions" in summary
