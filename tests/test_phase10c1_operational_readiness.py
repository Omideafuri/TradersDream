"""Automated tests for Phase 10C.1 30-day collection operational readiness audit."""

import json
from pathlib import Path
import shutil
import time
import pytest

from bot.config import BotConfig
from phase10b4.collector.config import CollectorConfig
from phase10b4.collector.buffer_writer import (
    EventBufferWriter, 
    RawMessageWriter, 
    DiskCapacityExceededError, 
    SyntheticDataForbiddenError
)
from phase10b4.collector.stream_client import BinanceUSStreamCollector, CollectorWatchdogTimeoutError
from phase10c.adapter import TardisL2Adapter


def test_safety_invariants_strictly_maintained():
    """Verify core safety invariants remain intact in Phase 10C.1."""
    cfg = BotConfig.from_env()
    assert cfg.paper_trading_only is True
    assert cfg.use_live_jev is False
    assert cfg.leverage == 1.0


def test_synthetic_fallback_strictly_forbidden(tmp_path: Path):
    """Requirement 2: Collector must strictly reject synthetic fallback data."""
    writer = EventBufferWriter(
        output_dir=tmp_path,
        symbol="BTCUSDT",
        stream_type="trades",
        gzip_compress=False,
        allow_synthetic=False,
    )

    valid_event = {
        "exchange": "binance-us",
        "symbol": "BTCUSDT",
        "timestamp": 1700000000000000,
        "local_timestamp": 1700000000000000,
        "id": "1001",
        "side": "buy",
        "price": 60000.0,
        "amount": 0.5,
    }
    writer.write_event(valid_event)
    assert len(writer.buffer) == 1

    # Synthetic event must be rejected
    synthetic_event = dict(valid_event)
    synthetic_event["is_synthetic"] = True
    with pytest.raises(SyntheticDataForbiddenError, match="Synthetic event rejected"):
        writer.write_event(synthetic_event)


def test_raw_data_preservation_stage(tmp_path: Path):
    """Requirement 3: Raw exchange messages must be preserved in distinct RAW stage."""
    raw_dir = tmp_path / "raw"
    norm_dir = tmp_path / "norm"
    
    cfg = CollectorConfig(
        output_dir=norm_dir,
        raw_output_dir=raw_dir,
        enable_gzip_compression=False,
    )
    collector = BinanceUSStreamCollector(config=cfg)

    raw_writer = RawMessageWriter(
        output_dir=raw_dir,
        symbol="BTCUSDT",
        gzip_compress=False,
    )
    norm_writer = EventBufferWriter(
        output_dir=norm_dir,
        symbol="BTCUSDT",
        stream_type="trades",
        gzip_compress=False,
    )
    collector.register_raw_writer("BTCUSDT", raw_writer)
    collector.register_writer("BTCUSDT_trades", norm_writer)

    raw_trade_msg = json.dumps({
        "e": "trade",
        "E": 1709251205000,
        "s": "BTCUSDT",
        "t": 88888,
        "p": "62000.50",
        "q": "0.25",
        "b": 12,
        "a": 34,
        "m": False,
    })

    collector.dispatch_raw_message(raw_trade_msg)
    collector.stop()

    # Verify RAW stage output exists and contains unaltered raw string
    raw_files = list(raw_dir.glob("binance-us_raw_*.jsonl"))
    assert len(raw_files) == 1
    raw_content = raw_files[0].read_text(encoding="utf-8")
    parsed_entry = json.loads(raw_content)
    assert "local_timestamp" in parsed_entry
    assert '"t": 88888' in parsed_entry["raw"]
    assert '"s": "BTCUSDT"' in parsed_entry["raw"]


    # Verify NORMALIZED stage output exists and contains parsed CSV fields
    norm_files = list(norm_dir.glob("binance-us_trades_*.csv"))
    assert len(norm_files) == 1
    norm_content = norm_files[0].read_text(encoding="utf-8")
    assert "88888" in norm_content
    assert "62000.5" in norm_content


def test_crash_safety_and_restart_header_integrity(tmp_path: Path):
    """Requirement 4 & 5: Process restart on existing file must survive without header duplication."""
    writer = EventBufferWriter(
        output_dir=tmp_path,
        symbol="BTCUSDT",
        stream_type="trades",
        gzip_compress=False,
    )

    ev1 = {
        "exchange": "binance-us",
        "symbol": "BTCUSDT",
        "timestamp": 1709251200000000,
        "local_timestamp": 1709251200000000,
        "id": "1",
        "side": "buy",
        "price": 60000.0,
        "amount": 0.1,
    }
    writer.write_event(ev1)
    writer.flush()

    file_path = writer.current_file_path
    assert file_path is not None
    assert file_path.is_file()

    # Simulate abrupt process restart: instantiate a new writer pointing to same output directory
    writer2 = EventBufferWriter(
        output_dir=tmp_path,
        symbol="BTCUSDT",
        stream_type="trades",
        gzip_compress=False,
    )
    ev2 = {
        "exchange": "binance-us",
        "symbol": "BTCUSDT",
        "timestamp": 1709251201000000,
        "local_timestamp": 1709251201000000,
        "id": "2",
        "side": "sell",
        "price": 60005.0,
        "amount": 0.2,
    }
    writer2.write_event(ev2)
    writer2.flush()

    # Verify file contents: must have exactly 1 header line and 2 data lines (no duplicate header!)
    lines = file_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 3
    assert lines[0].startswith("exchange,symbol,timestamp")
    assert "1,buy,60000.0,0.1" in lines[1]
    assert "2,sell,60005.0,0.2" in lines[2]


