"""Automated Test Suite for Phase 5 Signal Reconstruction & Model Improvement.

Tests:
1. Jev decision architecture audit & trace.
2. Input quality audit (moments, skew, collinearity).
3. Causal market state & structure computation (EMAs, MACD, ATR, swings, BOS).
4. Causal regime classification & distributions.
5. Explicit prediction horizons (5m, 15m, 30m, 1h, 4h).
6. Return magnitude estimation & friction comparison.
7. Uncertainty decomposition & calibration.
8. Explicit abstention architecture (NO_EDGE vs HOLD).
9. Directional asymmetry & class balance.
10. Controlled prompt experiments (Variants A-E).
11. Chronological walk-forward validation (4-fold isolation).
12. Feature ablation & information gain.
13. Model-agnostic baselines.
14. Signal friction gate & hurdle barrier.
15. Experiment registry & status validation.
16. Full pipeline artifact generation (JSON, CSV, 18-section MD).
"""

import json
from pathlib import Path
import tempfile
import pytest
import numpy as np
import pandas as pd

from reconstruction.audit import audit_jev_decision_architecture
from reconstruction.input_quality import audit_feature_quality
from reconstruction.market_state import (
    compute_enriched_market_state_df,
    extract_enriched_market_state,
)
from reconstruction.regimes import assign_causal_regimes, audit_regime_distributions
from reconstruction.horizons import evaluate_prediction_horizons
from reconstruction.magnitude import classify_return_magnitude, audit_return_magnitudes
from reconstruction.uncertainty import (
    compute_indicator_contradiction_uncertainty,
    audit_uncertainty_calibration,
)
from reconstruction.abstention import (
    evaluate_decision_with_abstention,
    audit_abstention_impact,
)
from reconstruction.asymmetry import audit_directional_asymmetry
from reconstruction.prompt_experiments import (
    simulate_prompt_decision,
    run_prompt_experiments,
)
from reconstruction.walk_forward import run_walk_forward_evaluation
from reconstruction.information_gain import audit_feature_ablation_information_gain
from reconstruction.baselines import evaluate_baselines
from reconstruction.gate import SignalFrictionGate
from reconstruction.registry import ExperimentRegistry
from reconstruction.report import generate_phase5_markdown_report, save_phase5_artifacts
from reconstruction.run import run_pipeline


@pytest.fixture
def sample_ohlcv_df():
    """Generates synthetic OHLCV data with realistic trends and oscillations."""
    n = 250
    timestamps = [1704067200000 + i * 300000 for i in range(n)]
    np.random.seed(42)
    # Generate random walk with drift
    returns = np.random.normal(0.0001, 0.002, size=n)
    price = 50000.0 * np.exp(np.cumsum(returns))
    high = price * (1.0 + np.abs(np.random.normal(0, 0.001, size=n)))
    low = price * (1.0 - np.abs(np.random.normal(0, 0.001, size=n)))
    open_p = price * (1.0 + np.random.normal(0, 0.0005, size=n))
    volume = np.random.uniform(50.0, 200.0, size=n)

    return pd.DataFrame({
        "timestamp": timestamps,
        "open": open_p,
        "high": high,
        "low": low,
        "close": price,
        "volume": volume,
    })


def test_audit_jev_decision_architecture():
    report = audit_jev_decision_architecture()
    assert report.endpoint == "https://api.typesafe.ai/v1/systemone"
    assert report.model == "jev-latest"
    assert len(report.input_features) >= 8
    assert len(report.structural_deficiencies) >= 5
    assert "timestamp" in report.sanitized_decision_trace
    d = report.to_dict()
    assert isinstance(d, dict)
    assert "output_schema" in d


def test_input_quality_audit(sample_ohlcv_df):
    enriched = compute_enriched_market_state_df(sample_ohlcv_df)
    profiles = audit_feature_quality(enriched)
    assert len(profiles) > 0
    names = [p.feature_name for p in profiles]
    assert "close" in names
    assert "rsi14" in names
    assert "atr14" in names
    assert "volume_ratio" in names

    # Check that price is flagged as poorly scaled or collinear
    close_prof = next(p for p in profiles if p.feature_name == "close")
    assert close_prof.is_poorly_scaled is True


