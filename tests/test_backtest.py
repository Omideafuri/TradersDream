"""Automated tests for Phase 2 Historical Backtesting System.

Verifies:
1. No look-ahead bias
2. Forward-return calculation
3. LONG return calculation
4. SHORT return calculation
5. Confidence bucketing
6. Fee calculation
7. Slippage calculation
8. Position-size limit
9. Daily loss limit
10. Maximum drawdown
11. Chronological walk-forward split
12. Backtest reproducibility
"""

import pytest
import numpy as np
import pandas as pd

from backtest.dataset import DatasetManager, HistoricalDecision
from backtest.forward_returns import (
    calculate_directional_return,
    calculate_forward_returns,
    analyze_confidence_buckets,
)
from backtest.engine import BacktestEngine, BacktestConfig
from backtest.metrics import compute_metrics
from backtest.walk_forward import chronological_split


def test_no_look_ahead_bias():
    """Verifies that indicators at candle t depend exclusively on historical data up to t.
    
    Appending future candles must NOT alter prior indicator values.
    """
    history_initial = DatasetManager.generate_synthetic_history(count=100, seed=42)
    history_extended = DatasetManager.generate_synthetic_history(count=200, seed=42)

    # First 100 rows of extended are identical to initial
    pd.testing.assert_frame_equal(history_initial, history_extended.iloc[:100])

    ind_initial = DatasetManager.compute_causal_indicators(history_initial)
    ind_extended = DatasetManager.compute_causal_indicators(history_extended)

    # Values at index 50 must match exactly
    for col in ["ema20", "ema50", "ema200", "rsi14", "atr14", "volume_ratio"]:
        val_init = ind_initial[col].iloc[50]
        val_ext = ind_extended[col].iloc[50]
        assert pytest.approx(val_init, rel=1e-5) == val_ext, f"Look-ahead detected in column {col}"


def test_long_return_formula():
    """Verifies standard LONG return formula: (future_price / entry_price) - 1."""
    entry = 50000.0
    future = 55000.0
    expected = (55000.0 / 50000.0) - 1.0  # +10.0%
    actual = calculate_directional_return("LONG", entry, future)
    assert pytest.approx(actual, rel=1e-5) == expected
    assert pytest.approx(actual, rel=1e-5) == 0.10


def test_short_return_formula():
    """Verifies standard SHORT return formula: (entry_price / future_price) - 1."""
    entry = 50000.0
    future = 40000.0
    expected = (50000.0 / 40000.0) - 1.0  # +25.0%
    actual = calculate_directional_return("SHORT", entry, future)
    assert pytest.approx(actual, rel=1e-5) == expected
    assert pytest.approx(actual, rel=1e-5) == 0.25

    # Loss scenario: price goes up
    future_up = 60000.0
    expected_loss = (50000.0 / 60000.0) - 1.0  # -16.67%
    actual_loss = calculate_directional_return("SHORT", entry, future_up)
    assert pytest.approx(actual_loss, rel=1e-5) == expected_loss


def test_forward_return_calculation():
    """Verifies forward returns correctly offset across 5m, 15m, 30m, 1h, 4h."""
    candles = pd.DataFrame({
        "timestamp": [1000 + i * 300000 for i in range(50)],  # 50 5m candles
        "open": [100.0 + i for i in range(50)],
        "high": [101.0 + i for i in range(50)],
        "low": [99.0 + i for i in range(50)],
        "close": [100.0 + i for i in range(50)],
        "volume": [10.0] * 50,
    })

    decisions = [
        HistoricalDecision(
            timestamp=1000,
            symbol="BTCUSDT",
            timeframe="5m",
            price=100.0,
            action="LONG",
            confidence=0.8,
            prob_hold=0.1,
            prob_long=0.8,
            prob_short=0.1,
        )
    ]

    df_fwd = calculate_forward_returns(candles, decisions)
    # At index 0 (price=100):
    # 5m (offset 1): close at index 1 is 101.0 -> return is (101/100) - 1 = +1%
    # 15m (offset 3): close at index 3 is 103.0 -> return is (103/100) - 1 = +3%
    # 30m (offset 6): close at index 6 is 106.0 -> return is (106/100) - 1 = +6%
    # 1h (offset 12): close at index 12 is 112.0 -> return is (112/100) - 1 = +12%
    # 4h (offset 48): close at index 48 is 148.0 -> return is (148/100) - 1 = +48%
    assert pytest.approx(df_fwd["fwd_ret_5m"].iloc[0], rel=1e-4) == 0.01
    assert pytest.approx(df_fwd["fwd_ret_15m"].iloc[0], rel=1e-4) == 0.03
    assert pytest.approx(df_fwd["fwd_ret_30m"].iloc[0], rel=1e-4) == 0.06
    assert pytest.approx(df_fwd["fwd_ret_1h"].iloc[0], rel=1e-4) == 0.12
    assert pytest.approx(df_fwd["fwd_ret_4h"].iloc[0], rel=1e-4) == 0.48


