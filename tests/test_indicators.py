"""Automated tests for deterministic technical indicators and MarketState."""

import json
import numpy as np
import pandas as pd
import pytest

from bot.indicators import (
    calculate_ema,
    calculate_rsi,
    calculate_atr,
    calculate_indicators,
    build_market_state,
    MarketState,
)


def test_ema_calculation():
    """Verifies EMA calculation correctness and determinism."""
    prices = pd.Series([10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0, 20.0])
    ema = calculate_ema(prices, period=5)

    # Output length must match input
    assert len(ema) == len(prices)
    # EMA must be strictly increasing for strictly increasing series
    assert (ema.diff().dropna() > 0).all()

    # Known mathematical formula check: multiplier alpha = 2 / (span + 1) = 2/6 = 1/3
    # Step 1: seed = 10.0
    # Step 2: 11.0 * (1/3) + 10.0 * (2/3) = 3.666667 + 6.666667 = 10.333333
    assert pytest.approx(ema.iloc[0], rel=1e-4) == 10.0
    assert pytest.approx(ema.iloc[1], rel=1e-4) == 10.333333


def test_rsi_calculation_bounds_and_dynamics():
    """Verifies RSI 14 calculation, boundary conditions, and responsiveness."""
    # 1. Strictly upward trend -> RSI must reach near 100
    up_prices = pd.Series(list(range(100, 200)))
    rsi_up = calculate_rsi(up_prices, period=14)
    valid_rsi_up = rsi_up.dropna()
    assert len(valid_rsi_up) > 0
    assert (valid_rsi_up <= 100.0).all()
    assert valid_rsi_up.iloc[-1] > 95.0

    # 2. Strictly downward trend -> RSI must drop near 0
    down_prices = pd.Series(list(range(200, 100, -1)))
    rsi_down = calculate_rsi(down_prices, period=14)
    valid_rsi_down = rsi_down.dropna()
    assert (valid_rsi_down >= 0.0).all()
    assert valid_rsi_down.iloc[-1] < 5.0

    # 3. Flat prices -> no gains, no losses, must remain bounded
    flat_prices = pd.Series([100.0] * 30)
    rsi_flat = calculate_rsi(flat_prices, period=14)
    assert not rsi_flat.dropna().isna().any()
    assert ((rsi_flat.dropna() >= 0.0) & (rsi_flat.dropna() <= 100.0)).all()


def test_atr_calculation():
    """Verifies Average True Range calculation."""
    df = pd.DataFrame({
        "high": [105.0, 107.0, 108.0, 110.0, 109.0] * 10,
        "low": [95.0, 96.0, 97.0, 98.0, 96.0] * 10,
        "close": [100.0, 106.0, 102.0, 108.0, 100.0] * 10,
    })
    atr = calculate_atr(df, period=14)
    assert len(atr) == len(df)
    valid_atr = atr.dropna()
    assert (valid_atr > 0).all()


def test_market_state_serialization():
    """Verifies MarketState object structure and JSON serializability."""
    state = MarketState(
        symbol="BTCUSDT",
        price=104250.0,
        ema20=104100.0,
        ema50=103800.0,
        ema200=101900.0,
        rsi14=61.4,
        atr14=1850.0,
        volume_ratio=1.42,
        price_change_pct=0.85,
        timestamp=1700000000000,
    )

    state_dict = state.to_dict()
    assert state_dict["symbol"] == "BTCUSDT"
    assert state_dict["price"] == 104250.0
    assert state_dict["rsi14"] == 61.4

    json_str = state.to_json()
    parsed = json.loads(json_str)
    assert parsed["symbol"] == "BTCUSDT"
    assert parsed["price"] == 104250.0
    assert parsed["volume_ratio"] == 1.42
