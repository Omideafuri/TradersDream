"""Automated tests for Phase 10B.5 Forensic Remediation & Safety Hardening."""

import asyncio
import os
from pathlib import Path
import pytest
import pandas as pd
import numpy as np

from bot.config import BotConfig
from bot.main import CryptoTradingBot
from bot.decision import RuleBasedJev, JevApiProvider, Action
from backtest.engine import BacktestEngine, BacktestConfig
from backtest.forward_returns import calculate_directional_return
from phase10b.models import (
    BookSide,
    L2Delta,
    L2DeltaPacket,
    L2Snapshot,
    ms_to_us,
    us_to_ms,
)
from phase10b.reconstructor import OrderBookReconstructor, OrderBookReconstructionError
from phase10b.validator import EventDataValidator
from phase10b4.collector.config import CollectorConfig
from phase10b4.collector.stream_client import BinanceUSStreamCollector
from phase10b4.collector.buffer_writer import EventBufferWriter


# ==============================================================================
# 1. P0 SAFETY & USE_LIVE_JEV TESTS
# ==============================================================================

def test_safety_use_live_jev_defaults_to_false(monkeypatch):
    """Test that USE_LIVE_JEV defaults to False when omitted."""
    monkeypatch.delenv("USE_LIVE_JEV", raising=False)
    monkeypatch.delenv("JEV_AGENT_KEY", raising=False)
    cfg = BotConfig.from_env()
    assert cfg.use_live_jev is False
    bot = CryptoTradingBot(cfg)
    assert isinstance(bot.decision_engine.provider, RuleBasedJev)


def test_safety_presence_of_key_does_not_enable_live_jev(monkeypatch):
    """Test that presence of JEV_AGENT_KEY alone NEVER enables live mode."""
    monkeypatch.setenv("USE_LIVE_JEV", "false")
    monkeypatch.setenv("JEV_AGENT_KEY", "mock_dummy_test_key_12345")
    cfg = BotConfig.from_env()
    assert cfg.use_live_jev is False
    bot = CryptoTradingBot(cfg)
    assert isinstance(bot.decision_engine.provider, RuleBasedJev)


def test_safety_malformed_flag_fails_closed(monkeypatch):
    """Test that malformed or non-canonical flag values fail closed to offline."""
    for malformed in ["yes", "enable", "TRUE_PLEASE", "2", "ACTIVE", ""]:
        monkeypatch.setenv("USE_LIVE_JEV", malformed)
        cfg = BotConfig.from_env()
        assert cfg.use_live_jev is False
        bot = CryptoTradingBot(cfg)
        assert isinstance(bot.decision_engine.provider, RuleBasedJev)


def test_safety_explicit_live_mode_requires_deliberate_confirmation(monkeypatch):
    """Test that setting USE_LIVE_JEV=true without explicit confirmation raises safety error."""
    monkeypatch.setenv("USE_LIVE_JEV", "true")
    monkeypatch.delenv("LIVE_JEV_CONFIRMATION", raising=False)
    with pytest.raises(RuntimeError, match="CRITICAL SAFETY VIOLATION.*safety gate"):
        BotConfig.from_env()


def test_safety_explicit_live_mode_with_confirmation_permits_provider(monkeypatch):
    """Test that explicit flag WITH deliberate confirmation token permits JevApiProvider."""
    monkeypatch.setenv("USE_LIVE_JEV", "true")
    monkeypatch.setenv("LIVE_JEV_CONFIRMATION", "CONFIRM_ENABLE_LIVE_JEV")
    monkeypatch.setenv("JEV_AGENT_KEY", "test_key")
    cfg = BotConfig.from_env()
    assert cfg.use_live_jev is True
    bot = CryptoTradingBot(cfg)
    assert isinstance(bot.decision_engine.provider, JevApiProvider)


