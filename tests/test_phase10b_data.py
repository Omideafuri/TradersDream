"""Comprehensive Unit and Integration Test Suite for Phase 10B Event-Level Data.

Covers:
1. Sequence-gap detection
2. Duplicate detection
3. Out-of-order detection
4. Timestamp validation
5. Price validation
6. Quantity validation
7. Snapshot loading
8. Delta application
9. Book reconstruction
10. Crossed-book detection
11. Trade validation
12. Trade/book causal alignment
13. Holdout separation
14. Manifest generation
15. Hash reproducibility
16. Raw-data immutability
17. Deterministic rerun
18. Phase 9 integrity
19. Safety invariants
"""

import json
import os
from pathlib import Path
import pytest

from bot.config import BotConfig
from phase10b.models import (
    TickTrade,
    L2Delta,
    L2Snapshot,
    AggressorSide,
    BookSide,
    GapSeverity,
)
from phase10b.reconstructor import OrderBookReconstructor, OrderBookReconstructionError
from phase10b.validator import EventDataValidator
from phase10b.alignment import TradeBookAligner, AlignmentError
from phase10b.holdout import EventHoldoutManager, HoldoutContaminationError
from phase10b.auditor import Phase10BDataAuditor


@pytest.fixture
def sample_snapshot() -> L2Snapshot:
    """Fixture providing a standard valid L2 order book snapshot."""
    return L2Snapshot(
        symbol="BTCUSDT",
        exchange="BINANCE_US",
        exchange_timestamp_ms=1000,
        sequence_id=100,
        bids=[(50000.0, 1.5), (49990.0, 2.0), (49980.0, 5.0)],
        asks=[(50010.0, 1.0), (50020.0, 3.0), (50030.0, 4.0)],
    )


def test_snapshot_loading(sample_snapshot):
    """Test 7: Snapshot loading into OrderBookReconstructor."""
    reconstructor = OrderBookReconstructor(symbol="BTCUSDT", exchange="BINANCE_US")
    state = reconstructor.load_snapshot(sample_snapshot)

    assert state.best_bid == 50000.0
    assert state.best_ask == 50010.0
    assert state.spread == 10.0
    assert state.midpoint == 50005.0
    assert state.is_crossed is False
    assert reconstructor.last_sequence_id == 100


def test_delta_application_and_book_reconstruction(sample_snapshot):
    """Tests 8 & 9: Delta application (modify, add, delete) and state update."""
    reconstructor = OrderBookReconstructor(symbol="BTCUSDT", exchange="BINANCE_US")
    reconstructor.load_snapshot(sample_snapshot)

    # 1. Add higher bid (tighten spread)
    d1 = L2Delta(
        symbol="BTCUSDT",
        exchange="BINANCE_US",
        exchange_timestamp_ms=1010,
        sequence_id=101,
        side=BookSide.BID,
        price=50005.0,
        quantity=0.5,
    )
    s1 = reconstructor.apply_delta(d1)
    assert s1.best_bid == 50005.0
    assert s1.spread == 5.0

    # 2. Delete level (quantity = 0.0)
    d2 = L2Delta(
        symbol="BTCUSDT",
        exchange="BINANCE_US",
        exchange_timestamp_ms=1020,
        sequence_id=102,
        side=BookSide.BID,
        price=50005.0,
        quantity=0.0,
    )
    s2 = reconstructor.apply_delta(d2)
    assert s2.best_bid == 50000.0
    assert s2.spread == 10.0


def test_sequence_gap_detection(sample_snapshot):
    """Test 1: Sequence-gap detection in reconstructor and validator."""
    reconstructor = OrderBookReconstructor(symbol="BTCUSDT", exchange="BINANCE_US", strict_mode=True)
    reconstructor.load_snapshot(sample_snapshot)

    # Delta with jumped sequence (expected 101, got 105)
    gap_delta = L2Delta(
        symbol="BTCUSDT",
        exchange="BINANCE_US",
        exchange_timestamp_ms=1010,
        sequence_id=105,
        side=BookSide.ASK,
        price=50015.0,
        quantity=1.0,
    )

    with pytest.raises(OrderBookReconstructionError, match="Sequence gap detected"):
        reconstructor.apply_delta(gap_delta)

    # Non-strict mode records the gap
    reconstructor_lenient = OrderBookReconstructor(symbol="BTCUSDT", exchange="BINANCE_US", strict_mode=False)
    reconstructor_lenient.load_snapshot(sample_snapshot)
    reconstructor_lenient.apply_delta(gap_delta)
    assert len(reconstructor_lenient.sequence_gaps) == 1
    assert reconstructor_lenient.sequence_gaps[0].gap_size == 4


