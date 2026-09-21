"""Comprehensive automated test suite for Phase 3: Statistical Edge Validation & Robustness.

Tests:
1. Causality invariants (no look-ahead in indicators, rolling stats, regimes)
2. Bootstrap reproducibility with fixed random seed
3. Random baseline empirical null generation & distribution bounds
4. Calibration metrics (Brier score, ECE, small sample N < 30 flagging)
5. Cost sensitivity monotonicity (Scenarios A through E)
6. Regime detection (strictly causal classification)
7. Holdout isolation (strict chronological non-overlapping partitions)
8. Dataset integrity checker (detecting inverted OHLC, non-positive price, duplicates, gaps)
9. Multiple testing corrections (Bonferroni and Benjamini-Hochberg FDR)
10. Reproducibility metadata and report artifact generation
"""

import math
from pathlib import Path
import tempfile
import numpy as np
import pandas as pd
import pytest

from backtest.dataset import DatasetManager, HistoricalDecision
from backtest.engine import BacktestEngine, BacktestConfig
from validation.data_quality import DatasetIntegrityChecker, DataQualityReport
from validation.dataset_expansion import MultiAssetDataManager
from validation.forward_returns import (
    evaluate_directional_forward_returns,
    compute_bootstrap_ci,
)
from validation.calibration import compute_calibration_analysis, CalibrationReport
from validation.statistical import (
    calculate_expectancy,
    calculate_risk_adjusted_ratios,
    calculate_t_test_one_sample,
    apply_multiple_testing_corrections,
    normal_cdf,
)
from validation.bootstrap import DeterministicBootstrapper
from validation.random_baseline import RandomBaselineEngine
from validation.ablation import run_ablation_study, generate_ablated_decisions
from validation.cost_sensitivity import run_cost_sensitivity_analysis
from validation.regime import classify_causal_regimes, evaluate_regime_performance
from validation.holdout import partition_three_way, evaluate_sealed_holdout
from validation.report import ValidationReportGenerator, compute_file_sha256


@pytest.fixture
def sample_candles():
    """Generates deterministic 300-candle sample for fast unit testing."""
    return DatasetManager.generate_synthetic_history(count=300, start_price=50000.0, seed=123)


@pytest.fixture
def sample_enriched(sample_candles):
    return DatasetManager.compute_causal_indicators(sample_candles)


@pytest.fixture
def sample_decisions(sample_enriched):
    return DatasetManager.generate_simulated_decisions(sample_enriched, seed=456)


# 1. Test Causality Invariants
def test_causality_invariants(sample_candles):
    """Verifies that appending future rows does NOT alter indicators or regimes of prior rows."""
    df_short = sample_candles.iloc[:150].copy()
    df_long = sample_candles.iloc[:200].copy()

    enriched_short = DatasetManager.compute_causal_indicators(df_short)
    enriched_long = DatasetManager.compute_causal_indicators(df_long)

    # Indicator values for row 140 must be identical in both sets
    for col in ["ema20", "ema50", "rsi14", "atr14"]:
        val_short = enriched_short.loc[140, col]
        val_long = enriched_long.loc[140, col]
        assert pytest.approx(val_short, rel=1e-6) == val_long, f"Look-ahead detected in {col}"

    # Regimes for row 140 must also be identical
    reg_short = classify_causal_regimes(enriched_short)
    reg_long = classify_causal_regimes(enriched_long)
    assert reg_short.loc[140, "trend_regime"] == reg_long.loc[140, "trend_regime"]
    assert reg_short.loc[140, "vol_regime"] == reg_long.loc[140, "vol_regime"]


