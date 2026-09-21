"""Comprehensive unit tests for Phase 9B independent data acquisition, validation & holdout sealing."""

import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import pytest
import numpy as np
import pandas as pd

from phase9.backfill import PaginatedBackfillEngine, BackfillError
from phase9.data_quality import (
    audit_timestamps,
    audit_ohlc,
    compute_statistical_profile,
    evaluate_asset_independence,
    compare_cross_source_datasets,
)
from phase9.dataset_registry import DatasetRegistry
from phase9.holdout import Phase9HoldoutManager
from phase9.ingestion.base import DataSourceAdapter, NormalizedMarketData, SourceDiscoveryResult
from phase9.leakage_guard import LeakageGuard
from phase9.provenance import (
    compute_file_sha256,
    DatasetProvenanceRecord,
    SyntheticStatus,
    IndependenceStatus,
)
from phase9.split_manager import SplitManager


# Mock Adapter for deterministic unit testing
class MockFlakyAdapter(DataSourceAdapter):
    """Mock adapter that simulates pagination, duplicate keys, and intermittent network retries."""

    def __init__(self, total_available_bars: int = 2500, fail_attempts: int = 1):
        super().__init__()
        self.total_available_bars = total_available_bars
        self.fail_attempts = fail_attempts
        self.call_count = 0
        base_ts = 1700000000000
        # Create deterministic synthetic bars with 5m spacing
        timestamps = [base_ts + i * 300_000 for i in range(total_available_bars)]
        self.all_candles = []
        for i, ts in enumerate(timestamps):
            price = 50000.0 + i * 2.0
            self.all_candles.append({
                "timestamp": ts,
                "open": price,
                "high": price + 5.0,
                "low": price - 5.0,
                "close": price + 1.0,
                "volume": 10.0 + (i % 50),
            })

    def get_source_name(self) -> str:
        return "MOCK_FLAKY"

    async def discover(self) -> SourceDiscoveryResult:
        return SourceDiscoveryResult(
            source="MOCK",
            status="AVAILABLE",
            available_assets=["BTCUSDT"],
            available_time_range="Full",
            available_timeframes=["5m"],
            microstructure_available={"orderbook_l2": False, "trade_flow": False, "funding_rate": False, "open_interest": False},
            rate_limit="None",
            data_format="JSON",
            license_access_notes="Test mock",
        )

    async def download_candles(self, symbol: str, interval: str = "5m", limit: int = 1000, end_ts: int | None = None) -> NormalizedMarketData:
        self.call_count += 1
        if self.call_count <= self.fail_attempts:
            raise ConnectionError("Simulated transient connection timeout")

        if end_ts is None:
            filtered = self.all_candles
        else:
            filtered = [c for c in self.all_candles if c["timestamp"] <= end_ts]

        page = filtered[-limit:] if len(filtered) > limit else filtered
        df = pd.DataFrame(page)

        return NormalizedMarketData(
            symbol=symbol,
            instrument_type="CANDLE",
            timeframe=interval,
            df=df,
            raw_payload=[],
            row_count=len(df),
            sha256="mock_hash",
            is_valid=True,
        )

    async def download_orderbook(self, symbol: str, depth: int = 50) -> NormalizedMarketData:
        return NormalizedMarketData(symbol, "ORDERBOOK_L2", "snapshot", pd.DataFrame(), [], 0, "", True)

    async def download_trades(self, symbol: str, limit: int = 100) -> NormalizedMarketData:
        return NormalizedMarketData(symbol, "TRADE_FLOW", "tick", pd.DataFrame(), [], 0, "", True)


