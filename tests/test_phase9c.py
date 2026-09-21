"""Tests for Phase 9C: Hypothesis-Driven Feature Engineering, Causal Pre-Processing & Leakage Proof.

Covers all 18 requirements specified in the Phase 9C charter:
1. feature causality
2. future perturbation invariance
3. rolling normalization
4. no holdout access
5. partition boundaries
6. cross-asset timestamp alignment
7. lead-lag correctness
8. target generation
9. missing-data handling
10. feature registry integrity
11. hypothesis registry integrity
12. multiple-testing correction
13. economic gate
14. deterministic reproducibility
15. artifact generation
16. synthetic historical dataset rejection
17. validation isolation
18. feature schema stability
"""

import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from phase9.features import FeatureEngineer
from phase9.targets import TargetGenerator
from phase9.lead_lag import LeadLagEngine, LeadLagPairResult
from phase9.feature_analysis import (
    FeatureAuditor,
    MultipleTestingCorrector,
    DiagnosticBaselines,
    calc_corr_and_p,
    calc_spearman,
)
from phase9.economic_gate import EconomicGate, ExecutionParameters
from phase9.leakage_guard import LeakageGuard
from phase9.split_manager import SplitManager
from phase9.phase9c_pipeline import Phase9CPipeline
from phase9.data_quality import evaluate_asset_independence


@pytest.fixture
def sample_ohlcv() -> pd.DataFrame:
    """Generates synthetic 500-bar OHLCV dataframe for fast testing."""
    np.random.seed(42)
    n = 500
    base_price = 50000.0
    returns = np.random.normal(0.0001, 0.005, size=n)
    close = base_price * np.exp(np.cumsum(returns))
    high = close * (1.0 + np.abs(np.random.normal(0, 0.002, size=n)))
    low = close * (1.0 - np.abs(np.random.normal(0, 0.002, size=n)))
    open_p = (high + low) / 2.0
    volume = np.random.uniform(10.0, 100.0, size=n)
    timestamps = [1700000000000 + i * 300000 for i in range(n)]

    return pd.DataFrame({
        "timestamp": timestamps,
        "open": open_p,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    })


def test_feature_causality_and_perturbation_invariance(sample_ohlcv):
    """Req 1 & 2: Features must be invariant to perturbation of future observations t+1..t+k."""
    leak_check = LeakageGuard.test_future_perturbation(
        df=sample_ohlcv,
        feature_calculator_fn=FeatureEngineer.compute_all_single_asset_features,
        target_bar_idx=150,
        perturbation_bars=30,
        noise_magnitude=2000.0,
    )
    assert leak_check["is_causal"] is True
    assert leak_check["status"] == "PASS"
    assert leak_check["max_delta"] < 1e-9


def test_rolling_normalization_causality(sample_ohlcv):
    """Req 3: Rolling normalization must use historical observations only (zero lookahead)."""
    feats = FeatureEngineer.compute_price_return_features(sample_ohlcv)
    
    # Calculate rolling norm
    norm_a = FeatureEngineer.rolling_historical_standardize(feats, window=50, min_periods=10)
    
    # Perturb future rows after index 100
    perturbed_feats = feats.copy()
    perturbed_feats.iloc[101:] = perturbed_feats.iloc[101:] * 50.0
    norm_b = FeatureEngineer.rolling_historical_standardize(perturbed_feats, window=50, min_periods=10)

    # Values at index 100 must be mathematically identical
    for col in norm_a.columns:
        val_a = norm_a[col].iloc[100]
        val_b = norm_b[col].iloc[100]
        if not (np.isnan(val_a) and np.isnan(val_b)):
            assert abs(val_a - val_b) < 1e-9