def test_disk_space_threshold_abort(tmp_path: Path, monkeypatch):
    """Requirement 8: Hard safety threshold when disk space is insufficient."""
    writer = EventBufferWriter(
        output_dir=tmp_path,
        symbol="BTCUSDT",
        stream_type="trades",
        gzip_compress=False,
        min_disk_free_bytes=5 * 1024 * 1024 * 1024,  # 5 GB threshold
    )

    # Monkeypatch shutil.disk_usage to simulate disk space dropped to 1 GB
    def mock_disk_usage(path):
        return (100 * 1024**3, 99 * 1024**3, 1 * 1024**3)  # 1 GB free
    monkeypatch.setattr(shutil, "disk_usage", mock_disk_usage)

    ev = {
        "exchange": "binance-us",
        "symbol": "BTCUSDT",
        "timestamp": 1709251200000000,
        "local_timestamp": 1709251200000000,
        "id": "1",
        "side": "buy",
        "price": 60000.0,
        "amount": 0.1,
    }
    writer.write_event(ev)
    with pytest.raises(DiskCapacityExceededError, match="below safety threshold"):
        writer.flush()


def test_silent_collector_watchdog_detection():
    """Requirement 7: Detect condition 'process alive + zero messages' for abnormal duration."""
    cfg = CollectorConfig(watchdog_timeout_seconds=0.1)
    collector = BinanceUSStreamCollector(config=cfg)
    collector.is_running = True

    # Simulate message received in past
    collector.last_message_time = time.time() - 10.0

    health = collector.check_health()
    assert health["silent_stall_detected"] is True
    assert health["health_status"] == "CRITICAL_SILENT_FAILURE"
    assert health["time_since_last_message_seconds"] >= 10.0


def test_duplicate_trade_packet_detection(tmp_path: Path):
    """Requirement 5: Duplicate trades across reconnects or network retries must be recorded."""
    collector = BinanceUSStreamCollector()
    mock_writer = EventBufferWriter(
        output_dir=tmp_path,
        symbol="BTCUSDT",
        stream_type="trades",
        gzip_compress=False,
    )
    collector.register_writer("BTCUSDT_trades", mock_writer)

    trade_msg = json.dumps({
        "e": "trade",
        "E": 1709251200000,
        "s": "BTCUSDT",
        "t": 77777,
        "p": "61000.0",
        "q": "0.1",
        "m": False,
    })

    # Dispatch first time
    collector.dispatch_raw_message(trade_msg)
    assert collector.duplicate_packets_count == 0

    # Dispatch identical trade second time
    collector.dispatch_raw_message(trade_msg)
    assert collector.duplicate_packets_count == 1


def test_daily_qualification_checkpoint_schema(tmp_path: Path):
    """Requirement 9 & 10: Machine-readable daily qualification checkpoint with continuity audit."""
    ckpt_dir = tmp_path / "checkpoints"
    cfg = CollectorConfig(checkpoint_dir=ckpt_dir)
    collector = BinanceUSStreamCollector(config=cfg)

    ckpt = collector.generate_daily_checkpoint(date_str="2024-03-01", symbol="BTCUSDT")

    assert ckpt["date"] == "2024-03-01"
    assert ckpt["symbol"] == "BTCUSDT"
    assert "event_count" in ckpt
    assert "reconnect_count" in ckpt
    assert "downtime_seconds" in ckpt
    assert "continuity_status" in ckpt
    assert ckpt["allow_synthetic_fallback"] is False

    # Check file exists on disk
    expected_file = ckpt_dir / "checkpoint_2024-03-01_BTCUSDT.json"
    assert expected_file.is_file()
    saved = json.loads(expected_file.read_text(encoding="utf-8"))
    assert saved["collector_version"] == "v10c.1"


def test_accounting_discrepancy_pre_snapshot_delta_resolution():
    """Requirement 14: Resolve the 7,997 vs 7,996 deltas discrepancy definitively.

    In the authentic L2 CSV:
    Total deltas = 7,997.
    Exactly 1 delta row has timestamp <= snapshot_timestamp (1709251201056000 <= 1709251201077754).
    Following Binance buffer synchronization rules, this pre-snapshot delta is dropped.
    7,997 - 1 = 7,996 applied deltas.
    """
    csv_path = Path(__file__).resolve().parent.parent / "phase10b4" / "data" / "sample_binance-us_incremental_book_L2_2024-03-01_BTCUSDT.csv"
    snapshot, packets, stats = TardisL2Adapter.parse_incremental_book_l2_csv(csv_path)

    assert stats["snapshot_rows_count"] == 2002
    assert stats["snapshot_zero_levels_filtered"] == 2
    assert stats["discarded_pre_snapshot_deltas"] == 1
    assert stats["total_valid_deltas"] == 7996
    # 7996 deltas + 1 discarded pre-snapshot delta = 7997 total delta records in CSV
    assert stats["total_valid_deltas"] + stats["discarded_pre_snapshot_deltas"] == 7997