# 2. Test Bootstrap Reproducibility
def test_bootstrap_reproducibility():
    """Verifies that bootstrap confidence intervals are strictly deterministic for a given seed."""
    data = np.array([0.01, -0.02, 0.03, 0.005, -0.015, 0.04, -0.005, 0.02])
    low1, high1 = compute_bootstrap_ci(data, n_resamples=200, seed=42)
    low2, high2 = compute_bootstrap_ci(data, n_resamples=200, seed=42)
    assert low1 == low2
    assert high1 == high2
    assert low1 < high1

    bootstrapper = DeterministicBootstrapper(n_resamples=200, seed=42)
    res1 = bootstrapper.compute_ci(data)
    res2 = bootstrapper.compute_ci(data)
    assert res1.ci_lower == res2.ci_lower
    assert res1.ci_upper == res2.ci_upper


# 3. Test Random Baseline Empirical Null Generation
def test_random_baseline_null_distribution(sample_candles, sample_decisions):
    """Verifies that RandomBaselineEngine generates valid empirical null distributions."""
    cfg = BacktestConfig(initial_balance=10000.0, fee_rate=0.001, slippage_rate=0.0005)
    engine = BacktestEngine(cfg)
    actual_res = engine.run(sample_candles, sample_decisions)

    baseline_engine = RandomBaselineEngine(cfg, n_simulations=10, base_seed=999)
    null_rand = baseline_engine.evaluate_null_distribution(
        sample_candles, sample_decisions, actual_res, baseline_type="random_direction"
    )

    assert null_rand.n_iterations == 10
    assert 0.0 <= null_rand.empirical_p_value_return <= 1.0
    assert 0.0 <= null_rand.empirical_p_value_win_rate <= 1.0
    assert null_rand.min_return_pct <= null_rand.mean_return_pct <= null_rand.max_return_pct


# 4. Test Calibration Metrics & Small Sample Flagging
def test_calibration_metrics(sample_candles, sample_decisions):
    """Verifies Brier score, ECE, and sample size < 30 flagging."""
    from backtest.forward_returns import calculate_forward_returns
    df_fwd = calculate_forward_returns(sample_candles, sample_decisions)

    report = compute_calibration_analysis(df_fwd, horizon="15m", min_sample_reliable=30)
    assert 0.0 <= report.brier_score <= 1.0
    assert 0.0 <= report.expected_calibration_error_pct <= 100.0

    # Ensure buckets with count < 30 are flagged as not statistically reliable
    for b in report.buckets:
        if b.count < 30:
            assert b.is_statistically_reliable is False
        else:
            assert b.is_statistically_reliable is True


# 5. Test Cost Sensitivity Monotonicity
def test_cost_sensitivity_monotonicity(sample_candles, sample_decisions):
    """Verifies that increasing execution friction (fees/slippage) monotonically degrades net returns."""
    cfg = BacktestConfig(initial_balance=10000.0)
    results = run_cost_sensitivity_analysis(sample_candles, sample_decisions, cfg)
    assert len(results) == 5

    # Check fee/slippage progression
    scenario_map = {r.scenario_id: r for r in results}
    scen_a = scenario_map["A"]  # 0 fee / 0 slippage
    scen_c = scenario_map["C"]  # 0.10% fee / 0.05% slippage
    scen_e = scenario_map["E"]  # 0.20% fee / 0.15% slippage

    assert scen_a.total_fees_paid == 0.0
    assert scen_a.total_slippage_cost == 0.0
    assert scen_a.total_return_pct >= scen_c.total_return_pct
    assert scen_c.total_return_pct >= scen_e.total_return_pct


# 6. Test Regime Detection
def test_regime_classification(sample_enriched):
    """Verifies causal regime assignment covering trend and volatility categories."""
    classified = classify_causal_regimes(sample_enriched)
    assert "trend_regime" in classified.columns
    assert "vol_regime" in classified.columns

    trend_types = set(classified["trend_regime"].unique())
    vol_types = set(classified["vol_regime"].unique())

    # Should contain standard regime types
    assert trend_types.issubset({"Trending Up", "Trending Down", "Sideways"})
    assert vol_types.issubset({"High Volatility", "Low Volatility"})