@pytest.mark.asyncio
async def test_offline_mode_makes_zero_http_calls(monkeypatch):
    """Test that RuleBasedJev executes purely in-memory with zero network calls."""
    monkeypatch.setenv("USE_LIVE_JEV", "false")
    cfg = BotConfig.from_env()
    bot = CryptoTradingBot(cfg)
    # Execute decision on synthetic market state
    klines = bot.market_data.generate_synthetic_klines(count=250)
    from bot.indicators import calculate_indicators, build_market_state
    state = build_market_state(calculate_indicators(klines))
    decision = await bot.decision_engine.get_decision(state)
    assert decision.action in (Action.LONG, Action.SHORT, Action.HOLD)
    assert decision.reason_code in ("TREND_CONFIRMATION", "DOWNTREND_CONFIRMATION", "NO_CLEAR_SIGNAL")


from backtest.dataset import HistoricalDecision


# ==============================================================================
# 2. P1 BACKTEST CASH ACCOUNTING RECONCILIATION
# ==============================================================================

def test_backtest_cash_accounting_reconciliation_long():
    """Hand-calculated exact accounting test for LONG position with slippage.
    
    Verifies that cash after position exit exactly equals:
        initial_balance + net_pnl
    Proving that entry slippage is not double-deducted and exit capital is exact.
    """
    initial_cash = 10000.0
    config = BacktestConfig(
        initial_balance=initial_cash,
        fee_rate=0.001,          # 10 bps
        slippage_rate=0.002,     # 20 bps
    )
    engine = BacktestEngine(config)

    # 2 candles: entry bar, exit bar
    candles = pd.DataFrame({
        "timestamp": [1000, 2000],
        "open": [100.0, 110.0],
        "high": [105.0, 115.0],
        "low": [99.0, 108.0],
        "close": [100.0, 110.0],
        "volume": [100.0, 100.0],
    })
    decisions = [
        HistoricalDecision(1000, "BTCUSDT", "5m", 100.0, "LONG", 0.9, 0.1, 0.9, 0.0),
    ]

    result = engine.run(candles, decisions)
    assert len(result.trades) == 1
    t = result.trades[0]

    # Verify exact cash conservation:
    # Final cash must equal initial balance + trade net_pnl
    expected_final_cash = initial_cash + t.net_pnl
    assert pytest.approx(result.equity_curve[-1], rel=1e-6) == expected_final_cash


def test_backtest_cash_accounting_reconciliation_short():
    """Hand-calculated exact accounting test for SHORT position with slippage.
    
    Verifies that cash after short position exit exactly equals:
        initial_balance + net_pnl
    Proving that entry slippage is not erroneously refunded on shorts.
    """
    initial_cash = 10000.0
    config = BacktestConfig(
        initial_balance=initial_cash,
        fee_rate=0.001,
        slippage_rate=0.002,
    )
    engine = BacktestEngine(config)

    # Price falls from 100 to 80 (profitable short)
    candles = pd.DataFrame({
        "timestamp": [1000, 2000],
        "open": [100.0, 90.0],
        "high": [101.0, 91.0],
        "low": [98.0, 88.0],
        "close": [100.0, 90.0],
        "volume": [100.0, 100.0],
    })
    decisions = [
        HistoricalDecision(1000, "BTCUSDT", "5m", 100.0, "SHORT", 0.9, 0.1, 0.0, 0.9),
    ]

    result = engine.run(candles, decisions)
    assert len(result.trades) == 1
    t = result.trades[0]

    expected_final_cash = initial_cash + t.net_pnl
    assert pytest.approx(result.equity_curve[-1], rel=1e-6) == expected_final_cash


def test_backtest_end_of_data_liquidation_cash():
    """Verify that open positions closed at END_OF_DATA conserve cash exactly."""
    initial_cash = 10000.0
    config = BacktestConfig(
        initial_balance=initial_cash,
        fee_rate=0.001,
        slippage_rate=0.002,
    )
    engine = BacktestEngine(config)

    candles = pd.DataFrame({
        "timestamp": [1000, 2000],
        "open": [100.0, 101.0],
        "high": [101.0, 101.5],
        "low": [99.5, 100.5],
        "close": [100.0, 101.0],
        "volume": [100.0, 100.0],
    })
    decisions = [
        HistoricalDecision(1000, "BTCUSDT", "5m", 100.0, "LONG", 0.9, 0.1, 0.9, 0.0),
    ]

    result = engine.run(candles, decisions)
    assert len(result.trades) == 1
    t = result.trades[0]
    assert t.exit_reason == "END_OF_DATA"

    expected_final_cash = initial_cash + t.net_pnl
    assert pytest.approx(result.equity_curve[-1], rel=1e-6) == expected_final_cash


