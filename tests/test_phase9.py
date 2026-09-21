"""Comprehensive unit tests for Phase 9A research infrastructure and data ingestion."""

import os
from pathlib import Path
import pytest
import numpy as np
import pandas as pd

from bot.config import BotConfig
from phase9.provenance import (
    compute_file_sha256,
    DatasetProvenanceRecord,
    SyntheticStatus,
    IndependenceStatus,
)
from phase9.dataset_registry import DatasetRegistry
from phase9.data_quality import (
    audit_timestamps,
    audit_ohlc,
    compute_statistical_profile,
    evaluate_asset_independence,
)
from phase9.hypothesis_registry import (
    HypothesisRegistry,
    HypothesisRecord,
    HypothesisStatus,
)
from phase9.economic_gate import (
    EconomicGate,
    ExecutionParameters,
)
from phase9.leakage_guard import (
    LeakageGuard,
    LeakageViolationError,
)
from phase9.split_manager import (
    SplitManager,
)
from phase9.ingestion.base import (
    DataSourceAdapter,
    SourceDiscoveryResult,
    NormalizedMarketData,
)
from phase9.ingestion.coinbase import CoinbaseAdapter
from phase9.ingestion.kraken import KrakenAdapter
from phase9.ingestion.okx import OKXAdapter
from phase9.ingestion.binance_us import BinanceUSAdapter


# ---------------------------------------------------------------------------
# 1. Safety Invariants Tests
# ---------------------------------------------------------------------------

def test_phase9_safety_invariants():
    """Confirms Phase 9 strictly inherits and enforces all safety guardrails."""
    cfg = BotConfig.from_env()
    assert cfg.paper_trading_only is True
    assert cfg.leverage == 1.0
    use_live_jev = os.getenv("USE_LIVE_JEV", "false").strip().lower() in ("true", "1")
    assert use_live_jev is False


# ---------------------------------------------------------------------------
# 2. Provenance & Registry Tests
# ---------------------------------------------------------------------------

def test_provenance_sha256_determinism(tmp_path):
    """Verifies that compute_file_sha256 produces deterministic hashes."""
    test_file = tmp_path / "sample.csv"
    test_file.write_text("timestamp,close\n1000,100.0\n2000,101.0\n", encoding="utf-8")
    hash1 = compute_file_sha256(test_file)
    hash2 = compute_file_sha256(test_file)
    assert hash1 == hash2
    assert len(hash1) == 64


def test_dataset_registration_and_immutability(tmp_path):
    """Verifies dataset registration, retrieval, and prevention of silent overwrites."""
    reg_path = tmp_path / "test_reg.json"
    registry = DatasetRegistry(storage_path=reg_path)

    f1 = tmp_path / "data1.csv"
    f1.write_text("timestamp,open,high,low,close,volume\n100,1,2,1,2,10\n", encoding="utf-8")

    rec1 = DatasetProvenanceRecord(
        dataset_id="TEST_DATASET_V1",
        asset="BTC",
        symbol="BTCUSDT",
        exchange="TEST_EXCHANGE",
        market_type="SPOT",
        instrument_type="CANDLE",
        timeframe="5m",
        start_timestamp="100",
        end_timestamp="100",
        row_count=1,
        source="TEST_SOURCE",
        source_url="http://test",
        retrieval_timestamp="2026-09-22T00:00:00Z",
        synthetic_status=SyntheticStatus.GENUINE,
        independence_status=IndependenceStatus.INDEPENDENT,
        file_path=str(f1),
    )
    registry.register_dataset(rec1)
    retrieved = registry.get_dataset("TEST_DATASET_V1")
    assert retrieved.dataset_id == "TEST_DATASET_V1"
    assert retrieved.sha256 != ""

    # Attempting to register different content under same ID without overwrite flag must fail
    f2 = tmp_path / "data2.csv"
    f2.write_text("timestamp,open,high,low,close,volume\n100,5,5,5,5,50\n", encoding="utf-8")
    rec2 = DatasetProvenanceRecord(
        dataset_id="TEST_DATASET_V1",
        asset="BTC",
        symbol="BTCUSDT",
        exchange="TEST_EXCHANGE",
        market_type="SPOT",
        instrument_type="CANDLE",
        timeframe="5m",
        start_timestamp="100",
        end_timestamp="100",
        row_count=1,
        source="TEST_SOURCE",
        source_url="http://test",
        retrieval_timestamp="2026-09-22T00:00:00Z",
        synthetic_status=SyntheticStatus.GENUINE,
        independence_status=IndependenceStatus.INDEPENDENT,
        file_path=str(f2),
    )
    with pytest.raises(ValueError, match="already exists with different hash"):
        registry.register_dataset(rec2, overwrite=False)


