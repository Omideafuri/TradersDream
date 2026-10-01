"""Automated tests for Phase 10C authentic L2 data qualification, adapter, and gate evaluation."""

import csv
from pathlib import Path
import pytest

from phase10b.models import BookSide, AggressorSide
from phase10b.reconstructor import OrderBookReconstructor, OrderBookReconstructionError
from phase10c.adapter import TardisL2Adapter, TardisL2AdapterError


DATA_DIR = Path(__file__).resolve().parent.parent / "phase10b4" / "data"
L2_CSV = DATA_DIR / "sample_binance-us_incremental_book_L2_2024-03-01_BTCUSDT.csv"
TRADES_CSV = DATA_DIR / "sample_binance-us_trades_2024-03-01_BTCUSDT.csv"


def test_safety_invariants_strictly_maintained():
    """Verify core safety invariants remain intact in Phase 10C."""
    from bot.config import BotConfig
    cfg = BotConfig.from_env()
    assert cfg.paper_trading_only is True
    assert cfg.use_live_jev is False
    assert cfg.leverage == 1.0



def test_authentic_data_files_exist_and_hashes():
    """Verify authentic historical data files exist and have valid non-empty SHA-256 hashes."""
    assert L2_CSV.is_file(), f"L2 file missing: {L2_CSV}"
    assert TRADES_CSV.is_file(), f"Trades file missing: {TRADES_CSV}"

    l2_hash = TardisL2Adapter.calculate_file_hash(L2_CSV)
    trades_hash = TardisL2Adapter.calculate_file_hash(TRADES_CSV)

    assert len(l2_hash) == 64
    assert len(trades_hash) == 64
    # Empty string sha256 check
    empty_hash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    assert l2_hash != empty_hash
    assert trades_hash != empty_hash


def test_trades_csv_parsing():
    """Verify lossless parsing of authentic trades CSV into canonical TickTrade models."""
    trades = TardisL2Adapter.parse_trades_csv(TRADES_CSV)
    assert len(trades) == 4999
    
    first = trades[0]
    assert first.symbol == "BTCUSDT"
    assert first.exchange == "binance-us"
    assert first.price > 0
    assert first.quantity > 0
    assert first.aggressor_side in (AggressorSide.BUY, AggressorSide.SELL)
    assert first.exchange_timestamp_ms > 0
    assert first.local_receive_timestamp_ms is not None

    # Check side distribution
    buys = sum(1 for t in trades if t.aggressor_side == AggressorSide.BUY)
    sells = sum(1 for t in trades if t.aggressor_side == AggressorSide.SELL)
    assert buys == 3369
    assert sells == 1630


def test_incremental_book_l2_parsing_and_snapshot():
    """Verify L2 CSV normalization into initial L2Snapshot and grouped delta packets."""
    snapshot, packets, stats = TardisL2Adapter.parse_incremental_book_l2_csv(
        L2_CSV, symbol="BTCUSDT", exchange="binance-us"
    )

    assert snapshot.symbol == "BTCUSDT"
    assert snapshot.exchange == "binance-us"
    assert len(snapshot.bids) > 0
    assert len(snapshot.asks) > 0

    # Ensure zero-amount levels were filtered from snapshot
    assert stats["snapshot_zero_levels_filtered"] == 2
    assert all(q > 0 for _, q in snapshot.bids)
    assert all(q > 0 for _, q in snapshot.asks)

    # Ensure prices are sorted properly in snapshot
    assert all(snapshot.bids[i][0] >= snapshot.bids[i+1][0] for i in range(len(snapshot.bids)-1))
    assert all(snapshot.asks[i][0] <= snapshot.asks[i+1][0] for i in range(len(snapshot.asks)-1))

    # Pre-snapshot deltas discarded
    assert stats["discarded_pre_snapshot_deltas"] == 1
    assert stats["total_valid_deltas"] == 7996
    assert stats["total_delta_packets"] == 2231
    assert len(packets) == 2231


def test_deterministic_orderbook_reconstruction_strict_mode():
    """Verify 100% deterministic reconstruction of the authentic dataset in strict mode."""
    report = TardisL2Adapter.run_reconstruction_qualification(
        L2_CSV, symbol="BTCUSDT", exchange="binance-us", strict_mode=True
    )

    recon = report["reconstruction_metrics"]
    seq = report["orderbook_sequence_quality"]
    integ = report["integrity_metrics"]

    assert recon["successful_packets"] == 2231
    assert recon["successful_deltas"] == 7996
    assert recon["reconstruction_success_rate_pct"] == 100.0
    assert recon["crossed_book_occurrences"] == 0

    assert seq["sequence_gaps_count"] == 0
    assert seq["reconstruction_failures_count"] == 0

    assert integ["total_records"] == 9999
    assert integ["timestamp_ordering_violations"] == 0

    # Spreads must be positive throughout
    assert recon["initial_spread"] > 0
    assert recon["final_spread"] > 0
    assert recon["min_spread"] > 0
    assert recon["final_best_bid"] < recon["final_best_ask"]


def test_adapter_rejects_missing_schema_fields(tmp_path: Path):
    """Verify adapter strictly rejects malformed CSVs missing required contract fields."""
    bad_csv = tmp_path / "bad_l2.csv"
    with open(bad_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["exchange", "symbol", "price", "amount"])  # missing timestamp, side, etc.
        writer.writerow(["binance-us", "BTCUSDT", "60000.0", "1.0"])

    with pytest.raises(TardisL2AdapterError, match="missing required schema fields"):
        TardisL2Adapter.parse_incremental_book_l2_csv(bad_csv)


def test_adapter_rejects_invalid_price_or_quantity(tmp_path: Path):
    """Verify adapter rejects non-positive prices or negative quantities."""
    bad_price_csv = tmp_path / "bad_price.csv"
    with open(bad_price_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["exchange", "symbol", "timestamp", "local_timestamp", "is_snapshot", "side", "price", "amount"])
        writer.writerow(["binance-us", "BTCUSDT", "1709251201000000", "1709251201000000", "true", "bid", "-100.0", "1.0"])

    with pytest.raises(TardisL2AdapterError, match="Invalid non-positive price"):
        TardisL2Adapter.parse_incremental_book_l2_csv(bad_price_csv)


def test_scientific_separation_rejects_ohlcv_proxy():
    """Verify that OHLCV candles cannot be qualified as authentic event-level L2 data."""
    ohlcv_path = Path(__file__).resolve().parent.parent / "data" / "historical" / "BTCUSDT_5m_candles.csv"
    assert ohlcv_path.is_file()

    with pytest.raises(TardisL2AdapterError):
        TardisL2Adapter.parse_incremental_book_l2_csv(ohlcv_path)


def test_phase10c_qualification_gate_decision():
    """Verify scientific qualification gate: PARTIALLY_QUALIFIED due to sample coverage limits."""
    report = TardisL2Adapter.run_reconstruction_qualification(
        L2_CSV, symbol="BTCUSDT", exchange="binance-us", strict_mode=True
    )

    decision = TardisL2Adapter.evaluate_qualification_gate(report, min_required_days=30)

    # Technical validity passed
    assert decision["technical_validity"] == "VALID"
    # Data sufficiency failed (sample is ~8 minutes / 1 day slice, not 30 continuous days)
    assert decision["data_sufficiency"] == "INSUFFICIENT"
    # Final gate must be PARTIALLY_QUALIFIED
    assert decision["gate_status"] == "PARTIALLY_QUALIFIED"
    # Phase 10D must NOT be permitted to begin automatically
    assert decision["phase10d_permission"] is False
    assert "INSUFFICIENT" in decision["decision_reason"]