# ---------------------------------------------------------------------------
# 1. Backfill Pagination, Retry, and Resumability Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_paginated_backfill_retry_and_resumability(tmp_path):
    """Verifies pagination across multiple pages, exponential backoff retries, and checkpoint resumption."""
    mock_adapter = MockFlakyAdapter(total_available_bars=2500, fail_attempts=1)
    ckpt_dir = tmp_path / "checkpoints"
    out_file = tmp_path / "backfill_out.csv"

    engine = PaginatedBackfillEngine(
        adapter=mock_adapter,
        checkpoint_dir=ckpt_dir,
        batch_limit=1000,
        rate_limit_delay_seconds=0.01,
        max_retries=3,
    )

    # First backfill: Target 1,500 bars
    df1 = await engine.backfill(
        symbol="BTCUSDT",
        interval="5m",
        target_bars=1500,
        output_file=out_file,
        resume=True,
    )
    assert len(df1) == 1500
    assert out_file.exists()
    assert mock_adapter.call_count >= 2  # 1 failure + 2 successful batches

    # Verify checkpoint exists
    ckpt = engine.load_checkpoint("BTCUSDT", "5m")
    assert ckpt["total_downloaded"] >= 1500

    # Resume backfill to target 2,200 bars
    df2 = await engine.backfill(
        symbol="BTCUSDT",
        interval="5m",
        target_bars=2200,
        output_file=out_file,
        resume=True,
    )
    assert len(df2) == 2200
    assert df2["timestamp"].is_monotonic_increasing


@pytest.mark.asyncio
async def test_backfill_corrupted_dataset_rejection(tmp_path):
    """Verifies that pages with malformed OHLC or timestamps trigger validation failure and retry."""
    class MalformedPageAdapter(MockFlakyAdapter):
        async def download_candles(self, symbol: str, interval: str = "5m", limit: int = 1000, end_ts: int | None = None) -> NormalizedMarketData:
            # Return invalid OHLC (High < Low)
            bad_df = pd.DataFrame([{
                "timestamp": 1700000000000,
                "open": 100.0,
                "high": 80.0,  # Invalid
                "low": 90.0,
                "close": 95.0,
                "volume": 10.0,
            }])
            is_val, notes = self.validate_normalized_data(bad_df, "CANDLE")
            return NormalizedMarketData(
                symbol=symbol, instrument_type="CANDLE", timeframe=interval,
                df=bad_df, raw_payload=[], row_count=1, sha256="", is_valid=is_val, validation_notes=notes
            )

    bad_adapter = MalformedPageAdapter(total_available_bars=10, fail_attempts=0)
    engine = PaginatedBackfillEngine(adapter=bad_adapter, checkpoint_dir=tmp_path, max_retries=2, rate_limit_delay_seconds=0.01)

    with pytest.raises(BackfillError, match="Failed to fetch batch"):
        await engine.fetch_batch_with_retry("BTCUSDT", "5m", 10, None)


# ---------------------------------------------------------------------------
# 2. Duplicate Removal & Gap Detection Tests
# ---------------------------------------------------------------------------

def test_duplicate_removal_and_gap_accounting():
    """Verifies accounting of gaps and deduplication behavior."""
    timestamps = [1000, 2000, 2000, 3000, 6000]  # Duplicate at 2000, gap between 3000 and 6000
    df = pd.DataFrame({
        "timestamp": timestamps,
        "open": [10, 10, 10, 11, 12],
        "high": [12, 12, 12, 13, 14],
        "low": [9, 9, 9, 10, 11],
        "close": [11, 11, 11, 12, 13],
        "volume": [1, 1, 1, 1, 1],
    })

    audit_before = audit_timestamps(df, expected_interval_ms=1000)
    assert audit_before.has_duplicates is True
    assert audit_before.duplicate_count == 1
    assert audit_before.gap_count == 1

    # Remove duplicates
    df_dedup = df.drop_duplicates(subset=["timestamp"]).reset_index(drop=True)
    audit_after = audit_timestamps(df_dedup, expected_interval_ms=1000)
    assert audit_after.has_duplicates is False
    assert audit_after.gap_count == 1  # Gap still correctly flagged


# ---------------------------------------------------------------------------
# 3. Cross-Source Validation Tests
# ---------------------------------------------------------------------------