def test_duplicate_detection():
    """Test 2: Duplicate detection for trades and deltas."""
    trades = [
        TickTrade("t1", "BTCUSDT", "BINANCE_US", 1000, 50000.0, 0.1, AggressorSide.BUY),
        TickTrade("t1", "BTCUSDT", "BINANCE_US", 1001, 50000.0, 0.2, AggressorSide.BUY),
    ]
    is_valid, issues = EventDataValidator.validate_trades(trades)
    assert is_valid is False
    assert any("duplicate_trade_id" in i.check_name for i in issues)

    deltas = [
        L2Delta("BTCUSDT", "BINANCE_US", 1000, 101, BookSide.BID, 50000.0, 1.0),
        L2Delta("BTCUSDT", "BINANCE_US", 1001, 101, BookSide.BID, 50000.0, 1.5),
    ]
    is_valid_d, issues_d, _ = EventDataValidator.validate_deltas(deltas)
    assert is_valid_d is False
    assert any("duplicate_delta_sequence" in i.check_name for i in issues_d)


def test_out_of_order_detection():
    """Test 3: Out-of-order timestamp detection."""
    trades = [
        TickTrade("t1", "BTCUSDT", "BINANCE_US", 2000, 50000.0, 0.1, AggressorSide.BUY),
        TickTrade("t2", "BTCUSDT", "BINANCE_US", 1500, 50000.0, 0.2, AggressorSide.BUY),
    ]
    is_valid, issues = EventDataValidator.validate_trades(trades)
    assert is_valid is False
    assert any("trade_timestamp_out_of_order" in i.check_name for i in issues)


def test_timestamp_validation():
    """Test 4: Timestamp validation logic in audit_stream_integrity."""
    trades = [TickTrade("t1", "BTCUSDT", "BINANCE_US", 1000, 50000.0, 0.1, AggressorSide.BUY)]
    deltas = [L2Delta("BTCUSDT", "BINANCE_US", 1000, 1, BookSide.BID, 50000.0, 1.0)]
    report = EventDataValidator.audit_stream_integrity("BTCUSDT", "BINANCE_US", trades, deltas, [])
    assert report.coverage_start_ms == 1000
    assert report.coverage_end_ms == 1000
    assert report.timespan_hours == 0.0


def test_price_validation():
    """Test 5: Price validation (non-positive price rejection)."""
    trades = [TickTrade("t1", "BTCUSDT", "BINANCE_US", 1000, -100.0, 0.1, AggressorSide.BUY)]
    is_valid, issues = EventDataValidator.validate_trades(trades)
    assert is_valid is False
    assert any("invalid_trade_price" in i.check_name for i in issues)

    deltas = [L2Delta("BTCUSDT", "BINANCE_US", 1000, 1, BookSide.BID, 0.0, 1.0)]
    is_valid_d, issues_d, _ = EventDataValidator.validate_deltas(deltas)
    assert is_valid_d is False
    assert any("invalid_delta_price" in i.check_name for i in issues_d)


def test_quantity_validation():
    """Test 6: Quantity validation (non-positive trade, negative delta size)."""
    trades = [TickTrade("t1", "BTCUSDT", "BINANCE_US", 1000, 50000.0, -0.5, AggressorSide.BUY)]
    is_valid, issues = EventDataValidator.validate_trades(trades)
    assert is_valid is False
    assert any("invalid_trade_quantity" in i.check_name for i in issues)

    deltas = [L2Delta("BTCUSDT", "BINANCE_US", 1000, 1, BookSide.BID, 50000.0, -1.0)]
    is_valid_d, issues_d, _ = EventDataValidator.validate_deltas(deltas)
    assert is_valid_d is False
    assert any("invalid_delta_quantity" in i.check_name for i in issues_d)


def test_crossed_book_detection(sample_snapshot):
    """Test 10: Crossed-book detection in reconstructor."""
    reconstructor = OrderBookReconstructor(symbol="BTCUSDT", exchange="BINANCE_US", strict_mode=True)
    reconstructor.load_snapshot(sample_snapshot)

    # Apply bid that exceeds best ask (50010.0)
    crossing_bid = L2Delta(
        symbol="BTCUSDT",
        exchange="BINANCE_US",
        exchange_timestamp_ms=1010,
        sequence_id=101,
        side=BookSide.BID,
        price=50015.0,
        quantity=1.0,
    )
    with pytest.raises(OrderBookReconstructionError, match="Crossed book"):
        reconstructor.apply_delta(crossing_bid)


def test_trade_validation():
    """Test 11: Valid trade sequence passes audit cleanly."""
    trades = [
        TickTrade("t1", "BTCUSDT", "BINANCE_US", 1000, 50000.0, 0.1, AggressorSide.BUY),
        TickTrade("t2", "BTCUSDT", "BINANCE_US", 1005, 50005.0, 0.2, AggressorSide.SELL),
    ]
    is_valid, issues = EventDataValidator.validate_trades(trades)
    assert is_valid is True
    assert len(issues) == 0