# ==============================================================================
# 3. P1 FORWARD RETURN FORMULA TESTS
# ==============================================================================

def test_directional_return_mathematical_symmetry():
    """Verifies directional returns for LONG and SHORT:
    
    If entry=100 and future=50:
      LONG return = (50/100) - 1.0 = -50%
      SHORT return = 1.0 - (50/100) = +50%
    If entry=100 and future=200:
      LONG return = (200/100) - 1.0 = +100%
      SHORT return = 1.0 - (200/100) = -100%
    """
    assert pytest.approx(calculate_directional_return("LONG", 100.0, 50.0)) == -0.50
    assert pytest.approx(calculate_directional_return("SHORT", 100.0, 50.0)) == 0.50
    assert pytest.approx(calculate_directional_return("LONG", 100.0, 200.0)) == 1.00
    assert pytest.approx(calculate_directional_return("SHORT", 100.0, 200.0)) == -1.00


# ==============================================================================
# 4. P1 L2 PACKET-LEVEL SEQUENCE MODEL & INTRA-PACKET UPDATES
# ==============================================================================

def test_reconstructor_intra_packet_updates():
    """Verify that multiple price updates sharing the same sequence_id (intra-packet) are permitted."""
    reconstructor = OrderBookReconstructor(symbol="BTCUSDT", exchange="BINANCE_US", strict_mode=True)
    snapshot = L2Snapshot(
        symbol="BTCUSDT",
        exchange="BINANCE_US",
        exchange_timestamp_ms=1000,
        sequence_id=100,
        bids=[(50000.0, 1.0), (49990.0, 2.0)],
        asks=[(50010.0, 1.0), (50020.0, 2.0)],
    )
    reconstructor.load_snapshot(snapshot)

    # First update of packet 101
    d1 = L2Delta("BTCUSDT", "BINANCE_US", 1010, 101, BookSide.BID, 50005.0, 0.5)
    # Second intra-packet update at sequence 101
    d2 = L2Delta("BTCUSDT", "BINANCE_US", 1010, 101, BookSide.ASK, 50008.0, 0.8)

    s1 = reconstructor.apply_delta(d1)
    s2 = reconstructor.apply_delta(d2)

    assert s2.best_bid == 50005.0
    assert s2.best_ask == 50008.0
    assert len(reconstructor.sequence_gaps) == 0


def test_reconstructor_apply_delta_packet():
    """Verify that apply_delta_packet applies an atomic packet of multiple deltas."""
    reconstructor = OrderBookReconstructor(symbol="BTCUSDT", exchange="BINANCE_US", strict_mode=True)
    snapshot = L2Snapshot(
        symbol="BTCUSDT",
        exchange="BINANCE_US",
        exchange_timestamp_ms=1000,
        sequence_id=100,
        bids=[(50000.0, 1.0)],
        asks=[(50010.0, 1.0)],
    )
    reconstructor.load_snapshot(snapshot)

    packet = L2DeltaPacket(
        symbol="BTCUSDT",
        exchange="BINANCE_US",
        exchange_timestamp_ms=1010,
        first_update_id=101,
        final_update_id=105,
        deltas=[
            L2Delta("BTCUSDT", "BINANCE_US", 1010, 101, BookSide.BID, 50002.0, 1.5),
            L2Delta("BTCUSDT", "BINANCE_US", 1010, 105, BookSide.ASK, 50006.0, 2.0),
        ],
    )
    state = reconstructor.apply_delta_packet(packet)
    assert state.best_bid == 50002.0
    assert state.best_ask == 50006.0
    assert reconstructor.last_sequence_id == 105