def test_register_historical_phase_datasets(tmp_path):
    """Verifies historical datasets are registered with correct synthetic and independence statuses."""
    reg_path = tmp_path / "hist_reg.json"
    registry = DatasetRegistry(storage_path=reg_path)
    registry.register_historical_phase_datasets(base_dir="data/historical")

    datasets = registry.list_datasets()
    assert len(datasets) == 3

    btc = registry.get_dataset("HIST_BTCUSDT_5M_202401_V1")
    assert btc.synthetic_status == SyntheticStatus.GENUINE
    assert btc.independence_status == IndependenceStatus.INDEPENDENT

    eth = registry.get_dataset("HIST_ETHUSDT_5M_202401_V1")
    assert eth.synthetic_status == SyntheticStatus.SYNTHETIC
    assert eth.independence_status == IndependenceStatus.NON_INDEPENDENT

    sol = registry.get_dataset("HIST_SOLUSDT_5M_202401_V1")
    assert sol.synthetic_status == SyntheticStatus.SYNTHETIC
    assert sol.independence_status == IndependenceStatus.NON_INDEPENDENT


# ---------------------------------------------------------------------------
# 3. Data Quality & Synthetic Detection Tests
# ---------------------------------------------------------------------------

def test_timestamp_auditor():
    """Tests timestamp gap detection, duplicates, and monotonicity."""
    # Clean monotonic
    df_clean = pd.DataFrame({"timestamp": [1000, 2000, 3000, 4000]})
    res_clean = audit_timestamps(df_clean, expected_interval_ms=1000)
    assert res_clean.is_valid is True
    assert res_clean.gap_count == 0

    # Gap present
    df_gap = pd.DataFrame({"timestamp": [1000, 2000, 5000, 6000]})
    res_gap = audit_timestamps(df_gap, expected_interval_ms=1000)
    assert res_gap.is_valid is False
    assert res_gap.gap_count == 1
    assert res_gap.gaps[0]["missing_bars"] == 2

    # Duplicates
    df_dup = pd.DataFrame({"timestamp": [1000, 2000, 2000, 3000]})
    res_dup = audit_timestamps(df_dup, expected_interval_ms=1000)
    assert res_dup.has_duplicates is True
    assert res_dup.duplicate_count == 1


def test_ohlc_invariants_auditor():
    """Verifies detection of invalid OHLC relationships."""
    df_valid = pd.DataFrame({
        "open": [100.0, 102.0],
        "high": [105.0, 106.0],
        "low": [99.0, 101.0],
        "close": [103.0, 104.0],
        "volume": [50.0, 60.0],
    })
    res_valid = audit_ohlc(df_valid)
    assert res_valid.is_valid is True

    # High < Low violation
    df_invalid = pd.DataFrame({
        "open": [100.0],
        "high": [90.0],  # Invalid: high < open/low
        "low": [95.0],
        "close": [98.0],
        "volume": [10.0],
    })
    res_invalid = audit_ohlc(df_invalid)
    assert res_invalid.is_valid is False
    assert res_invalid.violations_high > 0


def test_synthetic_scaled_detection():
    """Verifies that mathematical independence detection flags scaled series (like DISC-001)."""
    np.random.seed(42)
    n = 200
    timestamps = np.arange(1000, 1000 + n * 300_000, 300_000)
    btc_prices = 60000.0 + np.cumsum(np.random.normal(5, 50, size=n))
    btc_vols = np.random.exponential(100, size=n)

    df_btc = pd.DataFrame({"timestamp": timestamps, "close": btc_prices, "volume": btc_vols})

    # Synthetic scaled ETH
    eth_prices = btc_prices * 0.05
    df_eth_scaled = pd.DataFrame({"timestamp": timestamps, "close": eth_prices, "volume": btc_vols * 10})

    res_scaled = evaluate_asset_independence(df_btc, df_eth_scaled, asset_a="BTC", asset_b="ETH_SCALED")
    assert res_scaled.is_suspicious is True
    assert res_scaled.verdict == "SYNTHETIC_SCALED"
    assert res_scaled.pearson_return_corr > 0.9999

    # Independent asset with genuine drift
    independent_prices = 3000.0 + np.cumsum(np.random.normal(-2, 30, size=n))
    df_indep = pd.DataFrame({"timestamp": timestamps, "close": independent_prices, "volume": btc_vols * 2})

    res_indep = evaluate_asset_independence(df_btc, df_indep, asset_a="BTC", asset_b="INDEP_ASSET")
    assert res_indep.is_suspicious is False
    assert res_indep.verdict == "INDEPENDENT"