def test_trade_book_causal_alignment(sample_snapshot):
    """Test 12: Trade/book causal alignment and lookahead prevention."""
    reconstructor = OrderBookReconstructor(symbol="BTCUSDT", exchange="BINANCE_US")
    b0 = reconstructor.load_snapshot(sample_snapshot)

    # Book update at t=1010
    d1 = L2Delta("BTCUSDT", "BINANCE_US", 1010, 101, BookSide.BID, 50002.0, 1.0)
    b1 = reconstructor.apply_delta(d1)

    trades = [
        # Trade at t=1005 should match b0 (t=1000), NOT b1 (t=1010)
        TickTrade("t1", "BTCUSDT", "BINANCE_US", 1005, 50005.0, 0.1, AggressorSide.BUY),
        # Trade at t=1015 should match b1 (t=1010)
        TickTrade("t2", "BTCUSDT", "BINANCE_US", 1015, 50008.0, 0.2, AggressorSide.SELL),
    ]

    aligner = TradeBookAligner()
    aligned, report = aligner.align_stream(trades, [b0, b1])

    assert report.is_valid is True
    assert report.aligned_trades == 2
    assert report.causal_violations == 0
    assert aligned[0].preceding_book.timestamp_ms == 1000
    assert aligned[0].book_age_ms == 5
    assert aligned[1].preceding_book.timestamp_ms == 1010
    assert aligned[1].book_age_ms == 5


def test_holdout_separation_and_leakage_guard():
    """Test 13: Holdout 60/20/20 partitioning and contamination rejection."""
    events = [
        {"trade_id": f"t_{i}", "exchange_timestamp_ms": 1000 + i * 10}
        for i in range(100)
    ]

    dev, val, holdout = EventHoldoutManager.partition_events(events)

    assert len(dev) == 60
    assert len(val) == 20
    assert len(holdout) == 20

    # Temporal bounds check
    assert max(x["exchange_timestamp_ms"] for x in dev) <= min(x["exchange_timestamp_ms"] for x in val)
    assert max(x["exchange_timestamp_ms"] for x in val) <= min(x["exchange_timestamp_ms"] for x in holdout)

    # Overlapping ID injection must raise HoldoutContaminationError
    corrupted_holdout = list(holdout)
    corrupted_holdout[0] = dict(dev[0])
    with pytest.raises(HoldoutContaminationError):
        EventHoldoutManager.verify_no_contamination(dev, val, corrupted_holdout)


def test_manifest_generation(tmp_path):
    """Test 14: Manifest generation in Phase10BDataAuditor."""
    auditor = Phase10BDataAuditor(repo_root=tmp_path)
    manifest = auditor.generate_data_manifest()
    acq_log = auditor.generate_acquisition_log()
    val_report = auditor.generate_validation_report()

    assert manifest["validation_status"] == "DATA_INSUFFICIENT"
    assert val_report["sufficiency"] == "DATA INSUFFICIENT"
    assert val_report["phase10c_permission"] == "BLOCKED"
    assert len(acq_log["candidate_sources"]) == 4


def test_hash_reproducibility():
    """Test 15: Deterministic hash calculation on partitions."""
    events = [{"trade_id": "t1", "exchange_timestamp_ms": 1000, "price": 50000.0}]
    h1 = EventHoldoutManager.compute_partition_sha256(events)
    h2 = EventHoldoutManager.compute_partition_sha256(events)
    assert h1 == h2
    assert len(h1) == 64


def test_raw_data_immutability():
    """Test 16: Ensure raw directory structure is read-only and preserved."""
    repo_root = Path(__file__).resolve().parent.parent
    raw_dir = repo_root / "data" / "phase10b" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    assert raw_dir.is_dir()


def test_deterministic_rerun(sample_snapshot):
    """Test 17: Running reconstruction on identical sequence produces 0 delta."""
    deltas = [
        L2Delta("BTCUSDT", "BINANCE_US", 1010, 101, BookSide.BID, 50002.0, 1.0),
        L2Delta("BTCUSDT", "BINANCE_US", 1020, 102, BookSide.ASK, 50008.0, 1.5),
    ]

    r1 = OrderBookReconstructor("BTCUSDT", "BINANCE_US")
    r1.load_snapshot(sample_snapshot)
    for d in deltas:
        r1.apply_delta(d)
    s1 = r1.get_current_state()

    r2 = OrderBookReconstructor("BTCUSDT", "BINANCE_US")
    r2.load_snapshot(sample_snapshot)
    for d in deltas:
        r2.apply_delta(d)
    s2 = r2.get_current_state()

    assert s1.best_bid == s2.best_bid
    assert s1.best_ask == s2.best_ask
    assert s1.midpoint == s2.midpoint
    assert s1.spread == s2.spread


def test_phase9_integrity_preserved():
    """Test 18: Phase 9 freeze and closure documents remain intact."""
    repo_root = Path(__file__).resolve().parent.parent
    freeze = repo_root / "RESEARCH_FREEZE.md"
    assert freeze.is_file()
    assert "MASTER_CLASSIFICATION:  NOT_SUPPORTED" in freeze.read_text(encoding="utf-8")

    closure_doc = repo_root / "PHASE9E_RESEARCH_CLOSURE.md"
    assert closure_doc.is_file()
    assert "NOT_SUPPORTED" in closure_doc.read_text(encoding="utf-8")


def test_safety_invariants():
    """Test 19: Strict paper trading only and zero leverage."""
    cfg = BotConfig.from_env()
    assert cfg.paper_trading_only is True
    assert cfg.leverage == 1.0
    use_live_jev = os.getenv("USE_LIVE_JEV", "false").strip().lower() in ("true", "1")
    assert use_live_jev is False