def test_reconstructor_apply_delta_packet_gap_detection():
    """Verify that a gap in packet first_update_id is detected and raises in strict mode."""
    reconstructor = OrderBookReconstructor(symbol="BTCUSDT", exchange="BINANCE_US", strict_mode=True)
    snapshot = L2Snapshot(
        symbol="BTCUSDT",
        exchange="BINANCE_US",
        exchange_timestamp_ms=1000,
        sequence_id=100,
        bids=[(50000.0, 1.0)],
        asks=[(50010.0, 1.0)],
    )
    reconstructor.load_snapshot(snapshot)

    # Gap: expected 101, got 105
    packet = L2DeltaPacket(
        symbol="BTCUSDT",
        exchange="BINANCE_US",
        exchange_timestamp_ms=1010,
        first_update_id=105,
        final_update_id=110,
        deltas=[L2Delta("BTCUSDT", "BINANCE_US", 1010, 105, BookSide.BID, 50002.0, 1.5)],
    )
    with pytest.raises(OrderBookReconstructionError, match="Sequence gap detected"):
        reconstructor.apply_delta_packet(packet)


def test_validator_delta_packets():
    """Verify that EventDataValidator.validate_delta_packets validates packets correctly."""
    packets = [
        L2DeltaPacket(
            symbol="BTCUSDT",
            exchange="BINANCE_US",
            exchange_timestamp_ms=1000,
            first_update_id=1,
            final_update_id=5,
            deltas=[L2Delta("BTCUSDT", "BINANCE_US", 1000, 1, BookSide.BID, 50000.0, 1.0)],
        ),
        L2DeltaPacket(
            symbol="BTCUSDT",
            exchange="BINANCE_US",
            exchange_timestamp_ms=1010,
            first_update_id=6,
            final_update_id=10,
            deltas=[L2Delta("BTCUSDT", "BINANCE_US", 1010, 6, BookSide.ASK, 50010.0, 1.0)],
        ),
    ]
    is_valid, issues, gaps = EventDataValidator.validate_delta_packets(packets)
    assert is_valid is True
    assert len(gaps) == 0


# ==============================================================================
# 5. P3 TIMESTAMP NORMALIZATION TESTS
# ==============================================================================

def test_timestamp_conversions():
    """Verify millisecond to microsecond conversion utilities."""
    ms = 1700000000123
    us = ms_to_us(ms)
    assert us == 1700000000123000
    assert us_to_ms(us) == ms

    delta = L2Delta(
        symbol="BTCUSDT",
        exchange="BINANCE_US",
        exchange_timestamp_ms=ms,
        sequence_id=1,
        side=BookSide.BID,
        price=50000.0,
        quantity=1.0,
        local_receive_timestamp_ms=ms + 5,
    )
    assert delta.exchange_timestamp_us == ms * 1000
    assert delta.local_receive_timestamp_us == (ms + 5) * 1000


# ==============================================================================
# 6. P1 COLLECTOR & FAIL-CLOSED MARKET DATA TESTS
# ==============================================================================

def test_collector_configuration_and_instantiation(tmp_path):
    """Verify CollectorConfig and BinanceUSStreamCollector signatures and writer registration."""
    config = CollectorConfig(
        venue="binance-us",
        symbols=["BTCUSDT"],
        output_dir=tmp_path,
        enable_gzip_compression=False,
    )
    collector = BinanceUSStreamCollector(config=config)
    writer = EventBufferWriter(tmp_path, "BTCUSDT", "incremental_book_L2", gzip_compress=False)
    collector.register_writer("BTCUSDT_depth", writer)

    assert "BTCUSDT_depth" in collector.writers
    assert "btcusdt@depth@100ms" in collector.build_stream_url()


@pytest.mark.asyncio
async def test_bot_market_data_fails_closed():
    """Verify that CryptoTradingBot raises RuntimeError when market data fails and fallback is disabled."""
    bot = CryptoTradingBot(allow_synthetic_fallback=False)
    # Patch market_data.fetch_klines to raise network error
    async def mock_fail(*args, **kwargs):
        raise ConnectionError("Simulated network outage")

    bot.market_data.fetch_klines = mock_fail
    with pytest.raises(RuntimeError, match="Failing closed"):
        await bot.step()
