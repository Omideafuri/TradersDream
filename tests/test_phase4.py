"""Phase 4 Automated Test Suite: Signal Diagnosis & Strategy Reconstruction.

Tests:
1. Raw signal extraction & decomposition
2. Directional horizon matrix calculation
3. Signal decay curve trajectories
4. MFE / MAE excursion boundary invariants
5. Exit ablation mechanics (SL, TP, Time-only)
6. Entry timing delay evaluation
7. Regime x Signal cross-tabulation
8. Confidence rank correlation & calibration isolation (Dev-only fitting)
9. HOLD subsequent volatility & drift analysis
10. Control baselines & random reproducibility
11. Cross-asset evaluation
12. Temporal stability quarters
13. Candidate architectures holdout sealing
14. Phase 4 report & artifact generation
"""

from pathlib import Path
import tempfile
import numpy as np
import pandas as pd
import pytest

from backtest.dataset import DatasetManager, HistoricalDecision
from backtest.engine import BacktestConfig
from validation.dataset_expansion import MultiAssetDataManager
from validation.holdout import partition_three_way

from diagnosis.decomposition import (
    extract_raw_signal_records,
    compute_horizon_matrix,
    RawDecisionRecord,
)
from diagnosis.decay import compute_decay_curve, SignalDecayCurve
from diagnosis.excursion import (
    compute_excursions,
    summarize_excursions,
    ExcursionRecord,
)
from diagnosis.exit_ablation import run_exit_ablation
from diagnosis.timing import evaluate_entry_timing_delays
from diagnosis.regime_matrix import build_regime_signal_matrix
from diagnosis.confidence_analysis import (
    compute_spearman_rank_correlation,
    evaluate_confidence_information_content,
    reconstruct_calibration,
)
from diagnosis.hold_analysis import analyze_hold_behavior
from diagnosis.control_baselines import run_control_baselines
from diagnosis.cross_asset import run_cross_asset_evaluation
from diagnosis.stability import evaluate_temporal_stability
from diagnosis.reconstruction import evaluate_candidate_architectures
from diagnosis.report import Phase4ReportGenerator


@pytest.fixture
def sample_candles():
    return DatasetManager.generate_synthetic_history(count=300, start_price=60000.0, seed=42)


@pytest.fixture
def sample_enriched(sample_candles):
    return DatasetManager.compute_causal_indicators(sample_candles)


@pytest.fixture
def sample_decisions(sample_enriched):
    return DatasetManager.generate_simulated_decisions(sample_enriched, seed=123)


# 1. Raw Signal Extraction
def test_raw_signal_extraction(sample_candles, sample_decisions):
    records = extract_raw_signal_records(sample_candles, sample_decisions)
    assert len(records) == len(sample_decisions)

    # Check directional mapping
    for r in records:
        if r.action == "LONG" and r.raw_returns.get("15m") is not None:
            assert r.directional_returns["15m"] == r.raw_returns["15m"]
            assert r.is_correct["15m"] == (r.raw_returns["15m"] > 0)
        elif r.action == "SHORT" and r.raw_returns.get("15m") is not None:
            assert pytest.approx(r.directional_returns["15m"]) == -r.raw_returns["15m"]
            assert r.is_correct["15m"] == (r.raw_returns["15m"] < 0)


# 2. Horizon Matrix
def test_horizon_matrix(sample_candles, sample_decisions):
    records = extract_raw_signal_records(sample_candles, sample_decisions)
    matrix = compute_horizon_matrix(records, n_bootstrap=100, seed=42)

    assert "5m" in matrix and "15m" in matrix and "1h" in matrix
    assert "LONG" in matrix["15m"] and "SHORT" in matrix["15m"]
    stat_long = matrix["15m"]["LONG"]
    assert stat_long.sample_count > 0
    assert stat_long.ci_lower_pct <= stat_long.ci_upper_pct