def test_confidence_bucketing():
    """Verifies decisions partition accurately into confidence ranges [0.50-0.59] through [0.90-1.00]."""
    test_data = pd.DataFrame({
        "timestamp": [1, 2, 3, 4, 5],
        "action": ["LONG", "LONG", "SHORT", "HOLD", "LONG"],
        "confidence": [0.55, 0.65, 0.75, 0.85, 0.95],
        "fwd_ret_15m": [0.02, -0.01, 0.05, 0.0, 0.10],
    })

    buckets = analyze_confidence_buckets(test_data, horizon="15m")
    bucket_map = {b.bucket_range: b for b in buckets}

    assert bucket_map["0.50-0.59"].total_count == 1
    assert bucket_map["0.50-0.59"].win_rate == 100.0
    assert bucket_map["0.60-0.69"].win_rate == 0.0  # negative return
    assert bucket_map["0.70-0.79"].short_count == 1
    assert bucket_map["0.80-0.89"].hold_count == 1
    assert bucket_map["0.90-1.00"].avg_return_pct == 10.0


def test_fee_calculation():
    """Verifies trading fee calculation on entry and exit."""
    cfg = BacktestConfig(initial_balance=10000.0, fee_rate=0.001, slippage_rate=0.0)  # 0.1% fee
    engine = BacktestEngine(cfg)

    # 2 candles flat
    candles = pd.DataFrame({
        "timestamp": [1000, 2000],
        "open": [100.0, 100.0],
        "high": [100.0, 100.0],
        "low": [100.0, 100.0],
        "close": [100.0, 100.0],
        "volume": [10.0, 10.0],
    })
    decisions = [
        HistoricalDecision(1000, "BTCUSDT", "5m", 100.0, "LONG", 0.9, 0.1, 0.9, 0.0),
    ]

    res = engine.run(candles, decisions)
    assert len(res.trades) == 1
    trade = res.trades[0]
    # Trade notional is ~10% of $10,000 = $1,000
    # Entry fee ~ $1.00, Exit fee ~ $1.00, Total fees ~ $2.00
    assert trade.entry_fee > 0.0
    assert trade.exit_fee > 0.0
    assert pytest.approx(trade.entry_fee + trade.exit_fee, rel=1e-2) == res.metrics.total_fees


def test_slippage_calculation():
    """Verifies that execution slippage degrades fill prices adversely."""
    cfg = BacktestConfig(slippage_rate=0.01)  # 1% slippage for prominent test
    engine = BacktestEngine(cfg)

    candles = pd.DataFrame({
        "timestamp": [1000, 2000],
        "open": [100.0, 100.0],
        "high": [100.0, 100.0],
        "low": [100.0, 100.0],
        "close": [100.0, 100.0],
        "volume": [10.0, 10.0],
    })
    decisions = [
        HistoricalDecision(1000, "BTCUSDT", "5m", 100.0, "LONG", 0.9, 0.1, 0.9, 0.0),
    ]

    res = engine.run(candles, decisions)
    trade = res.trades[0]
    # Raw entry 100.0, Fill entry for LONG with 1% slippage = 101.0
    assert pytest.approx(trade.entry_price_fill, rel=1e-4) == 101.0
    # Raw exit 100.0, Fill exit for LONG with 1% slippage = 99.0
    assert pytest.approx(trade.exit_price_fill, rel=1e-4) == 99.0
    assert trade.slippage_cost > 0.0


def test_position_size_limit():
    """Verifies that no trade ever exceeds the 10% maximum portfolio allocation."""
    cfg = BacktestConfig(initial_balance=10000.0, max_position_size=0.10)
    engine = BacktestEngine(cfg)

    candles = pd.DataFrame({
        "timestamp": [1000, 2000],
        "open": [50000.0, 50000.0],
        "high": [50000.0, 50000.0],
        "low": [50000.0, 50000.0],
        "close": [50000.0, 50000.0],
        "volume": [10.0, 10.0],
    })
    decisions = [
        HistoricalDecision(1000, "BTCUSDT", "5m", 50000.0, "LONG", 0.95, 0.05, 0.95, 0.0),
    ]

    res = engine.run(candles, decisions)
    trade = res.trades[0]
    notional = trade.quantity * trade.entry_price_fill
    # Max allowed notional is 10% of $10,000 = $1,000
    assert notional <= 1000.0 + 1e-4