def test_causal_market_state_computation(sample_ohlcv_df):
    enriched = compute_enriched_market_state_df(sample_ohlcv_df)
    assert "dist_ema20_pct" in enriched.columns
    assert "dist_ema50_pct" in enriched.columns
    assert "rsi14" in enriched.columns
    assert "rsi_slope_3" in enriched.columns
    assert "macd_hist_norm" in enriched.columns
    assert "atr_norm_pct" in enriched.columns
    assert "bb_width_pct" in enriched.columns
    assert "bb_pct_b" in enriched.columns
    assert "volume_ratio" in enriched.columns
    assert "swing_high" in enriched.columns
    assert "swing_low" in enriched.columns
    assert "break_of_structure" in enriched.columns
    assert "structure_type" in enriched.columns
    assert "compression_state" in enriched.columns

    # Test strongly-typed extraction
    state = extract_enriched_market_state(enriched, idx=50)
    assert state.close > 0
    assert state.structure.structure_type in ["HH_HL", "LH_LL", "MIXED"]
    assert state.structure.break_of_structure in ["BULLISH_BOS", "BEARISH_BOS", "NONE"]


def test_causal_regime_classification(sample_ohlcv_df):
    enriched = compute_enriched_market_state_df(sample_ohlcv_df)
    regimed = assign_causal_regimes(enriched)
    assert "market_regime" in regimed.columns
    valid_regimes = {
        "TRENDING_UP",
        "TRENDING_DOWN",
        "RANGE_BOUND",
        "HIGH_VOLATILITY",
        "LOW_VOLATILITY",
        "TRANSITION",
    }
    assert set(regimed["market_regime"].unique()).issubset(valid_regimes)

    profiles = audit_regime_distributions(regimed)
    assert len(profiles) == len(valid_regimes)
    total_freq = sum(p.frequency_pct for p in profiles)
    assert pytest.approx(total_freq, 0.1) == 100.0


def test_prediction_horizons(sample_ohlcv_df):
    evals = evaluate_prediction_horizons(sample_ohlcv_df)
    assert len(evals) >= 4  # 5m, 15m, 30m, 1h
    h_names = [e.horizon_name for e in evals]
    assert "5m" in h_names
    assert "15m" in h_names
    assert "1h" in h_names


def test_return_magnitude(sample_ohlcv_df):
    assert classify_return_magnitude(0.75) == "STRONG_POSITIVE"
    assert classify_return_magnitude(0.25) == "MODERATE_POSITIVE"
    assert classify_return_magnitude(0.02) == "NEUTRAL"
    assert classify_return_magnitude(-0.25) == "MODERATE_NEGATIVE"
    assert classify_return_magnitude(-0.75) == "STRONG_NEGATIVE"

    mags = audit_return_magnitudes(sample_ohlcv_df, horizon_bars=3, friction_bps=30.0)
    assert len(mags) == 5
    tot_freq = sum(m.frequency_pct for m in mags)
    assert pytest.approx(tot_freq, 0.1) == 100.0


def test_uncertainty_decomposition_and_calibration(sample_ohlcv_df):
    enriched = compute_enriched_market_state_df(sample_ohlcv_df)
    row = enriched.iloc[30]
    score = compute_indicator_contradiction_uncertainty(row)
    assert 0.0 <= score <= 1.0

    bins = audit_uncertainty_calibration(sample_ohlcv_df, horizon_bars=3)
    assert len(bins) == 3
    names = [b.bin_name for b in bins]
    assert "LOW_UNCERTAINTY" in names
    assert "HIGH_UNCERTAINTY" in names


def test_abstention_architecture(sample_ohlcv_df):
    profile = audit_abstention_impact(sample_ohlcv_df, horizon_bars=3, uncertainty_threshold=0.50)
    assert profile.total_bars == len(sample_ohlcv_df)
    assert profile.active_trade_rate_pct + profile.abstention_rate_pct == pytest.approx(100.0, 0.1)
    assert profile.long_count + profile.short_count + profile.hold_count + profile.no_edge_count == len(sample_ohlcv_df)


def test_directional_asymmetry(sample_ohlcv_df):
    report = audit_directional_asymmetry(sample_ohlcv_df, horizon_bars=3)
    assert report.total_bars == len(sample_ohlcv_df)
    assert report.market_trend_direction in ["BULLISH_DRIFT", "BEARISH_DRIFT", "NEUTRAL"]
    assert report.long_short_ratio > 0


def test_prompt_experiments(sample_ohlcv_df):
    results = run_prompt_experiments(sample_ohlcv_df, horizon_bars=3)
    assert len(results) == 5
    vids = [r.variant_id for r in results]
    assert vids == ["Variant_A", "Variant_B", "Variant_C", "Variant_D", "Variant_E"]
    for r in results:
        assert r.status in ["SUPPORTED", "NOT_SUPPORTED", "INSUFFICIENT_SAMPLE"]


