"""Automated tests for system-level safety invariants."""

import pytest
from bot.config import BotConfig


def test_refuse_to_start_if_real_trading_enabled():
    """Verifies that the bot refuses to boot if PAPER_TRADING_ONLY is false."""
    with pytest.raises(RuntimeError, match="CRITICAL SAFETY VIOLATION"):
        BotConfig(
            paper_trading_only=False,  # Attempting real execution
            symbol="BTCUSDT",
            candle_interval="5m",
            candle_limit=250,
            initial_balance=10000.0,
            maker_fee=0.0002,
            taker_fee=0.00075,
            max_risk_per_trade=0.005,
            max_daily_loss=0.02,
            max_position_size=0.10,
            max_open_positions=1,
            leverage=1.0,
            loop_interval_seconds=60,
        ).validate_safety()


def test_refuse_to_start_if_leverage_detected():
    """Verifies that the bot refuses to boot if leverage > 1.0 is set."""
    with pytest.raises(RuntimeError, match="CRITICAL SAFETY VIOLATION"):
        BotConfig(
            paper_trading_only=True,
            symbol="BTCUSDT",
            candle_interval="5m",
            candle_limit=250,
            initial_balance=10000.0,
            maker_fee=0.0002,
            taker_fee=0.00075,
            max_risk_per_trade=0.005,
            max_daily_loss=0.02,
            max_position_size=0.10,
            max_open_positions=1,
            leverage=2.0,  # Leverage violation
            loop_interval_seconds=60,
        ).validate_safety()
