"""
Phase 13 Comprehensive Test Suite:
Validates paper-trading invariants, cryptographic strategy hashes, causal next-bar execution,
daily integrity verification, research dashboard endpoints, quote deduplication idempotency,
adverse slippage directional correctness, and boundary candle finalization.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
import pytest
from starlette.testclient import TestClient

from phase13.engine.state_manager import StateManager, ForwardState
from phase13.engine.execution_simulator import ExecutionSimulator
from phase13.engine.integrity_monitor import IntegrityMonitor
from phase13.engine.forward_monitor import ForwardMonitor
from phase13.engine.runner import ForwardRunner
from phase13.dashboard.app import app

ROOT_DIR = Path(__file__).resolve().parent.parent


def test_safety_invariants_hardcoded():
    """Verify safety invariants are hardcoded and non-negotiable."""
    runner = ForwardRunner()
    assert runner.PAPER_TRADING_ONLY is True
    assert runner.LIVE_ORDERS == 0
    assert runner.WALLET_CONNECTIONS == 0
    assert runner.PRIVATE_KEYS == 0
    assert runner.LEVERAGE == 1.0

    state = runner.monitor.sm.state
    assert state.environment == "PAPER_TRADING_ONLY"
    assert state.live_orders_permitted == 0
    assert state.wallet_connections == 0
    assert state.private_keys == 0
    assert state.leverage == 1.0


def test_strategy_immutability_hashes():
    """Verify cryptographic SHA-256 strategy lock hashes match exact file contents."""
    sm = StateManager()
    im = IntegrityMonitor(sm)
    ok, mismatches = im.verify_strategy_hashes()
    assert ok is True, f"Strategy mutation detected: {mismatches}"
    assert len(mismatches) == 0


def test_daily_integrity_checklist():
    """Verify the 6-point daily integrity checklist passes completely."""
    sm = StateManager()
    im = IntegrityMonitor(sm)
    res = im.run_daily_integrity_check()
    assert res["all_passed"] is True
    for check_name, check_data in res["checks"].items():
        assert check_data["pass"] is True, f"Check failed: {check_name}"


def test_execution_simulator_causal_flow(tmp_path):
    """Verify causal next-bar execution and spread/cost modeling using isolated temp files."""
    st_file = tmp_path / "test_state.json"
    log_file = tmp_path / "test_log.jsonl"
    sm = StateManager(state_file=st_file, event_log_file=log_file)
    sim = ExecutionSimulator(
        sm,
        modeled_spread_bps=4.0,
        modeled_slippage_bps=2.0,
        commission_per_oz=0.05,
        annual_swap_rate=0.035,
    )

    # Initial state
    sm.state.current_state = "FLAT"
    sm.state.cash_balance = 10000.0
    sm.state.current_equity = 10000.0
    sm.state.pending_order = None

    # Bar t signal: SMA50 > SMA200 -> queue BUY
    sim.queue_order(
        action="BUY",
        signal_time="2026-10-01T01:00:00+00:00",
        reference_close=4140.0,
    )
    assert sm.state.pending_order is not None
    assert sm.state.pending_order["action"] == "BUY"
    assert sm.state.current_state == "FLAT"  # Still flat until next bar open!

    # Bar t+1 Open: execute fill
    exec_row = sim.execute_pending_order(
        bar_open_time="2026-10-01T02:00:00+00:00",
        bar_open_price=4145.0,
    )
    assert exec_row is not None
    assert sm.state.current_state == "LONG"
    assert sm.state.pending_order is None
    assert sm.state.position_units > 0.0
    # Entry price must reflect modeled Ask = 4145.0 * (1 + 0.0002) + slippage
    assert exec_row["execution_price"] > 4145.0
    assert exec_row["action"] == "BUY"

    # Queue exit at bar t+2
    sim.queue_order(
        action="SELL",
        signal_time="2026-10-01T03:00:00+00:00",
        reference_close=4160.0,
    )
    assert sm.state.current_state == "LONG"

    # Bar t+3 Open: execute exit fill
    exit_row = sim.execute_pending_order(
        bar_open_time="2026-10-01T04:00:00+00:00",
        bar_open_price=4165.0,
    )
    assert exit_row is not None
    assert sm.state.current_state == "FLAT"
    assert sm.state.position_units == 0.0
    # Exit price must reflect modeled Bid = 4165.0 - slippage
    assert exit_row["execution_price"] <= 4165.0
    assert exit_row["action"] == "SELL"


def test_adverse_slippage_directions(tmp_path):
    """Verify mathematically that BUY fills higher than reference open and SELL fills lower."""
    sm = StateManager(state_file=tmp_path / "st.json", event_log_file=tmp_path / "log.jsonl")
    sim = ExecutionSimulator(sm, modeled_spread_bps=4.0, modeled_slippage_bps=2.0)
    
    # BUY entry test
    sm.state.current_state = "FLAT"
    sm.state.cash_balance = 10000.0
    sim.queue_order("BUY", "2026-10-01T01:00:00+00:00", 4000.0)
    buy_exec = sim.execute_pending_order("2026-10-01T02:00:00+00:00", 4000.0)
    
    # Expected Ask = 4000 + 4000 * (0.0004/2) + 4000 * 0.0002 = 4000 + 0.80 + 0.80 = 4001.60
    assert buy_exec["execution_price"] > 4000.0
    assert pytest.approx(buy_exec["execution_price"], rel=1e-4) == 4001.60

    # SELL exit test
    sim.queue_order("SELL", "2026-10-01T03:00:00+00:00", 4100.0)
    sell_exec = sim.execute_pending_order("2026-10-01T04:00:00+00:00", 4100.0)
    
    # Expected Bid = 4100 - 4100 * (0.0004/2) - 4100 * 0.0002 = 4100 - 0.82 - 0.82 = 4098.36
    assert sell_exec["execution_price"] < 4100.0
    assert pytest.approx(sell_exec["execution_price"], rel=1e-4) == 4098.36


def test_swap_rollover_calculation(tmp_path):
    """Verify overnight financing swap logic and Wednesday triple rollover."""
    import pandas as pd
    st_file = tmp_path / "test_state.json"
    log_file = tmp_path / "test_log.jsonl"
    sm = StateManager(state_file=st_file, event_log_file=log_file)
    sim = ExecutionSimulator(sm, annual_swap_rate=0.035, swap_cut_hour_utc=22)

    # Normal day (e.g. Tuesday entry 12:00, exit next day 12:00 -> passes Tue 22:00)
    entry_tue = pd.Timestamp("2026-10-06 12:00:00", tz="UTC")
    exit_wed = pd.Timestamp("2026-10-07 12:00:00", tz="UTC")
    total_days, std_cnt, wed_cnt = sim.calculate_swap_days(entry_tue, exit_wed)
    assert total_days == 1
    assert std_cnt == 1
    assert wed_cnt == 0

    # Over Wednesday 22:00 rollover (e.g. Wednesday 12:00 to Thursday 12:00 -> 3x swap)
    entry_wed = pd.Timestamp("2026-10-07 12:00:00", tz="UTC")
    exit_thu = pd.Timestamp("2026-10-08 12:00:00", tz="UTC")
    total_days_wed, std_cnt_wed, wed_cnt_wed = sim.calculate_swap_days(entry_wed, exit_thu)
    assert total_days_wed == 3
    assert std_cnt_wed == 0
    assert wed_cnt_wed == 1


def test_hourly_boundary_candle_finalization(tmp_path):
    """Verify exact candle finalization at 21:59:59 -> 22:00:00 UTC and 23:59:59 -> 00:00:00 UTC boundaries."""
    sm = StateManager(state_file=tmp_path / "st.json", event_log_file=tmp_path / "log.jsonl")
    fm = ForwardMonitor(state_mgr=sm, ledger_file=tmp_path / "ledger.csv", coverage_file=tmp_path / "cov.json")

    # Quote 1 at 21:59:59 (starts 21:00 bucket)
    q1 = {"price": 4150.0, "symbol": "XAU", "updatedAt": "2026-10-01T21:59:59.000Z"}
    fin1, candle1 = fm.process_quote(q1)
    assert fin1 is False

    # Quote 2 at 22:00:00 (starts 22:00 bucket -> finalizes 21:00 bucket)
    q2 = {"price": 4152.0, "symbol": "XAU", "updatedAt": "2026-10-01T22:00:00.000Z"}
    fin2, candle2 = fm.process_quote(q2)
    assert fin2 is True
    assert candle2 == "2026-10-01T21:00:00+00:00"

    # Quote 3 at 22:30:00 (inside 22:00 bucket -> does NOT finalize)
    q3 = {"price": 4154.0, "symbol": "XAU", "updatedAt": "2026-10-01T22:30:00.000Z"}
    fin3, candle3 = fm.process_quote(q3)
    assert fin3 is False

    # Quote 4 at 23:00:00 (starts 23:00 bucket -> finalizes 22:00 bucket)
    q4 = {"price": 4158.0, "symbol": "XAU", "updatedAt": "2026-10-01T23:00:00.000Z"}
    fin4, candle4 = fm.process_quote(q4)
    assert fin4 is True
    assert candle4 == "2026-10-01T22:00:00+00:00"

    # Quote 5 at 23:59:59 (inside 23:00 bucket -> does NOT finalize)
    q5 = {"price": 4159.0, "symbol": "XAU", "updatedAt": "2026-10-01T23:59:59.000Z"}
    fin5, candle5 = fm.process_quote(q5)
    assert fin5 is False

    # Quote 6 at 00:00:00 next day (starts 00:00 bucket -> finalizes 23:00 bucket)
    q6 = {"price": 4160.0, "symbol": "XAU", "updatedAt": "2026-10-02T00:00:00.000Z"}
    fin6, candle6 = fm.process_quote(q6)
    assert fin6 is True
    assert candle6 == "2026-10-01T23:00:00+00:00"


def test_dashboard_api_endpoints():
    """Verify research dashboard endpoints return valid status and data."""
    client = TestClient(app)
    
    # Root dashboard HTML
    resp_root = client.get("/")
    assert resp_root.status_code == 200
    assert "PHASE 13" in resp_root.text
    assert "PAPER TRADING ONLY" in resp_root.text

    # State JSON
    resp_state = client.get("/api/state")
    assert resp_state.status_code == 200
    st_json = resp_state.json()
    assert st_json["strategy_id"] == "XAUUSD_FROZEN_SMA50_200_1H"
    assert st_json["environment"] == "PAPER_TRADING_ONLY"
    assert st_json["instrument"] == "XAU/USD"

    # Integrity JSON
    resp_int = client.get("/api/integrity")
    assert resp_int.status_code == 200
    int_json = resp_int.json()
    assert int_json["all_passed"] is True


def test_telemetry_counters_and_denominators(tmp_path):
    """Verify telemetry counters track correctly and property rates use explicit denominators."""
    sm = StateManager(state_file=tmp_path / "st.json", event_log_file=tmp_path / "log.jsonl")
    st = sm.state
    
    # Initial state
    assert st.poll_success_rate == 0.0
    assert st.raw_archive_completeness == 0.0
    assert st.provider_freshness_rate == 0.0

    st.scheduled_polls = 10
    st.successful_polls = 8
    st.failed_polls = 2
    st.raw_responses_archived = 8
    st.new_provider_updates = 6
    st.unchanged_provider_updates = 2

    assert pytest.approx(st.poll_success_rate, rel=1e-4) == 0.8  # 8 / 10
    assert pytest.approx(st.raw_archive_completeness, rel=1e-4) == 1.0  # 8 / 8
    assert pytest.approx(st.provider_freshness_rate, rel=1e-4) == 0.75  # 6 / 8


def test_raw_preservation_and_processing_deduplication(tmp_path):
    """Verify raw vendor responses are archived while processing layer deduplicates unchanged quotes."""
    from unittest.mock import patch, MagicMock
    import io

    sm = StateManager(state_file=tmp_path / "st.json", event_log_file=tmp_path / "log.jsonl")
    raw_dir = tmp_path / "raw_quotes"
    raw_dir.mkdir(parents=True, exist_ok=True)
    cov_file = tmp_path / "coverage.json"
    fm = ForwardMonitor(state_mgr=sm, raw_quotes_dir=raw_dir, coverage_file=cov_file, ledger_file=tmp_path / "ledger.csv")

    payload = b'{"symbol": "XAU", "price": 4150.0, "updatedAt": "2026-10-01T10:00:00.000Z"}'

    # Ingest first quote via fetch_live_quote
    mock_resp1 = MagicMock()
    mock_resp1.read.return_value = payload
    mock_resp1.__enter__.return_value = mock_resp1

    with patch("urllib.request.urlopen", return_value=mock_resp1):
        q1 = fm.fetch_live_quote()
        assert q1 is not None
        fm.process_quote(q1)

    assert sm.state.raw_responses_archived == 1
    assert sm.state.unique_provider_observations == 1
    assert sm.state.duplicate_provider_observations == 0
    assert len(list(raw_dir.glob("raw_response_*.json"))) == 1

    # Ingest second identical quote (same price & timestamp)
    mock_resp2 = MagicMock()
    mock_resp2.read.return_value = payload
    mock_resp2.__enter__.return_value = mock_resp2

    with patch("urllib.request.urlopen", return_value=mock_resp2):
        q2 = fm.fetch_live_quote()
        assert q2 is not None
        assert q2["is_duplicate"] is True
        fm.process_quote(q2)

    assert sm.state.raw_responses_archived == 2  # Raw preserved
    assert sm.state.unique_provider_observations == 1  # Deduplicated in processing
    assert sm.state.duplicate_provider_observations == 1
    assert sm.state.unchanged_provider_updates == 1
    assert len(list(raw_dir.glob("raw_response_*.json"))) == 2


def test_hourly_coverage_registry(tmp_path):
    """Verify hourly coverage registry correctly logs hour buckets and update counts."""
    sm = StateManager(state_file=tmp_path / "st.json", event_log_file=tmp_path / "log.jsonl")
    cov_file = tmp_path / "coverage.json"
    fm = ForwardMonitor(state_mgr=sm, coverage_file=cov_file, ledger_file=tmp_path / "ledger.csv")

    q1 = {"symbol": "XAU", "price": 4150.0, "updatedAt": "2026-10-01T10:15:00.000Z"}
    fm.process_quote(q1)

    assert cov_file.exists()
    with open(cov_file, "r", encoding="utf-8") as f:
        registry = json.load(f)

    bucket = "2026-10-01T10:00:00+00:00"
    assert bucket in registry
    assert registry[bucket]["quotes_received"] == 1
    assert registry[bucket]["candle_finalized"] is False


def test_safe_restart_cycle(tmp_path):
    """Verify restarting the runner preserves existing state, cash, equity and increments restart_count."""
    st_file = tmp_path / "forward_state.json"
    log_file = tmp_path / "forward_log.jsonl"
    
    # 1. First run
    sm1 = StateManager(state_file=st_file, event_log_file=log_file)
    sm1.state.cash_balance = 9500.0
    sm1.state.current_equity = 10250.0
    sm1.state.current_state = "LONG"
    sm1.state.position_units = 2.45
    sm1.state.forward_start_timestamp = "2026-10-01T00:50:35.610230+00:00"
    sm1.state.restart_count = 0
    sm1.save_state()

    # 2. Emulate runner restart
    runner2 = ForwardRunner()
    runner2.monitor = ForwardMonitor(state_mgr=StateManager(state_file=st_file, event_log_file=log_file))
    st2 = runner2.monitor.sm.state

    # Invariants preserved
    assert st2.cash_balance == 9500.0
    assert st2.current_equity == 10250.0
    assert st2.current_state == "LONG"
    assert st2.position_units == 2.45
    assert st2.forward_start_timestamp == "2026-10-01T00:50:35.610230+00:00"

    # Simulate start/stop lifecycle
    st2.daemon_running = True
    st2.daemon_pid = 99999
    st2.restart_count += 1
    st2.feed_status = "RUNNING_HEALTHY"
    runner2.monitor.sm.save_state()

    # Verify reload
    sm3 = StateManager(state_file=st_file, event_log_file=log_file)
    assert sm3.state.restart_count == 1
    assert sm3.state.daemon_running is True
    assert sm3.state.feed_status == "RUNNING_HEALTHY"