def test_walk_forward_validation(sample_ohlcv_df):
    wf_results = run_walk_forward_evaluation(sample_ohlcv_df, n_folds=4, horizon_bars=3, friction_bps=30.0)
    assert len(wf_results) == 4
    for i, wf in enumerate(wf_results, start=1):
        assert wf.fold_index == i
        assert wf.train_bars > 0
        assert wf.test_bars > 0
        assert wf.status in ["SUPPORTED", "NOT_SUPPORTED", "INSUFFICIENT_SAMPLE"]


def test_feature_ablation_information_gain(sample_ohlcv_df):
    ablation = audit_feature_ablation_information_gain(sample_ohlcv_df, horizon_bars=3)
    assert len(ablation) == 5
    groups = [a.group_name for a in ablation]
    assert "Base_Trend_Only" in groups
    assert "Full_Unified_Model" in groups
    for a in ablation:
        assert a.brier_score >= 0.0
        assert a.out_of_sample_accuracy_pct >= 0.0


def test_model_agnostic_baselines(sample_ohlcv_df):
    baselines = evaluate_baselines(sample_ohlcv_df, horizon_bars=3, friction_bps=30.0)
    assert len(baselines) == 6
    names = [b.baseline_name for b in baselines]
    assert "Always_HOLD" in names
    assert "Random_Direction" in names
    assert "Simple_Momentum_3Bar" in names
    assert "Mean_Reversion_RSI" in names
    assert "EMA_Crossover_20_50" in names
    assert "Logistic_Regression_Linear" in names


def test_signal_friction_gate():
    gate = SignalFrictionGate(
        round_trip_fee_bps=20.0,
        round_trip_slippage_bps=10.0,
        safety_margin_bps=10.0,
        max_uncertainty_threshold=0.50,
    )
    assert gate.hurdle_bps == 40.0

    # 1. Passive action
    v1 = gate.evaluate("HOLD", prob_win=0.6, expected_move_bps=50.0, uncertainty_score=0.2)
    assert not v1.passed
    assert v1.filtered_action == "HOLD"

    # 2. Excessive uncertainty
    v2 = gate.evaluate("LONG", prob_win=0.7, expected_move_bps=60.0, uncertainty_score=0.65)
    assert not v2.passed
    assert v2.filtered_action == "NO_EDGE"

    # 3. Insufficient edge
    v3 = gate.evaluate("LONG", prob_win=0.52, expected_move_bps=20.0, uncertainty_score=0.2)
    assert not v3.passed
    assert v3.filtered_action == "NO_EDGE"

    # 4. Valid signal exceeding hurdle
    v4 = gate.evaluate("LONG", prob_win=0.65, expected_move_bps=150.0, uncertainty_score=0.25)
    assert v4.passed
    assert v4.filtered_action == "LONG"


def test_experiment_registry():
    reg = ExperimentRegistry()
    rec = reg.register(
        experiment_id="TEST-01",
        hypothesis="Test hypothesis",
        feature_set=["f1", "f2"],
        sample_window="Test window",
        in_sample_metric="IS: 100",
        out_of_sample_metric="OOS: 95",
        hurdle_rate_bps=40.0,
        status="SUPPORTED",
        key_findings="Test passed successfully",
    )
    assert rec.status == "SUPPORTED"
    assert len(reg.records) == 1
    raw_json = reg.to_json()
    assert "TEST-01" in raw_json


def test_end_to_end_pipeline_and_artifacts():
    with tempfile.TemporaryDirectory() as tmpdir:
        res = run_pipeline(symbol="BTCUSDT", timeframe="5m", output_dir=tmpdir)
        assert res["master_verdict"] in ["NOT_SUPPORTED", "SUPPORTED", "INSUFFICIENT_SAMPLE"]
        assert "jev_audit" in res
        assert "input_quality" in res
        assert "prompt_experiments" in res

        # Verify artifacts exist in tmpdir
        files = list(Path(tmpdir).iterdir())
        json_files = [f for f in files if f.name.endswith(".json")]
        csv_files = [f for f in files if f.name.endswith(".csv")]
        md_files = [f for f in files if f.name.endswith(".md")]

        assert len(json_files) == 1
        assert len(csv_files) == 1
        assert len(md_files) == 1

        # Check MD content contains 18 sections
        md_text = md_files[0].read_text(encoding="utf-8")
        for sec_num in range(1, 19):
            assert f"## {sec_num}." in md_text