# ---------------------------------------------------------------------------
# 4. Hypothesis Registry Tests
# ---------------------------------------------------------------------------

def test_hypothesis_registry(tmp_path):
    """Verifies registration and status lifecycle of hypotheses H1–H8."""
    hyp_path = tmp_path / "hypotheses.json"
    reg = HypothesisRegistry(storage_path=hyp_path)
    all_hyp = reg.list_all()
    assert len(all_hyp) == 8

    h1 = reg.get("H1_ORDERBOOK_IMBALANCE")
    assert h1.status == HypothesisStatus.PREREGISTERED
    assert h1.economic_hurdle_bps == 20.0

    reg.update_status("H1_ORDERBOOK_IMBALANCE", HypothesisStatus.DATA_PENDING, notes="Awaiting L2 orderbook data")
    h1_updated = reg.get("H1_ORDERBOOK_IMBALANCE")
    assert h1_updated.status == HypothesisStatus.DATA_PENDING
    assert "Awaiting" in h1_updated.evaluation_notes


# ---------------------------------------------------------------------------
# 5. Dynamic Economic Gate Tests
# ---------------------------------------------------------------------------

def test_economic_gate_hurdle_and_monotonicity():
    """Verifies that the economic gate computes accurate hurdles and exhibits monotonicity."""
    gate = EconomicGate()
    breakdown = gate.compute_round_trip_cost()
    # 20 bps fee + 5 bps spread + 6 bps slippage + 4 bps impact + 2 bps latency + 3 bps adverse = 40 bps friction
    assert breakdown["total_friction_bps"] == 40.0
    assert breakdown["required_hurdle_bps"] == 50.0  # + 10 bps safety margin

    # Evaluation with 60 bps gross edge -> Net edge = 20 bps, Margin = 10 bps -> Viable
    eval_viable = gate.evaluate(60.0)
    assert eval_viable.is_economically_viable is True
    assert eval_viable.classification == "ECONOMICALLY_VIABLE"
    assert eval_viable.net_edge_bps == 20.0

    # Evaluation with 45 bps gross edge -> Net edge = 5 bps, Margin = -5 bps -> Predictive only
    eval_pred = gate.evaluate(45.0)
    assert eval_pred.is_economically_viable is False
    assert eval_pred.classification == "PREDICTIVE_ONLY"

    # Evaluation with 20 bps gross edge -> Net edge = -20 bps -> Friction dominated
    eval_fric = gate.evaluate(20.0)
    assert eval_fric.is_economically_viable is False
    assert eval_fric.classification == "FRICTION_DOMINATED"

    # Monotonicity test: Higher gross edge must produce strictly higher net edge and economic margin
    edges = [-10.0, 0.0, 20.0, 40.0, 50.0, 70.0]
    net_edges = [gate.evaluate(e).net_edge_bps for e in edges]
    assert np.all(np.diff(net_edges) > 0)


def test_exchange_specific_presets():
    """Verifies exchange presets provide realistic differing friction models."""
    gate_cb = EconomicGate.get_exchange_preset("COINBASE")
    gate_okx = EconomicGate.get_exchange_preset("OKX")
    cost_cb = gate_cb.compute_round_trip_cost()["total_friction_bps"]
    cost_okx = gate_okx.compute_round_trip_cost()["total_friction_bps"]
    assert cost_cb > cost_okx  # Coinbase standard tier fee is higher than OKX VIP0


# ---------------------------------------------------------------------------
# 6. Causality & Perturbation Guard Tests
# ---------------------------------------------------------------------------

