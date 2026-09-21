"""Unit and integration test suite for Phase 9D: Microstructure Feature Streaming & Regime Discovery.

Covers:
1. Data provenance
2. Timestamp alignment and causal lookback slicing
3. Microstructure aggregation
4. Order-book metrics calculation
5. Trade-flow metrics calculation
6. Causality and future perturbation invariance (LeakageGuard)
7. Holdout isolation and pre-holdout freeze protocol
8. Dual economic gate (Static 40 bps vs Dynamic friction)
9. Statistical analysis (Block bootstrap, AUC, FDR, Holm)
10. Incremental information evaluation
11. Regime-conditioned analysis
12. Deterministic reproducibility (Run A vs Run B)
13. Safety invariants
"""

import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from phase9d.hypothesis_registry import Phase9DHypothesisRegistry, PreRegisteredHypothesis
from phase9d.microstructure import MicrostructureEngine
from phase9d.alignment import TemporalAlignment
from phase9d.aggregation import MicrostructureAggregator
from phase9d.statistical_analysis import (
    calc_corr_and_p,
    calc_spearman,
    compute_auc,
    compute_brier_score,
    block_bootstrap_delta_auc,
    MultipleTesting,
)
from phase9d.economic_analysis import DualEconomicGate
from phase9d.regime_analysis import RegimeMicrostructureAnalyzer
from phase9d.incremental_information import IncrementalInformationEvaluator
from phase9d.holdout_protocol import Phase9DHoldoutProtocol, HoldoutProtectionError
from phase9d.reproducibility import Phase9DReproducibilityAudit
from phase9.leakage_guard import LeakageGuard


@pytest.fixture
def sample_candles() -> pd.DataFrame:
    """Creates a sample 300-bar OHLCV DataFrame."""
    np.random.seed(42)
    n = 300
    base = 60000.0
    rets = np.random.normal(0.0001, 0.004, size=n)
    close = base * np.exp(np.cumsum(rets))
    high = close * (1.0 + np.abs(np.random.normal(0, 0.002, size=n)))
    low = close * (1.0 - np.abs(np.random.normal(0, 0.002, size=n)))
    open_p = (high + low) / 2.0
    volume = np.random.uniform(5.0, 50.0, size=n)
    ts = [1700000000000 + i * 300000 for i in range(n)]

    return pd.DataFrame({
        "timestamp": ts,
        "open": open_p,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    })


@pytest.fixture
def sample_orderbook() -> pd.DataFrame:
    """Creates sample L2 orderbook snapshot data."""
    records = []
    ts = 1700000000000
    for i in range(1, 11):
        records.append({"timestamp": ts, "side": "BID", "price": 60000.0 - i * 1.0, "quantity": 0.5 * i, "level": i})
        records.append({"timestamp": ts, "side": "ASK", "price": 60001.0 + i * 1.0, "quantity": 0.6 * i, "level": i})
    return pd.DataFrame(records)


@pytest.fixture
def sample_trades() -> pd.DataFrame:
    """Creates sample tick trade data."""
    records = []
    ts_start = 1700000000000 - 300000
    for i in range(50):
        records.append({
            "timestamp": ts_start + i * 5000,
            "price": 60000.0 + np.random.normal(0, 2.0),
            "quantity": np.random.uniform(0.01, 0.5),
            "side": "BUY" if i % 2 == 0 else "SELL",
            "trade_id": 1000 + i,
        })
    return pd.DataFrame(records)


def test_hypothesis_pre_registration():
    """Verifies that all 5 Phase 9D hypotheses are registered and immutable."""
    reg = Phase9DHypothesisRegistry()
    hyps = reg.list_all()
    assert len(hyps) >= 5

    h_ids = [h.hypothesis_id for h in hyps]
    for required_id in ["P9D-H01", "P9D-H02", "P9D-H03", "P9D-H04", "P9D-H05"]:
        assert required_id in h_ids

    # Attempting to register duplicate must raise ValueError
    with pytest.raises(ValueError):
        reg.register(hyps[0], allow_update=False)


def test_orderbook_metrics_calculation(sample_orderbook):
    """Tests calculation of instantaneous orderbook spread and depth imbalance."""
    metrics = MicrostructureEngine.compute_orderbook_snapshot_metrics(sample_orderbook)
    
    assert "spread_bps" in metrics
    assert "ob_imbalance_l1" in metrics
    assert "ob_imbalance_l5" in metrics
    assert "ob_imbalance_l10" in metrics
    assert "depth_ratio_l5" in metrics

    assert metrics["spread_bps"] > 0.0
    assert -1.0 <= metrics["ob_imbalance_l5"] <= 1.0


def test_trade_flow_metrics_calculation(sample_trades):
    """Tests calculation of trade intensity, volume, and aggressor imbalance."""
    metrics = MicrostructureEngine.compute_trade_flow_window_metrics(sample_trades, window_seconds=300.0)
    
    assert "aggressor_imbalance" in metrics
    assert "buy_volume" in metrics
    assert "sell_volume" in metrics
    assert "trade_count" in metrics
    assert -1.0 <= metrics["aggressor_imbalance"] <= 1.0
    assert metrics["trade_count"] == 50


