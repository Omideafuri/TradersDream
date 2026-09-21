"""Tests for Phase 7: Horizon Reassessment & Temporal Resolution Study.

Verifies:
1. Safety invariants strictly maintained (paper trading only, no live trading).
2. Causal temporal aggregation and valid OHLC bounds across 15m, 30m, 1h, 4h.
3. Causal prediction targets and forward excursions (MFE, MAE).
4. Primary vs Secondary methodology separation.
5. Signal-level evaluation metrics, Brier score, ECE, and rank correlations.
6. Economic cost model with frozen 30 bps friction and 40 bps hurdle.
7. Execution frequency and turnover attribution.
8. Temporal monotonicity test logic.
9. Formal statistical power audit (H0 vs H1 at +40 bps alternative).
10. Cross-regime generalization across horizons.
11. Walk-forward chronological 4-fold validation and exact boundaries.
12. Model-agnostic baselines across horizons.
13. Experiment registry and Benjamini-Hochberg FDR multiple-testing control.
14. End-to-end pipeline execution and 23-section report generation.
"""

import os
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from bot.config import BotConfig
from temporal.data_aggregator import TemporalDataAggregator, TIMEFRAME_BAR_RATIOS
from temporal.targets import calculate_forward_targets
from temporal.methodology import execute_primary_methodology, execute_secondary_methodology
from temporal.signal_eval import evaluate_signal_metrics, calculate_spearman_rank_correlation, calculate_ece
from temporal.cost_model import evaluate_horizon_economics
from temporal.frequency_effect import audit_frequency_effect
from temporal.monotonicity import evaluate_temporal_monotonicity
from temporal.power_audit import audit_statistical_power
from temporal.cross_regime import audit_regimes_across_horizon
from temporal.walk_forward import run_temporal_walk_forward
from temporal.baselines import evaluate_temporal_baselines
from temporal.registry import Phase7ExperimentRegistry
from temporal.report import generate_phase7_markdown_report, save_phase7_artifacts
from temporal.run import run_phase7_pipeline


@pytest.fixture
def sample_5m_candles() -> pd.DataFrame:
    """Generates synthetic 5m candles for deterministic unit testing."""
    n = 300
    base_ts = 1715000000000  # ms
    interval_ms = 5 * 60 * 1000
    timestamps = [base_ts + i * interval_ms for i in range(n)]

    rng = np.random.RandomState(42)
    prices = [60000.0]
    for _ in range(n - 1):
        ret = rng.normal(0.0001, 0.002)
        prices.append(prices[-1] * (1.0 + ret))

    rows = []
    for i, p in enumerate(prices):
        spread = p * 0.001
        high = p + rng.uniform(0, spread)
        low = p - rng.uniform(0, spread)
        open_p = p + rng.uniform(-spread * 0.3, spread * 0.3)
        close_p = p
        high = max(high, open_p, close_p)
        low = min(low, open_p, close_p)
        vol = rng.uniform(10.0, 50.0)

        rows.append({
            "timestamp": timestamps[i],
            "open": open_p,
            "high": high,
            "low": low,
            "close": close_p,
            "volume": vol,
        })

    df = pd.DataFrame(rows)
    return df


def test_safety_invariants_strictly_maintained():
    """Verify safety invariants cannot be bypassed in Phase 7."""
    config = BotConfig.from_env()
    assert config.paper_trading_only is True, "paper_trading_only must remain True!"
    assert config.leverage == 1.0, "Leverage must remain locked at 1.0x!"


def test_temporal_data_aggregator(sample_5m_candles):
    """Verify causal aggregation of 5m bars into 15m, 30m, 1h, and 4h."""
    for tf, ratio in TIMEFRAME_BAR_RATIOS.items():
        resampled, meta = TemporalDataAggregator.aggregate_candles(sample_5m_candles, target_timeframe=tf, symbol="BTCUSDT")
        expected_len = len(sample_5m_candles) // ratio
        assert len(resampled) == expected_len
        assert meta.candle_count == expected_len
        assert meta.is_valid_ohlc is True
        assert len(meta.sha256_hash) == 64
        # Verify OHLC correctness
        assert (resampled["high"] >= resampled["low"]).all()
        assert (resampled["high"] >= resampled["open"]).all()
        assert (resampled["high"] >= resampled["close"]).all()


def test_forward_targets_causality(sample_5m_candles):
    """Verify target calculations never use future data at time t."""
    df_targets = calculate_forward_targets(sample_5m_candles, shift_bars=3, horizon_name="15m")
    assert "target_bps_15m" in df_targets.columns
    assert "target_mfe_15m" in df_targets.columns
    assert "target_mae_15m" in df_targets.columns

    # Check forward return formula: (close[t+3] - close[t]) / close[t] * 10000
    c0 = sample_5m_candles["close"].iloc[0]
    c3 = sample_5m_candles["close"].iloc[3]
    expected_bps = (c3 - c0) / c0 * 10000.0
    assert abs(df_targets["target_bps_15m"].iloc[0] - expected_bps) < 1e-4

    # Trailing 3 rows must have NaN targets
    assert pd.isna(df_targets["target_bps_15m"].iloc[-1])
    assert pd.isna(df_targets["target_bps_15m"].iloc[-3])