def test_leakage_guard_future_perturbation():
    """Verifies that causal feature extractors pass and non-causal extractors fail perturbation tests."""
    n = 100
    df = pd.DataFrame({
        "timestamp": np.arange(1000, 1000 + n * 1000, 1000),
        "open": np.linspace(100, 200, n),
        "high": np.linspace(105, 205, n),
        "low": np.linspace(95, 195, n),
        "close": np.linspace(102, 202, n),
        "volume": np.full(n, 50.0),
    })

    # Causal feature: rolling 10-bar mean of past closes
    def causal_features(data: pd.DataFrame) -> pd.DataFrame:
        res = pd.DataFrame()
        res["ema"] = data["close"].rolling(10, min_periods=1).mean()
        return res

    res_causal = LeakageGuard.test_future_perturbation(df, causal_features, target_bar_idx=40)
    assert res_causal["is_causal"] is True
    assert res_causal["max_delta"] == 0.0

    # Non-causal feature: lead / forward close (look-ahead)
    def non_causal_features(data: pd.DataFrame) -> pd.DataFrame:
        res = pd.DataFrame()
        res["future_close"] = data["close"].shift(-3)  # Looks 3 bars into future!
        return res

    res_non_causal = LeakageGuard.test_future_perturbation(df, non_causal_features, target_bar_idx=40)
    assert res_non_causal["is_causal"] is False
    assert res_non_causal["max_delta"] > 0.0


# ---------------------------------------------------------------------------
# 7. Chronological Splits & Holdout Tests
# ---------------------------------------------------------------------------

def test_chronological_split_manager(tmp_path):
    """Verifies strictly chronological partitions without overlap and manifest sealing."""
    n = 500
    df = pd.DataFrame({
        "timestamp": np.arange(1000, 1000 + n * 1000, 1000),
        "close": np.random.normal(100, 2, size=n),
    })

    dev_df, val_df, holdout_df, split_res = SplitManager.partition(
        df, dataset_id="TEST_PARTITION", dev_ratio=0.60, val_ratio=0.20
    )

    assert len(dev_df) == 300
    assert len(val_df) == 100
    assert len(holdout_df) == 100
    assert split_res.is_strictly_chronological is True
    assert split_res.is_disjoint is True

    # Seal manifest
    manifest_file = tmp_path / "holdout_manifest.json"
    SplitManager.seal_holdout_manifest(split_res, manifest_path=manifest_file)
    assert manifest_file.exists()


# ---------------------------------------------------------------------------
# 8. Ingestion Adapters Discovery & Normalization Tests
# ---------------------------------------------------------------------------

def test_ingestion_adapter_normalization():
    """Verifies schema validation and canonical normalization logic on adapters."""
    cb = CoinbaseAdapter()
    kr = KrakenAdapter()
    okx = OKXAdapter()
    bus = BinanceUSAdapter()

    assert cb.get_source_name() == "COINBASE"
    assert kr.get_source_name() == "KRAKEN"
    assert okx.get_source_name() == "OKX"
    assert bus.get_source_name() == "BINANCE_US"

    # Test candle validation helper
    df_good = pd.DataFrame({
        "timestamp": [1000, 2000, 3000],
        "open": [10, 11, 12],
        "high": [12, 13, 14],
        "low": [9, 10, 11],
        "close": [11, 12, 13],
        "volume": [100, 150, 200],
    })
    is_valid, _ = cb.validate_normalized_data(df_good, "CANDLE")
    assert is_valid is True

    # Test orderbook validation helper
    df_ob = pd.DataFrame({
        "timestamp": [1000, 1000],
        "side": ["BID", "ASK"],
        "price": [100.0, 101.0],
        "quantity": [1.5, 2.0],
        "level": [1, 1],
    })
    is_ob_valid, _ = cb.validate_normalized_data(df_ob, "ORDERBOOK_L2")
    assert is_ob_valid is True


@pytest.mark.asyncio
async def test_ingestion_adapter_discover_connectivity():
    """Tests discovery probing against reachable endpoints."""
    adapters = [KrakenAdapter(), CoinbaseAdapter(), OKXAdapter(), BinanceUSAdapter()]
    results = []
    for adapter in adapters:
        res = await adapter.discover()
        assert isinstance(res, SourceDiscoveryResult)
        assert res.source != ""
        assert len(res.available_assets) > 0
        results.append(res)

    # Confirm that at least one external public adapter is AVAILABLE
    available_sources = [r.source for r in results if r.status == "AVAILABLE"]
    assert len(available_sources) >= 1