# 3. Signal Decay Curves
def test_signal_decay_curve(sample_candles, sample_decisions):
    records = extract_raw_signal_records(sample_candles, sample_decisions)
    curve = compute_decay_curve(sample_candles, records, action_filter="POOLED")

    assert len(curve.points) == 6
    assert curve.curve_behavior in ("IMPROVING", "STABLE", "DECAYING", "REVERSING", "INCONCLUSIVE")
    for pt in curve.points:
        assert pt.sample_count >= 0


# 4. MFE / MAE Excursion Invariants
def test_mfe_mae_excursions(sample_candles, sample_decisions):
    excursions = compute_excursions(sample_candles, sample_decisions, window_bars=24, sl_pct=1.5, tp_pct=3.0)
    assert len(excursions) > 0

    for e in excursions:
        assert e.mfe_pct >= 0.0, "MFE must be non-negative"
        assert e.mae_pct >= 0.0, "MAE must be non-negative"
        assert 1 <= e.bars_to_mfe <= 24
        assert 1 <= e.bars_to_mae <= 24

    summary = summarize_excursions(excursions)
    assert summary.sample_count == len(excursions)
    assert 0.0 <= summary.premature_stopout_rate_pct <= 100.0


# 5. Exit Ablation
def test_exit_ablation(sample_candles, sample_decisions):
    cfg = BacktestConfig(initial_balance=10000.0)
    results = run_exit_ablation(sample_candles, sample_decisions, cfg)
    assert len(results) == 6

    # Verify that different exit rules produce different holding bars and metrics
    time_exit_6 = next(r for r in results if r.config_name == "time_only_6bars")
    assert time_exit_6.avg_holding_bars <= 6.0


# 6. Entry Timing Delays
def test_entry_timing_delays(sample_candles, sample_decisions):
    results = evaluate_entry_timing_delays(sample_candles, sample_decisions)
    assert len(results) == 5  # 0, 1, 2, 3, 6 bars
    for r in results:
        assert r.evaluated_trades > 0
        assert r.mean_mfe_pct >= 0.0


# 7. Regime x Signal Matrix
def test_regime_signal_matrix(sample_enriched, sample_decisions):
    matrices = build_regime_signal_matrix(sample_enriched, sample_decisions)
    assert "regime_x_direction" in matrices
    assert "regime_x_confidence" in matrices
    assert len(matrices["regime_x_direction"]) == 15  # 5 regimes x 3 actions


# 8. Confidence Rank Correlation & Calibration Isolation
def test_confidence_correlation_and_calibration(sample_candles, sample_decisions):
    # Pure spearman test
    x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    y = np.array([2.0, 4.0, 6.0, 8.0, 10.0])
    rho, p = compute_spearman_rank_correlation(x, y)
    assert pytest.approx(rho) == 1.0
    assert p < 0.05

    records = extract_raw_signal_records(sample_candles, sample_decisions)
    excursions = compute_excursions(sample_candles, sample_decisions)
    corr_results = evaluate_confidence_information_content(records, excursions)
    assert len(corr_results) >= 2

    # Calibration isolation test
    dev_recs = records[:180]
    val_recs = records[180:240]
    hld_recs = records[240:]

    calib_res = reconstruct_calibration(dev_recs, val_recs, hld_recs)
    assert calib_res.train_partition == "DEVELOPMENT_60%"
    assert calib_res.is_holdout_sealed is True


# 9. HOLD Subsequent Volatility
def test_hold_behavior_analysis(sample_candles, sample_decisions):
    records = extract_raw_signal_records(sample_candles, sample_decisions)
    hold_metrics = analyze_hold_behavior(sample_candles, records)

    assert "hold_metrics" in hold_metrics
    assert "active_metrics" in hold_metrics
    assert hold_metrics["hold_metrics"].sample_count > 0
    assert hold_metrics["hold_metrics"].mean_forward_volatility_pct >= 0.0