def test_primary_vs_secondary_methodology(sample_5m_candles):
    """Verify primary and secondary methodologies execute without interference."""
    prim = execute_primary_methodology(sample_5m_candles, symbol="BTCUSDT", timeframes=["5m", "15m"])
    sec = execute_secondary_methodology(sample_5m_candles, symbol="BTCUSDT", horizons=["5m", "15m"])

    assert "5m" in prim and "15m" in prim
    assert "5m" in sec and "15m" in sec

    assert prim["5m"].methodology == "PRIMARY"
    assert prim["15m"].methodology == "PRIMARY"
    assert sec["15m"].methodology == "SECONDARY"

    # Primary 15m has 100 bars (300 / 3)
    assert len(prim["15m"].df_evaluated) == 100
    # Secondary 15m has 300 base bars
    assert len(sec["15m"].df_evaluated) == 300


def test_signal_evaluation_metrics(sample_5m_candles):
    """Verify signal-level accuracy, Brier score, and calibration metrics."""
    prim = execute_primary_methodology(sample_5m_candles, symbol="BTCUSDT", timeframes=["5m"])
    metrics = evaluate_signal_metrics(prim["5m"].df_evaluated, symbol="BTCUSDT", timeframe="5m", horizon="5m")

    assert metrics.sample_size > 0
    assert 0.0 <= metrics.directional_accuracy_pct <= 100.0
    assert 0.0 <= metrics.abstention_rate_pct <= 100.0
    assert 0.0 <= metrics.brier_score <= 1.0
    assert -1.0 <= metrics.spearman_conf_return <= 1.0
    assert -1.0 <= metrics.spearman_conf_accuracy <= 1.0


def test_economic_cost_model(sample_5m_candles):
    """Verify frozen cost model (30 bps friction, 40 bps hurdle)."""
    prim = execute_primary_methodology(sample_5m_candles, symbol="BTCUSDT", timeframes=["5m"])
    eco = evaluate_horizon_economics(prim["5m"].df_evaluated, symbol="BTCUSDT", timeframe="5m", horizon="5m")

    assert eco.round_trip_friction_bps == 30.0
    assert eco.safety_margin_bps == 10.0
    assert eco.classification in ["SUPPORTED", "PREDICTIVE_BUT_NOT_ECONOMIC", "NOT_SUPPORTED"]


def test_frequency_effect_audit(sample_5m_candles):
    """Verify trade frequency and turnover attribution."""
    prim = execute_primary_methodology(sample_5m_candles, symbol="BTCUSDT", timeframes=["5m"])
    fe = audit_frequency_effect(prim["5m"].df_evaluated, symbol="BTCUSDT", timeframe="5m", horizon="5m")

    assert fe.trade_frequency_pct >= 0.0
    assert fe.primary_driver in [
        "GENUINE_SIGNAL_IMPROVEMENT",
        "MARGINAL_SIGNAL_IMPROVEMENT_INSUFFICIENT_FOR_FEES",
        "FRICTION_REDUCTION_ONLY",
        "NO_IMPROVEMENT",
    ]


def test_temporal_monotonicity_test():
    """Verify monotonicity detection across dummy horizon metrics."""
    dummy_metrics = {
        "5m": {"mean_forward_return_bps": 2.0, "directional_accuracy_pct": 50.1},
        "15m": {"mean_forward_return_bps": 5.0, "directional_accuracy_pct": 50.4},
        "30m": {"mean_forward_return_bps": 8.0, "directional_accuracy_pct": 50.7},
        "1h": {"mean_forward_return_bps": 15.0, "directional_accuracy_pct": 51.2},
        "4h": {"mean_forward_return_bps": 30.0, "directional_accuracy_pct": 52.0},
    }
    mono = evaluate_temporal_monotonicity(dummy_metrics, symbol="BTCUSDT")
    assert mono.trend_classification in ["MONOTONIC_INCREASE", "NON_MONOTONIC", "INVARIANT_NOISE"]
    assert mono.spearman_rho_edge >= 0.80


def test_formal_power_audit():
    """Verify formal power calculation under H0 vs H1."""
    # Synthetic negative returns
    rng = np.random.RandomState(42)
    neg_returns = rng.normal(-5.0, 50.0, size=200)
    audit = audit_statistical_power(neg_returns, symbol="BTCUSDT", horizon="5m", assumed_alternative_bps=40.0)

    assert audit.null_hypothesis == "H0: mu <= 0 (Zero or Negative Alpha)"
    assert audit.alternative_hypothesis == "H1: mu = +40.0 bps (Economic Hurdle Alpha)"
    assert audit.statistical_power_at_alternative > 0.50
    assert audit.is_null_rejected is False
    assert "methodological_clarification" in audit.to_dict()