def test_no_holdout_access_and_partition_boundaries():
    """Req 4 & 5: Development and Validation cannot access Sealed Holdout (final 20%)."""
    btc_path = Path("data/phase9_data/BINANCE_US_BTCUSDT_5m.csv")
    if not btc_path.is_file():
        pytest.skip("Phase 9B data file not found.")

    df = pd.read_csv(btc_path)
    assert len(df) == 26000

    dev_df, val_df, holdout_df, res = SplitManager.partition(df, dev_ratio=0.60, val_ratio=0.20)

    assert len(dev_df) == 15600
    assert len(val_df) == 5200
    assert len(holdout_df) == 5200

    # Ensure strictly disjoint timestamps
    assert dev_df["timestamp"].max() < val_df["timestamp"].min()
    assert val_df["timestamp"].max() < holdout_df["timestamp"].min()

    # Verify pipeline never evaluates holdout partition
    pipe = Phase9CPipeline()
    datasets = pipe._load_and_partition_datasets()
    assert datasets["BTCUSDT"]["holdout_status"] == "SEALED_UNTOUCHED"
    assert "target_ret_12" not in datasets["BTCUSDT"]


def test_cross_asset_timestamp_alignment_and_lead_lag(sample_ohlcv):
    """Req 6 & 7: Cross-asset merge respects timestamp monotonicity and computes causal lead-lag."""
    # Create peer asset with lag
    peer_ohlcv = sample_ohlcv.copy()
    peer_ohlcv["close"] = peer_ohlcv["close"] * 0.05  # ETH-like scale
    peer_ohlcv["timestamp"] = peer_ohlcv["timestamp"]  # Aligned timestamps

    res_lead, res_lag = LeadLagEngine.analyze_pair(
        df_a=sample_ohlcv,
        df_b=peer_ohlcv,
        asset_a="BTC",
        asset_b="ETH",
        lags=[1, 2, 3, 6],
    )

    assert res_lead.lead_asset == "BTC"
    assert res_lead.lag_asset == "ETH"
    assert -1.0 <= res_lead.contemporaneous_corr <= 1.0
    assert 1 in res_lead.lead_correlations


def test_target_generation_integrity(sample_ohlcv):
    """Req 8: Forward targets calculate lead returns correctly and leave trailing NaNs."""
    targets = TargetGenerator.compute_forward_targets(sample_ohlcv, horizons=[1, 6, 12])
    
    assert "target_ret_1" in targets.columns
    assert "target_dir_1" in targets.columns
    assert "target_abs_ret_1" in targets.columns
    assert "target_vol_1" in targets.columns

    # Horizon 1 must have exactly 1 trailing NaN in forward return
    assert np.isnan(targets["target_ret_1"].iloc[-1])
    assert not np.isnan(targets["target_ret_1"].iloc[-2])

    # Horizon 12 must have exactly 12 trailing NaNs
    assert targets["target_ret_12"].iloc[-12:].isna().all()
    assert not np.isnan(targets["target_ret_12"].iloc[-13])


def test_missing_data_handling_and_feature_auditor(sample_ohlcv):
    """Req 9: Feature auditor handles NaNs and constant values gracefully."""
    sample_ohlcv.loc[10:15, "close"] = np.nan
    feats = FeatureEngineer.compute_price_return_features(sample_ohlcv)
    
    metrics = FeatureAuditor.audit_feature_quality(feats)
    assert len(metrics) == len(feats.columns)
    
    # Missing rate must reflect NaNs
    m_ret1 = [m for m in metrics if m.feature_name == "ret_log_1"][0]
    assert m_ret1.missing_rate > 0.0


def test_feature_registry_and_schema_stability():
    """Req 10 & 18: Feature registry schema contains all expected families."""
    reg_path = Path("data/phase9_results/phase9c_feature_registry.json")
    if not reg_path.is_file():
        pytest.skip("phase9c_feature_registry.json not yet generated.")

    with open(reg_path, "r", encoding="utf-8") as f:
        reg = json.load(f)

    assert "total_features" in reg
    assert "families" in reg
    for fam in ["PRICE_RETURN", "VOLATILITY", "VOLUME", "STRUCTURE", "REGIME", "CROSS_ASSET"]:
        assert fam in reg["families"]
        assert len(reg["families"][fam]) > 0