# 10. Control Baselines
def test_control_baselines(sample_candles, sample_enriched, sample_decisions):
    cfg = BacktestConfig(initial_balance=10000.0)
    baselines = run_control_baselines(sample_candles, sample_enriched, sample_decisions, cfg)
    assert len(baselines) == 6

    always_hold = next(b for b in baselines if b.model_name == "always_hold")
    assert always_hold.total_trades == 0
    assert always_hold.total_return_pct == 0.0


# 11. Cross-Asset Evaluation
def test_cross_asset_evaluation(sample_candles):
    with tempfile.TemporaryDirectory() as tmp_dir:
        data_mgr = MultiAssetDataManager(Path(tmp_dir))
        cfg = BacktestConfig(initial_balance=10000.0)
        results = run_cross_asset_evaluation(data_mgr, cfg, assets=["BTCUSDT", "ETHUSDT"])
        assert len(results) == 2
        for r in results:
            assert r.candle_count == 1500


# 12. Temporal Stability Quarters
def test_temporal_stability(sample_candles, sample_decisions):
    cfg = BacktestConfig(initial_balance=10000.0)
    segments, stability_class = evaluate_temporal_stability(sample_candles, sample_decisions, cfg, n_segments=4)
    assert len(segments) == 4
    assert stability_class in ("PERSISTENT_POSITIVE", "PERSISTENT_NEGATIVE", "DECAYING", "INTERMITTENT_REGIME_DEPENDENT")


# 13. Candidate Architectures Holdout Sealing
def test_candidate_architectures_holdout_sealing(sample_candles, sample_decisions):
    dev_set, val_set, holdout_set, _ = partition_three_way(sample_candles, sample_decisions, 0.60, 0.20)
    cfg = BacktestConfig(initial_balance=10000.0)

    arch_results = evaluate_candidate_architectures(dev_set, val_set, holdout_set, cfg)
    assert len(arch_results) == 5

    for ar in arch_results:
        assert ar.generalization_status in ("SUPPORTED", "NOT_SUPPORTED", "INCONCLUSIVE", "INSUFFICIENT_SAMPLE")


# 14. Phase 4 Report & Artifact Generation
def test_phase4_report_generation(sample_candles, sample_decisions):
    records = extract_raw_signal_records(sample_candles, sample_decisions)
    excursions = compute_excursions(sample_candles, sample_decisions)

    fake_data = {
        "reproducibility": {"execution_timestamp": "2026-09-21T00:00:00Z"},
        "phase3_baseline": {"strategy_return_pct": -1.85},
        "dataset_coverage": {"total_candles": len(sample_candles)},
        "data_integrity": {"is_valid": True, "violation_count": 0},
        "raw_signal_summary": {"total_decisions": len(records)},
        "horizon_matrix": {},
        "decay_curve": {"curve_behavior": "DECAYING", "peak_horizon": "15m", "peak_return_pct": 0.05, "points": []},
        "excursion_summary": {"mean_mfe_pct": 0.5, "mean_mae_pct": 0.4, "mfe_to_mae_ratio": 1.25},
        "exit_ablation": [],
        "timing_analysis": [],
        "regime_matrix": {"regime_x_direction": [], "regime_x_confidence": []},
        "confidence_correlation": [],
        "calibration_reconstruction": {},
        "hold_analysis": {"hold_metrics": {}, "active_metrics": {}},
        "control_baselines": [],
        "cross_asset": [],
        "feature_ablation": [],
        "stability": {"classification": "INTERMITTENT", "segments": []},
        "candidate_architectures": [],
        "final_evidence_assessment": {"overall_status": "NOT_SUPPORTED", "synthesis": "Test synthesis."},
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        gen = Phase4ReportGenerator(
            symbol="BTCUSDT",
            timeframe="5m",
            results_data=fake_data,
            raw_records=records,
            excursions=excursions,
            output_dir=tmp_path,
        )
        artifacts = gen.generate_all_artifacts()

        assert artifacts["json"].exists()
        assert artifacts["csv"].exists()
        assert artifacts["markdown"].exists()
        assert artifacts["markdown"].stat().st_size > 0