def test_daily_loss_limit():
    """Verifies that daily loss >= limit halts new entries for the remainder of that day."""
    cfg = BacktestConfig(
        initial_balance=10000.0,
        max_daily_loss=0.005,  # 0.5% = $50 limit for this test
        stop_loss_pct=0.05,    # 5% SL on $1000 position = ~$52 loss
        take_profit_pct=0.10,  # 10% TP
    )
    engine = BacktestEngine(cfg)

    base_ts = 1704067200000  # 2024-01-01 00:00:00 UTC
    candles = pd.DataFrame({
        "timestamp": [base_ts + i * 300000 for i in range(5)],
        "open":  [100.0, 90.0, 90.0, 90.0, 90.0],
        "high":  [100.0, 90.0, 90.0, 90.0, 90.0],
        "low":   [100.0, 80.0, 80.0, 80.0, 80.0],  # Drops to 80, hitting SL
        "close": [100.0, 80.0, 80.0, 80.0, 80.0],
        "volume": [10.0] * 5,
    })

    # Trade 1 at base_ts enters at 100.0
    # Next candle low is 80.0, triggering stop loss (-20% on position, > 2% daily loss on portfolio)
    # Trade 2 at base_ts + 600000 should be rejected by the daily loss limit
    decisions = [
        HistoricalDecision(base_ts, "BTCUSDT", "5m", 100.0, "LONG", 0.9, 0.0, 0.9, 0.1),
        HistoricalDecision(base_ts + 600000, "BTCUSDT", "5m", 80.0, "LONG", 0.9, 0.0, 0.9, 0.1),
    ]

    res = engine.run(candles, decisions)
    # Trade 2 should be rejected because daily loss limit was reached by Trade 1
    assert len(res.trades) == 1
    assert res.trades[0].exit_reason == "STOP_LOSS"


def test_max_drawdown_calculation():
    """Verifies accurate peak-to-trough drawdown calculation."""
    # Equity sequence: 100 -> 120 (peak) -> 90 (trough) -> 110
    # Max DD from 120 to 90 is (120 - 90)/120 = 25.0%
    equity_curve = [100.0, 110.0, 120.0, 105.0, 90.0, 100.0, 110.0]
    metrics = compute_metrics(100.0, equity_curve, [])
    assert pytest.approx(metrics.max_drawdown_pct, rel=1e-3) == 25.0


def test_chronological_walk_forward_split():
    """Verifies that train and test sets strictly maintain chronological ordering with no overlap."""
    candles = pd.DataFrame({
        "timestamp": [1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000],
        "close": [1.0] * 10,
    })
    decisions = [
        HistoricalDecision(ts, "BTCUSDT", "5m", 1.0, "HOLD", 0.5, 0.5, 0.25, 0.25)
        for ts in candles["timestamp"]
    ]

    train_c, train_d, test_c, test_d = chronological_split(candles, decisions, train_ratio=0.70)

    assert len(train_c) == 7
    assert len(test_c) == 3
    assert train_c["timestamp"].max() < test_c["timestamp"].min()
    assert max(d.timestamp for d in train_d) < min(d.timestamp for d in test_d)


def test_backtest_reproducibility():
    """Verifies that identical historical inputs and configurations produce exact identical results."""
    candles = DatasetManager.generate_synthetic_history(count=300, seed=99)
    enriched = DatasetManager.compute_causal_indicators(candles)
    decisions = DatasetManager.generate_simulated_decisions(enriched, seed=77)

    cfg = BacktestConfig(initial_balance=10000.0, fee_rate=0.001, slippage_rate=0.0005)
    engine = BacktestEngine(cfg)

    res1 = engine.run(candles, decisions)
    res2 = engine.run(candles, decisions)

    assert res1.metrics.total_return_pct == res2.metrics.total_return_pct
    assert res1.metrics.max_drawdown_pct == res2.metrics.max_drawdown_pct
    assert len(res1.trades) == len(res2.trades)
    assert res1.equity_curve == res2.equity_curve