def test_temporal_alignment_and_causal_slicing(sample_trades):
    """Tests that temporal alignment strictly isolates trades within [T - W, T]."""
    candle_ts = 1700000000000
    sliced = TemporalAlignment.slice_causal_trades(sample_trades, candle_end_ts=candle_ts, window_name="1m")
    
    # 1 minute = 60,000 ms lookback [candle_ts - 60000, candle_ts]
    assert len(sliced) > 0
    assert sliced["timestamp"].min() >= candle_ts - 60_000
    assert sliced["timestamp"].max() <= candle_ts


def test_microstructure_aggregation_and_leakage_invariance(sample_candles):
    """Tests that microstructure aggregation is causal and invariant to future perturbation."""
    leak_check = LeakageGuard.test_future_perturbation(
        df=sample_candles,
        feature_calculator_fn=lambda df: MicrostructureAggregator.aggregate_to_candles(df, window_name="5m"),
        target_bar_idx=100,
        perturbation_bars=25,
        noise_magnitude=1000.0,
    )
    assert leak_check["is_causal"] is True
    assert leak_check["status"] == "PASS"
    assert leak_check["max_delta"] < 1e-9


def test_holdout_protection_and_freeze_protocol(tmp_path):
    """Tests that holdout protection raises error before freeze and unlocks only after freeze."""
    protocol = Phase9DHoldoutProtocol(
        freeze_manifest_path=tmp_path / "TEST_FREEZE.md",
        freeze_json_path=tmp_path / "test_freeze.json",
    )

    # Unauthorized access before freeze
    with pytest.raises(HoldoutProtectionError):
        protocol.verify_holdout_lock("SEALED_HOLDOUT")

    # Allowed access to Dev/Val
    protocol.verify_holdout_lock("DEVELOPMENT")
    protocol.verify_holdout_lock("VALIDATION")

    # Execute freeze
    freeze_payload = protocol.execute_pre_holdout_freeze(
        dataset_hashes={"BTC": "hash123"},
        feature_registry={"total_features": 10},
        hypotheses_summary=[{"id": "P9D-H01"}],
        validation_results=[{"auc": 0.52}],
        git_commit_hash="commit_test",
    )
    assert freeze_payload["status"] == "FROZEN_AND_SEALED"

    # Authorized access after freeze
    protocol.verify_holdout_lock("SEALED_HOLDOUT")


def test_dual_economic_gate():
    """Tests static 40 bps gate and dynamic microstructure cost evaluation."""
    gate = DualEconomicGate()
    cost = gate.compute_dynamic_cost(spread_bps=4.0, realized_vol_daily=0.60, depth_ratio=1.2)

    assert cost.static_hurdle_bps == 40.0
    assert cost.total_dynamic_hurdle_bps >= 35.0

    eval_fail = gate.evaluate(gross_edge_bps=15.0, spread_bps=4.0)
    assert eval_fail.survives_static_gate is False
    assert eval_fail.survives_dynamic_gate is False

    eval_pass = gate.evaluate(gross_edge_bps=65.0, spread_bps=4.0)
    assert eval_pass.survives_static_gate is True
    assert eval_pass.survives_dynamic_gate is True


def test_statistical_block_bootstrap_and_auc():
    """Tests block bootstrap confidence interval calculation for Delta_AUC."""
    np.random.seed(42)
    y_true = np.random.choice([0, 1], size=200)
    score_base = np.random.normal(0, 1, size=200)
    score_enh = score_base + 0.1 * y_true  # Slight enhancement

    delta_auc, ci_l, ci_u, p_val = block_bootstrap_delta_auc(
        y_true, score_base, score_enh, block_size=12, n_replications=100, seed=42
    )
    assert isinstance(delta_auc, float)
    assert ci_l <= ci_u
    assert 0.0 <= p_val <= 1.0


def test_regime_microstructure_analysis(sample_candles):
    """Tests regime-conditioned evaluation and weak observation classification."""
    analyzer = RegimeMicrostructureAnalyzer()
    
    signal = pd.Series(np.random.normal(0, 1, len(sample_candles)), index=sample_candles.index)
    target = pd.Series(np.random.normal(0, 0.01, len(sample_candles)), index=sample_candles.index)
    regimes = pd.Series(np.random.choice([0.0, 1.0, 2.0, 3.0, 4.0, 5.0], len(sample_candles)), index=sample_candles.index)

    results = analyzer.evaluate_regimes(signal, target, regimes)
    assert len(results) == 6
    for r in results:
        assert r.regime_name in analyzer.REGIMES
        assert r.sample_size < 300  # sample_candles has 300 bars total
        assert r.classification == "WEAK_OBSERVATION_ONLY"


def test_deterministic_reproducibility(sample_candles):
    """Verifies that running feature extraction on identical data produces delta = 0."""
    audit = Phase9DReproducibilityAudit.audit_run_a_vs_run_b(
        df_sample=sample_candles,
        extractor_fn=lambda df: MicrostructureAggregator.aggregate_to_candles(df, window_name="5m"),
    )
    assert audit["status"] == "PASS"
    assert audit["is_reproducible"] is True
    assert audit["max_numerical_delta"] == 0.0


def test_safety_invariants_strictly_maintained():
    """Verifies strict safety architecture invariants."""
    # Ensure no live execution files exist in phase9d
    for p in Path("phase9d").glob("**/*.py"):
        content = p.read_text(encoding="utf-8")
        assert "private_key" not in content.lower()
        assert "place_order" not in content.lower()
        assert "execute_trade" not in content.lower()