# 7. Test Holdout Partitioning & Out-of-Sample Isolation
def test_holdout_partitioning(sample_candles, sample_decisions):
    """Verifies strict three-way non-overlapping chronological partitioning."""
    (dev_c, dev_d), (val_c, val_d), (hld_c, hld_d), meta = partition_three_way(
        sample_candles, sample_decisions, dev_ratio=0.60, val_ratio=0.20
    )

    # Invariant: Timestamps must not overlap
    assert dev_c["timestamp"].max() < val_c["timestamp"].min()
    assert val_c["timestamp"].max() < hld_c["timestamp"].min()

    # Sum of counts must match original
    assert len(dev_c) + len(val_c) + len(hld_c) == len(sample_candles)
    assert len(dev_d) + len(val_d) + len(hld_d) == len(sample_decisions)

    cfg = BacktestConfig(initial_balance=10000.0)
    evaluation = evaluate_sealed_holdout(
        (dev_c, dev_d), (val_c, val_d), (hld_c, hld_d), cfg
    )
    assert evaluation.is_holdout_sealed is True
    assert "total_return_pct" in evaluation.holdout_metrics


# 8. Test Dataset Integrity Checker
def test_dataset_integrity_checker(sample_candles):
    """Verifies detection of corrupted OHLC, duplicates, and physical violations."""
    # Clean dataset passes
    report = DatasetIntegrityChecker(sample_candles).run_all_checks()
    assert report.is_valid is True
    assert report.invalid_ohlc_rows == 0
    assert report.duplicate_timestamps == 0

    # Corrupted: High < Low
    corrupted = sample_candles.copy()
    corrupted.loc[10, "high"] = corrupted.loc[10, "low"] - 10.0
    bad_report = DatasetIntegrityChecker(corrupted).run_all_checks()
    assert bad_report.is_valid is False
    assert bad_report.invalid_ohlc_rows > 0

    # Corrupted: Duplicate timestamp
    dup_df = sample_candles.copy()
    dup_df.loc[5, "timestamp"] = dup_df.loc[4, "timestamp"]
    dup_report = DatasetIntegrityChecker(dup_df).run_all_checks()
    assert dup_report.is_valid is False
    assert dup_report.duplicate_timestamps > 0


# 9. Test Multiple Testing Corrections
def test_multiple_testing_corrections():
    """Verifies Bonferroni threshold and Benjamini-Hochberg FDR filtering."""
    p_values = [0.001, 0.01, 0.04, 0.12, 0.50]
    res = apply_multiple_testing_corrections(p_values, alpha=0.05)

    assert res["hypotheses_tested_count"] == 5
    assert pytest.approx(res["bonferroni_threshold"]) == 0.01  # 0.05 / 5

    # Bonferroni significance: p <= 0.01
    assert res["bonferroni_significant"] == [True, True, False, False, False]

    # B-H FDR significance
    assert any(res["fdr_significant"])


# 10. Test Reproducibility Metadata & Artifact Generation
def test_artifact_generation(sample_candles, sample_decisions):
    """Verifies that ValidationReportGenerator produces valid JSON, CSV, and Markdown files."""
    cfg = BacktestConfig(initial_balance=10000.0)
    engine = BacktestEngine(cfg)
    actual_res = engine.run(sample_candles, sample_decisions)

    from backtest.forward_returns import calculate_forward_returns
    df_fwd = calculate_forward_returns(sample_candles, sample_decisions)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        gen = ValidationReportGenerator(
            symbol="BTCUSDT",
            timeframe="5m",
            results_data={"primary_metrics": actual_res.metrics.to_dict()},
            trades=actual_res.trades,
            forward_returns_df=df_fwd,
            output_dir=tmp_path,
        )
        artifacts = gen.generate_all_artifacts()

        assert artifacts["json"].exists()
        assert artifacts["csv"].exists()
        assert artifacts["markdown"].exists()
        assert artifacts["json"].stat().st_size > 0
        assert artifacts["markdown"].stat().st_size > 0