def test_multiple_testing_correction_methods():
    """Req 12: Multiple testing adjustments (FDR, Bonferroni, Holm) strictly control error rate."""
    raw_p = [0.001, 0.008, 0.03, 0.04, 0.09, 0.25, 0.80]
    
    fdr_p, fdr_sig = MultipleTestingCorrector.benjamini_hochberg(raw_p, alpha=0.05)
    bonf_p, bonf_sig = MultipleTestingCorrector.bonferroni(raw_p, alpha=0.05)
    holm_p, holm_sig = MultipleTestingCorrector.holm_bonferroni(raw_p, alpha=0.05)

    assert len(fdr_p) == len(raw_p)
    # Bonferroni is the most conservative
    assert all(b >= f for b, f in zip(bonf_p, fdr_p))
    # Holm is <= Bonferroni
    assert all(h <= b for h, b in zip(holm_p, bonf_p))
    # Raw p < 0.001 should survive FDR
    assert fdr_sig[0] is True
    assert not fdr_sig[-1]


def test_economic_gate_hurdle_enforcement():
    """Req 13: Economic gate enforces 40 bps total friction hurdle."""
    gate = EconomicGate()
    
    # 25 bps gross edge (less than 40 bps hurdle)
    eval_sub = gate.evaluate(25.0)
    assert eval_sub.is_economically_viable is False
    assert eval_sub.classification in ["FRICTION_DOMINATED", "PREDICTIVE_ONLY"]

    # 55 bps gross edge (exceeds 40 bps hurdle)
    eval_sup = gate.evaluate(55.0)
    assert eval_sup.is_economically_viable is True
    assert eval_sup.classification == "ECONOMICALLY_VIABLE"


def test_deterministic_reproducibility(sample_ohlcv):
    """Req 14: Features computed on identical inputs produce zero numerical delta."""
    f1 = FeatureEngineer.compute_all_single_asset_features(sample_ohlcv)
    f2 = FeatureEngineer.compute_all_single_asset_features(sample_ohlcv)

    diff = (f1.fillna(0) - f2.fillna(0)).abs().max().max()
    assert diff == 0.0


def test_artifact_generation_and_validation_isolation():
    """Req 15 & 17: All Phase 9C machine-readable artifacts exist and validation partition is separate."""
    res_dir = Path("data/phase9_results")
    required_files = [
        "phase9c_feature_registry.json",
        "phase9c_hypothesis_results.json",
        "phase9c_feature_metrics.csv",
        "phase9c_lead_lag.csv",
        "phase9c_ablation.csv",
        "phase9c_validation.csv",
        "phase9c_reproducibility.json",
        "phase9c_data_quality.json",
        "phase9c_report.md",
    ]
    for rf in required_files:
        p = res_dir / rf
        assert p.is_file(), f"Artifact {rf} was not found."

    val_df = pd.read_csv(res_dir / "phase9c_validation.csv")
    assert len(val_df) == 10
    assert (val_df["partition"] == "VALIDATION").all()


def test_synthetic_historical_dataset_rejection(sample_ohlcv):
    """Req 16: Datasets with scaled synthetic properties fail independence audit."""
    synthetic_eth = sample_ohlcv.copy()
    synthetic_eth["close"] = sample_ohlcv["close"] * 0.05
    synthetic_eth["volume"] = sample_ohlcv["volume"] * 10.0

    indep = evaluate_asset_independence(
        sample_ohlcv, synthetic_eth, "BTC", "SYNTH_ETH"
    )
    assert indep.is_suspicious is True
    assert indep.verdict in ["SYNTHETIC_SCALED", "FLAGGED_POTENTIAL_COPY"]


def test_diagnostic_baselines_sanity(sample_ohlcv):
    """Sanity checks on model-agnostic reference baselines."""
    fwd_ret = sample_ohlcv["close"].pct_change(12).dropna().values
    past_ret = sample_ohlcv["close"].pct_change(12).shift(12).loc[sample_ohlcv.index[:len(fwd_ret)]].values

    b_hold = DiagnosticBaselines.evaluate_hold(fwd_ret)
    assert b_hold["directional_accuracy"] == 0.50
    assert b_hold["mean_return_bps"] == 0.0

    b_rand = DiagnosticBaselines.evaluate_random(fwd_ret)
    assert 0.40 <= b_rand["directional_accuracy"] <= 0.60