def test_cross_regime_audit(sample_5m_candles):
    """Verify regime conditioning across all 6 causal regimes."""
    prim = execute_primary_methodology(sample_5m_candles, symbol="BTCUSDT", timeframes=["5m"])
    reg_list = audit_regimes_across_horizon(prim["5m"].df_evaluated, symbol="BTCUSDT", horizon="5m")

    assert len(reg_list) == 6
    reg_names = [r.regime for r in reg_list]
    assert "TRENDING_UP" in reg_names
    assert "RANGE_BOUND" in reg_names


def test_walk_forward_validation_boundaries(sample_5m_candles):
    """Verify 4-fold walk-forward validation and exact boundaries."""
    prim = execute_primary_methodology(sample_5m_candles, symbol="BTCUSDT", timeframes=["5m"])
    wf_folds = run_temporal_walk_forward(prim["5m"].df_evaluated, symbol="BTCUSDT", horizon="5m", n_folds=4)

    assert len(wf_folds) == 4
    for fold in wf_folds:
        assert fold.train_start_idx < fold.train_end_idx
        assert fold.val_start_idx < fold.val_end_idx
        assert fold.test_start_idx < fold.test_end_idx
        assert fold.train_end_idx <= fold.val_start_idx
        assert fold.val_end_idx <= fold.test_start_idx


def test_temporal_baselines(sample_5m_candles):
    """Verify all 7 reference baselines run across horizons."""
    prim = execute_primary_methodology(sample_5m_candles, symbol="BTCUSDT", timeframes=["5m"])
    bl_metrics = evaluate_temporal_baselines(prim["5m"].df_evaluated, symbol="BTCUSDT", horizon="5m")

    assert len(bl_metrics) == 7
    bl_names = [b.baseline_name for b in bl_metrics]
    assert "Always HOLD" in bl_names
    assert "Random (Uniform 50/50)" in bl_names
    assert "Momentum (5-bar)" in bl_names
    assert "Mean Reversion (RSI 30/70)" in bl_names


def test_experiment_registry_and_fdr():
    """Verify experiment registry and Benjamini-Hochberg FDR adjustments."""
    registry = Phase7ExperimentRegistry()
    assert len(registry.configuration_hash) == 64

    # Register 3 dummy hypotheses
    registry.register_experiment(
        experiment_id="EXP-1",
        hypothesis="H7-test-1",
        asset="BTCUSDT",
        horizon="5m",
        execution_frequency="5m",
        dataset_hash="hash1",
        period="period1",
        primary_metric="net_return_bps",
        success_criterion="net_bps > 0",
        raw_p_value=0.04,
        observed_effect_bps=10.0,
        result="SUPPORTED",
    )
    registry.register_experiment(
        experiment_id="EXP-2",
        hypothesis="H7-test-2",
        asset="ETHUSDT",
        horizon="15m",
        execution_frequency="15m",
        dataset_hash="hash2",
        period="period2",
        primary_metric="net_return_bps",
        success_criterion="net_bps > 0",
        raw_p_value=0.08,
        observed_effect_bps=-5.0,
        result="NOT_SUPPORTED",
    )

    finalized = registry.finalize_multiple_testing_correction(alpha=0.05)
    assert len(finalized) == 2
    # Check that FDR adjustments were applied
    assert finalized[0].adjusted_p_value >= finalized[0].raw_p_value


def test_end_to_end_phase7_pipeline(tmp_path):
    """Verify full Phase 7 pipeline execution and artifact generation."""
    out_dir = str(tmp_path / "phase7_test_results")
    res = run_phase7_pipeline(
        symbols=["BTCUSDT"],
        horizons=["5m", "15m"],
        data_dir="data/historical",
        output_dir=out_dir,
    )

    assert res["master_classification"] in ["SUPPORTED", "NOT_SUPPORTED"]
    assert len(res["primary_signals"]) > 0
    assert len(res["primary_economics"]) > 0
    assert len(res["registry"]) > 0

    # Verify artifacts exist on disk
    p = Path(out_dir)
    json_files = list(p.glob("phase7_horizon_*.json"))
    csv_files = list(p.glob("phase7_horizon_*.csv"))
    md_files = list(p.glob("phase7_horizon_*.md"))

    assert len(json_files) == 1
    assert len(csv_files) == 1
    assert len(md_files) == 1

    # Verify report contains key sections
    with open(md_files[0], "r", encoding="utf-8") as f:
        md_text = f.read()
    assert "## 1. Executive Summary" in md_text
    assert "## 11. Statistical Analysis & Power Audit" in md_text
    assert "## 23. Final Classification" in md_text
