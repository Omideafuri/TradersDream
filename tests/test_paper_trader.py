"""Automated tests for virtual PaperTradingEngine."""

import pytest
from bot.paper_trader import PaperTradingEngine


def test_paper_buy_execution():
    """Verifies paper buy order: cash deducted, position established, fees recorded."""
    engine = PaperTradingEngine(initial_balance=10000.0, taker_fee=0.001)  # 0.1% for easy math
    assert engine.cash_balance == 10000.0
    assert engine.has_open_position is False

    price = 50000.0
    qty = 0.02  # Notional: $1,000
    pos = engine.execute_buy(symbol="BTCUSDT", price=price, quantity=qty)

    assert engine.has_open_position is True
    assert pos.symbol == "BTCUSDT"
    assert pos.side == "LONG"
    assert pos.quantity == 0.02
    assert pos.entry_price == 50000.0

    # Fee = $1,000 * 0.001 = $1.00
    # Deducted cash = $1,000 + $1 = $1,001
    assert pytest.approx(pos.entry_fee, rel=1e-4) == 1.00
    assert pytest.approx(engine.cash_balance, rel=1e-4) == 8999.00
    assert pytest.approx(engine.total_fees_paid, rel=1e-4) == 1.00


def test_paper_sell_execution_and_realized_pnl():
    """Verifies paper sell order: position closed, realized P&L computed, fees applied."""
    engine = PaperTradingEngine(initial_balance=10000.0, taker_fee=0.001)
    
    # 1. Buy 0.02 BTC at $50,000 ($1,000 notional, $1 fee)
    engine.execute_buy(symbol="BTCUSDT", price=50000.0, quantity=0.02)

    # 2. Sell 0.02 BTC at $55,000 ($1,100 notional, $1.10 fee)
    # Gross profit = ($55,000 - $50,000) * 0.02 = $100.00
    # Net profit = $100.00 - $1.00 (entry fee) - $1.10 (exit fee) = $97.90
    trade = engine.execute_sell(price=55000.0)

    assert engine.has_open_position is False
    assert trade.gross_pnl == 100.0
    assert pytest.approx(trade.net_pnl, rel=1e-4) == 97.90
    assert pytest.approx(engine.realized_pnl, rel=1e-4) == 97.90
    assert pytest.approx(engine.cash_balance, rel=1e-4) == 10097.90
    assert len(engine.trade_history) == 1


def test_unrealized_pnl_and_drawdown():
    """Verifies unrealized P&L calculation and peak-to-trough drawdown tracking."""
    engine = PaperTradingEngine(initial_balance=10000.0, taker_fee=0.0)

    # Buy at $50,000
    engine.execute_buy(symbol="BTCUSDT", price=50000.0, quantity=0.1)  # $5,000 notional

    # Price increases to $60,000 -> Unrealized profit +$1,000 -> Portfolio = $11,000
    engine.update_market_price(60000.0)
    snap_peak = engine.get_snapshot(60000.0)
    assert snap_peak["unrealized_pnl"] == 1000.0
    assert snap_peak["portfolio_value"] == 11000.0
    assert engine.peak_portfolio_value == 11000.0

    # Price drops to $45,000 -> Unrealized loss -$500 -> Portfolio = $9,500
    engine.update_market_price(45000.0)
    snap_trough = engine.get_snapshot(45000.0)
    assert snap_trough["unrealized_pnl"] == -500.0
    assert snap_trough["portfolio_value"] == 9500.0

    # Drawdown from $11,000 peak to $9,500 = (11,000 - 9,500) / 11,000 = 13.636%
    expected_drawdown = (11000.0 - 9500.0) / 11000.0 * 100.0
    assert pytest.approx(engine.max_drawdown_pct, rel=1e-3) == expected_drawdown