def test_cross_source_validation_metrics():
    """Verifies that comparison between two legitimate exchanges returns high return correlation and minor price spread."""
    n = 100
    ts = [1000 + i * 300_000 for i in range(n)]
    np.random.seed(123)
    p_base = 65000.0 + np.cumsum(np.random.normal(5, 30, n))

    # Exchange A prices
    df_a = pd.DataFrame({"timestamp": ts, "close": p_base, "volume": np.full(n, 10.0)})
    # Exchange B prices: ~0.01% spread deviation and independent volume
    p_b = p_base * (1.0 + np.random.normal(0.00002, 0.00005, n))
    df_b = pd.DataFrame({"timestamp": ts, "close": p_b, "volume": np.full(n, 15.0)})

    res = compare_cross_source_datasets(df_a, df_b, source_a="EX_A", source_b="EX_B", asset="BTC")
    assert res.overlapping_bars == n
    assert res.pearson_return_corr > 0.85
    assert res.price_mean_pct_diff < 0.20
    assert res.is_consistent is True


# ---------------------------------------------------------------------------
# 4. Holdout Sealing & Immutability Tests
# ---------------------------------------------------------------------------

def test_holdout_manager_sealing_and_manifest(tmp_path):
    """Verifies holdout manager seals 60/20/20 boundaries with immutable hashes and manifest generation."""
    n = 1000
    df = pd.DataFrame({
        "timestamp": [1000 + i * 300_000 for i in range(n)],
        "open": np.full(n, 100.0),
        "high": np.full(n, 105.0),
        "low": np.full(n, 95.0),
        "close": np.full(n, 102.0),
        "volume": np.full(n, 50.0),
    })

    json_manifest = tmp_path / "holdout.json"
    md_manifest = tmp_path / "holdout.md"
    mgr = Phase9HoldoutManager(manifest_json_path=json_manifest, manifest_md_path=md_manifest)

    rec = mgr.seal_dataset(df, asset="BTC", symbol="BTCUSDT")
    assert rec.total_rows == 1000
    assert rec.dev_rows == 600
    assert rec.validation_rows == 200
    assert rec.holdout_rows == 200
    assert len(rec.holdout_sha256) == 64

    mgr.save_manifests()
    assert json_manifest.exists()
    assert md_manifest.exists()

    with open(json_manifest, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "BTC" in data["assets"]
    assert data["assets"]["BTC"]["holdout_rows"] == 200


# ---------------------------------------------------------------------------
# 5. Asset Independence Rigor Tests
# ---------------------------------------------------------------------------

def test_asset_independence_scaling_detector():
    """Confirms synthetic scaled assets are rejected with SYNTHETIC_SCALED, while real uncorrelated drift passes."""
    n = 300
    ts = [1000 + i * 300_000 for i in range(n)]
    np.random.seed(99)
    btc_p = 60000.0 + np.cumsum(np.random.normal(5, 50, n))
    btc_df = pd.DataFrame({"timestamp": ts, "close": btc_p, "volume": np.full(n, 10.0)})

    # 1. Deterministic scaled asset (ETH = BTC * 0.05 + minor epsilon)
    scaled_p = btc_p * 0.05
    scaled_df = pd.DataFrame({"timestamp": ts, "close": scaled_p, "volume": np.full(n, 20.0)})
    indep_scaled = evaluate_asset_independence(btc_df, scaled_df, asset_a="BTC", asset_b="ETH_SCALED")
    assert indep_scaled.verdict == "SYNTHETIC_SCALED"
    assert indep_scaled.is_suspicious is True

    # 2. Genuinely independent asset (different drift and volatility dynamics)
    indep_p = 3500.0 + np.cumsum(np.random.normal(-2, 25, n))
    indep_df = pd.DataFrame({"timestamp": ts, "close": indep_p, "volume": np.full(n, 50.0)})
    indep_real = evaluate_asset_independence(btc_df, indep_df, asset_a="BTC", asset_b="ETH_REAL")
    assert indep_real.verdict == "INDEPENDENT"
    assert indep_real.is_suspicious is False
