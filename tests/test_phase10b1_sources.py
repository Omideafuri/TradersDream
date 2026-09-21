"""Unit tests for Phase 10B.1 Historical Event-Data Source Discovery and Feasibility."""

import json
import os
from pathlib import Path
import pytest

from bot.config import BotConfig
from phase10b.models import (
    TickTrade,
    L2Delta,
    L2Snapshot,
    BookSide,
    AggressorSide,
)
from phase10b.reconstructor import OrderBookReconstructor


def test_phase10b1_artifacts_exist():
    """Verify all required Phase 10B.1 documentation and manifests exist and are populated."""
    repo_root = Path(__file__).resolve().parent.parent

    research_doc = repo_root / "PHASE10B1_HISTORICAL_DATA_SOURCE_RESEARCH.md"
    source_reg = repo_root / "phase10b1" / "manifests" / "source_registry.json"
    sample_man = repo_root / "phase10b1" / "manifests" / "sample_manifest.json"
    acq_log = repo_root / "phase10b1" / "manifests" / "acquisition_log.json"
    comparison = repo_root / "phase10b1" / "reports" / "source_comparison.md"
    val_report = repo_root / "phase10b1" / "reports" / "source_validation_report.json"
    feasibility = repo_root / "phase10b1" / "reports" / "acquisition_feasibility.md"

    for p in [research_doc, source_reg, sample_man, acq_log, comparison, val_report, feasibility]:
        assert p.is_file(), f"Missing required Phase 10B.1 artifact: {p.name}"
        assert p.stat().st_size > 100, f"Artifact unexpectedly empty: {p.name}"


def test_source_registry_schema_and_qualifications():
    """Verify source registry structure, evaluated providers, and qualification statuses."""
    repo_root = Path(__file__).resolve().parent.parent
    reg_path = repo_root / "phase10b1" / "manifests" / "source_registry.json"

    data = json.loads(reg_path.read_text(encoding="utf-8"))
    assert "candidate_sources" in data
    sources = {s["provider"]: s for s in data["candidate_sources"]}

    assert "Tardis.dev" in sources
    assert "Kaiko" in sources
    assert "Binance Data Vision (Official)" in sources
    assert "Coinbase Exchange Native REST" in sources
    assert "Databento" in sources

    # Verify Tardis qualification
    tardis = sources["Tardis.dev"]
    assert tardis["trade_data"]["available"] is True
    assert tardis["l2_data"]["available"] is True
    assert tardis["snapshot_data"]["available"] is True
    assert "BTCUSDT" in tardis["symbols"]
    assert "ETHUSDT" in tardis["symbols"]
    assert "SOLUSDT" in tardis["symbols"]
    assert tardis["qualification_status"] == "QUALIFIED_PAID_ACCESS_REQUIRED"

    # Verify Binance Vision limitation
    bvision = sources["Binance Data Vision (Official)"]
    assert bvision["trade_data"]["available"] is True
    assert bvision["l2_data"]["available"] is False
    assert "MISSING_L2_DELTAS" in bvision["qualification_status"]


def test_sample_manifest_fields():
    """Verify sample manifest contents and schema integrity."""
    repo_root = Path(__file__).resolve().parent.parent
    man_path = repo_root / "phase10b1" / "manifests" / "sample_manifest.json"

    data = json.loads(man_path.read_text(encoding="utf-8"))
    required_keys = [
        "provider",
        "exchange",
        "symbol",
        "instrument_type",
        "event_type",
        "coverage_start",
        "coverage_end",
        "event_count",
        "raw_filename",
        "file_size_bytes",
        "sha256",
        "source_format",
        "timestamp_resolution",
        "sequence_identifier",
        "snapshot_available",
        "provenance",
        "validation_status",
    ]
    for k in required_keys:
        assert k in data, f"Missing key '{k}' in sample_manifest.json"

    assert data["provider"] == "Tardis.dev"
    assert data["symbol"] == "BTCUSDT"
    assert data["timestamp_resolution"] == "microsecond"
    assert data["validation_status"] == "DOCUMENTATION_AND_SCHEMA_VERIFIED"


def test_tardis_schema_integration_with_phase10b_engine():
    """Test mapping simulated Tardis normalized rows directly into Phase 10B Reconstructor."""
    # Simulated Tardis snapshot row (is_snapshot=True)
    tardis_snapshot_rows = [
        {"side": "bid", "price": "50000.0", "amount": "1.5", "timestamp": "1700000000000000"},
        {"side": "ask", "price": "50010.0", "amount": "1.0", "timestamp": "1700000000000000"},
    ]

    snapshot = L2Snapshot(
        symbol="BTCUSDT",
        exchange="BINANCE_US",
        exchange_timestamp_ms=int(int(tardis_snapshot_rows[0]["timestamp"]) / 1000),
        sequence_id=1,
        bids=[(float(r["price"]), float(r["amount"])) for r in tardis_snapshot_rows if r["side"] == "bid"],
        asks=[(float(r["price"]), float(r["amount"])) for r in tardis_snapshot_rows if r["side"] == "ask"],
    )

    reconstructor = OrderBookReconstructor("BTCUSDT", "BINANCE_US")
    state = reconstructor.load_snapshot(snapshot)
    assert state.best_bid == 50000.0
    assert state.best_ask == 50010.0

    # Simulated Tardis delta row (is_snapshot=False)
    tardis_delta_row = {
        "side": "bid",
        "price": "50005.0",
        "amount": "2.0",
        "timestamp": "1700000000010000",
    }
    delta = L2Delta(
        symbol="BTCUSDT",
        exchange="BINANCE_US",
        exchange_timestamp_ms=int(int(tardis_delta_row["timestamp"]) / 1000),
        sequence_id=2,
        side=BookSide.BID if tardis_delta_row["side"] == "bid" else BookSide.ASK,
        price=float(tardis_delta_row["price"]),
        quantity=float(tardis_delta_row["amount"]),
    )

    new_state = reconstructor.apply_delta(delta)
    assert new_state.best_bid == 50005.0
    assert new_state.spread == 5.0


def test_safety_invariants_and_zero_financial_commitment():
    """Verify safety invariants and confirm no live trading or purchase flags exist."""
    cfg = BotConfig.from_env()
    assert cfg.paper_trading_only is True
    assert cfg.leverage == 1.0
    use_live_jev = os.getenv("USE_LIVE_JEV", "false").strip().lower() in ("true", "1")
    assert use_live_jev is False

    repo_root = Path(__file__).resolve().parent.parent
    feasibility = (repo_root / "phase10b1" / "reports" / "acquisition_feasibility.md").read_text(encoding="utf-8")
    assert "DO NOT BUY ANYTHING WITHOUT EXPLICIT USER AUTHORIZATION" in feasibility
    assert "PAID ACQUISITION REQUIRED" in feasibility


def test_phase9_and_freeze_integrity():
    """Verify that RESEARCH_FREEZE.md and Phase 9/10A artifacts remain untouched."""
    repo_root = Path(__file__).resolve().parent.parent
    freeze = repo_root / "RESEARCH_FREEZE.md"
    assert freeze.is_file()
    assert "MASTER_CLASSIFICATION:  NOT_SUPPORTED" in freeze.read_text(encoding="utf-8")

    spec10a = repo_root / "PHASE10A_PASSIVE_EXECUTION_RESEARCH_SPEC.md"
    assert spec10a.is_file()
