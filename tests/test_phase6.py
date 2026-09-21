"""Automated Test Suite for Phase 6 Dataset Expansion & Generalization.

Tests:
1. Data loading and deterministic SHA256 hashing.
2. Data quality audit (monotonicity, duplicates, gaps, OHLC bounds, non-positive price).
3. Chronological temporal partitioning (Dev 60%, Val 20%, Holdout 20%, zero overlap).
4. Causal regime classification and macro period diversity.
5. Multi-horizon signal evaluation (5m, 15m, 30m, 1h, 4h).
6. Statistical power analysis and bootstrap confidence intervals.
7. Benjamini-Hochberg FDR multiple-testing adjustments.
8. Abstention generalization (NO_EDGE vs active trades, capital protection ratio).
9. Economic signal friction gate (40 bps hurdle).
10. Model-agnostic baselines (7 benchmarks).
11. Multi-fold walk-forward validation (4-fold chronological boundaries).
12. Cross-asset evaluation & transfer experiments (BTC, ETH, SOL).
13. Pre-registered experiment ledger & config hashing.
14. Full pipeline artifact generation (JSON, CSV, 26-section Markdown report).
15. Absolute safety invariants (PAPER_TRADING_ONLY, USE_LIVE_JEV).
"""

import json
from pathlib import Path
import tempfile
import pytest
import numpy as np
import pandas as pd

from generalization.data_loader import DatasetLoader, DatasetMetadata
from generalization.data_quality import audit_dataset_quality, DataQualityAuditReport
from generalization.temporal import partition_dataset_chronologically
from generalization.regimes import audit_regime_generalization, identify_macro_market_episodes
from generalization.signal_eval import evaluate_signal_across_horizons, calculate_spearman_rank_correlation, calculate_ece
from generalization.statistics import compute_bootstrap_ci, compute_statistical_power, apply_benjamini_hochberg_fdr
from generalization.abstention import audit_abstention_generalization
from generalization.gate import EconomicSignalGate
from generalization.baselines import evaluate_phase6_baselines
from generalization.walk_forward import run_phase6_walk_forward
from generalization.cross_asset import evaluate_asset_profile, run_cross_asset_transfer_experiments
from generalization.registry import Phase6ExperimentRegistry
from generalization.report import generate_phase6_markdown_report, save_phase6_artifacts
from generalization.run import run_phase6_pipeline
from bot.config import get_config, BotConfig


@pytest.fixture
def multiasset_sample_dfs():
    """Generates synthetic multi-asset OHLCV data for BTC, ETH, and SOL."""
    dfs = {}
    n = 300
    base_ts = 1704067200000

    assets_config = [
        ("BTCUSDT", 60000.0, 42),
        ("ETHUSDT", 3000.0, 43),
        ("SOLUSDT", 150.0, 44),
    ]

    for sym, base_p, seed in assets_config:
        rng = np.random.RandomState(seed)
        returns = rng.normal(0.0001, 0.002, size=n)
        price = base_p * np.exp(np.cumsum(returns))
        high = price * (1.0 + np.abs(rng.normal(0, 0.002, size=n)))
        low = price * (1.0 - np.abs(rng.normal(0, 0.002, size=n)))
        open_p = price * (1.0 + rng.normal(0, 0.0005, size=n))
        high = np.maximum(high, np.maximum(open_p, price))
        low = np.minimum(low, np.minimum(open_p, price))
        volume = rng.uniform(50.0, 500.0, size=n)
        ts = [base_ts + i * 300000 for i in range(n)]

        dfs[sym] = pd.DataFrame({
            "timestamp": ts,
            "open": open_p,
            "high": high,
            "low": low,
            "close": price,
            "volume": volume,
        })

    return dfs


def test_safety_invariants_strictly_maintained():
    """Verifies safety tripwires: real money, live trading, and live execution remain forbidden."""
    cfg = get_config()
    assert cfg.paper_trading_only is True
    assert cfg.leverage == 1.0
    # Verify environment overrides cannot start live exchange execution
    assert not hasattr(cfg, "EXECUTE_REAL_ORDERS")
    assert getattr(cfg, "USE_LIVE_JEV", False) is False


def test_data_loader_and_sha256_hash(multiasset_sample_dfs):
    with tempfile.TemporaryDirectory() as tmpdir:
        loader = DatasetLoader(data_dir=tmpdir)
        df_btc = multiasset_sample_dfs["BTCUSDT"]
        h1 = loader.compute_sha256(df_btc)
        h2 = loader.compute_sha256(df_btc)
        assert h1 == h2
        assert len(h1) == 64


def test_data_quality_audit(multiasset_sample_dfs):
    df_btc = multiasset_sample_dfs["BTCUSDT"]
    dq = audit_dataset_quality(df_btc, symbol="BTCUSDT")
    assert dq.status == "PASSED"
    assert dq.total_candles == len(df_btc)
    assert dq.duplicate_count == 0
    assert dq.gap_count == 0
    assert dq.ohlc_violation_count == 0
    assert dq.is_strictly_monotonic is True

    # Test failure on corrupted OHLC
    bad_df = df_btc.copy()
    bad_df.loc[5, "high"] = bad_df.loc[5, "low"] - 100.0  # High < Low violation
    bad_dq = audit_dataset_quality(bad_df, symbol="BTCUSDT")
    assert bad_dq.status == "CONTAMINATED"
    assert bad_dq.ohlc_violation_count > 0


def test_chronological_temporal_partitioning(multiasset_sample_dfs):
    df_btc = multiasset_sample_dfs["BTCUSDT"]
    dev, val, holdout, rep = partition_dataset_chronologically(df_btc, symbol="BTCUSDT")
    assert len(dev) + len(val) + len(holdout) == len(df_btc)
    assert rep.integrity_status == "PASSED"
    assert rep.is_frozen is True
    assert dev["timestamp"].iloc[-1] < val["timestamp"].iloc[0]
    assert val["timestamp"].iloc[-1] < holdout["timestamp"].iloc[0]


def test_regime_generalization_and_macro_episodes(multiasset_sample_dfs):
    df_btc = multiasset_sample_dfs["BTCUSDT"]
    reg_metrics = audit_regime_generalization(df_btc)
    assert len(reg_metrics) == 6
    names = [r.regime_name for r in reg_metrics]
    assert "TRENDING_UP" in names
    assert "RANGE_BOUND" in names

    episodes = identify_macro_market_episodes(df_btc, window_bars=50)
    assert len(episodes) > 0
    assert episodes[0].episode_name in ["SUSTAINED_BULL", "SUSTAINED_BEAR", "SIDEWAYS_CHOP", "SHARP_SELLOFF"]


def test_signal_evaluation_metrics(multiasset_sample_dfs):
    df_btc = multiasset_sample_dfs["BTCUSDT"]
    hz_metrics = evaluate_signal_across_horizons(df_btc, symbol="BTCUSDT")
    assert len(hz_metrics) >= 4
    names = [h.horizon_name for h in hz_metrics]
    assert "5m" in names
    assert "15m" in names
    for h in hz_metrics:
        assert 0.0 <= h.brier_score <= 1.0
        assert 0.0 <= h.abstention_rate_pct <= 100.0


def test_statistics_bootstrap_and_power():
    data = np.array([10.0, 20.0, 30.0, -10.0, 15.0, 25.0, -5.0, 40.0])
    ci = compute_bootstrap_ci(data, n_bootstrap=200, seed=42)
    assert ci.ci_lower_95 <= ci.observed_value <= ci.ci_upper_95

    power = compute_statistical_power(data)
    assert power.effective_sample_size > 0
    assert power.minimum_detectable_effect_bps > 0


def test_benjamini_hochberg_fdr():
    p_values = [0.001, 0.01, 0.04, 0.15, 0.40]
    adjusted = apply_benjamini_hochberg_fdr(p_values, alpha=0.05)
    assert len(adjusted) == len(p_values)
    # The smallest p-value should be adjusted and remain significant
    assert adjusted[0][0] <= 0.05
    assert adjusted[0][1] is True


def test_abstention_generalization(multiasset_sample_dfs):
    df_eth = multiasset_sample_dfs["ETHUSDT"]
    rep = audit_abstention_generalization(df_eth, symbol="ETHUSDT")
    assert rep.total_bars == len(df_eth)
    assert rep.active_rate_pct + rep.abstention_rate_pct == pytest.approx(100.0, 0.1)
    assert rep.verdict in ["GENERALIZED", "UNSTABLE", "INSUFFICIENT_SAMPLE"]


def test_economic_signal_gate():
    gate = EconomicSignalGate(round_trip_fee_bps=20.0, round_trip_slippage_bps=10.0, safety_margin_bps=10.0)
    assert gate.hurdle_bps == 40.0

    # 1. Negative gross edge
    e1 = gate.evaluate_aggregate_edge(symbol="BTC", action="LONG", win_rate_pct=48.0, expected_magnitude_bps=50.0)
    assert e1.economic_status == "NOT_SUPPORTED"
    assert not e1.gate_passed

    # 2. Predictive before costs, but negative after friction
    e2 = gate.evaluate_aggregate_edge(symbol="BTC", action="LONG", win_rate_pct=52.0, expected_magnitude_bps=50.0)
    # Gross edge = (2 * 0.52 - 1) * 50 = 2.0 bps. Net = 2.0 - 40 = -38 bps.
    assert e2.economic_status == "PREDICTIVE_BUT_NOT_ECONOMIC"
    assert not e2.gate_passed

    # 3. True economic edge
    e3 = gate.evaluate_aggregate_edge(symbol="BTC", action="LONG", win_rate_pct=65.0, expected_magnitude_bps=150.0)
    # Gross edge = 0.30 * 150 = 45 bps. Net = 45 - 40 = 5 bps.
    assert e3.economic_status == "SUPPORTED"
    assert e3.gate_passed


def test_phase6_baselines(multiasset_sample_dfs):
    df_sol = multiasset_sample_dfs["SOLUSDT"]
    res = evaluate_phase6_baselines(df_sol, symbol="SOLUSDT")
    assert len(res) == 7
    names = [r.baseline_name for r in res]
    assert "Always_HOLD" in names
    assert "Random_Direction" in names
    assert "Donchian_Channel_Breakout" in names


def test_walk_forward_multi_fold(multiasset_sample_dfs):
    df_btc = multiasset_sample_dfs["BTCUSDT"]
    folds = run_phase6_walk_forward(df_btc, symbol="BTCUSDT", n_folds=4)
    assert len(folds) == 4
    for i, f in enumerate(folds, start=1):
        assert f.fold_index == i
        assert f.train_bars > 0
        assert f.test_bars > 0


def test_cross_asset_transfer(multiasset_sample_dfs):
    transfers = run_cross_asset_transfer_experiments(multiasset_sample_dfs)
    assert len(transfers) == 4
    assert transfers[0].transfer_id == "XFER-01"
    assert transfers[0].source_asset == "BTCUSDT"
    assert transfers[0].target_asset == "ETHUSDT"


def test_experiment_registry_and_fdr():
    reg = Phase6ExperimentRegistry()
    reg.register(
        experiment_id="TEST-01",
        hypothesis="Test hypothesis 1",
        dataset="BTC 5m",
        asset="BTC",
        timeframe="5m",
        period="OOS",
        feature_version="v1",
        prompt_version="p1",
        configuration_dict={"test": 1},
        random_seed=42,
        primary_metric="Accuracy",
        success_criterion="Acc > 52%",
        empirical_result="Acc: 51%",
        p_value=0.03,
        status="NOT_SUPPORTED",
        notes="Test run",
    )
    reg.apply_multiple_testing_adjustments(alpha=0.05)
    entries = reg.to_list()
    assert len(entries) == 1
    assert "configuration_hash" in entries[0]
    assert "adjusted_p_value" in entries[0]


def test_phase6_pipeline_and_26_section_report(multiasset_sample_dfs):
    with tempfile.TemporaryDirectory() as tmpdir:
        # Save sample datasets to tmpdir
        for sym, df in multiasset_sample_dfs.items():
            df.to_csv(Path(tmpdir) / f"{sym}_5m_candles.csv", index=False)

        res = run_phase6_pipeline(
            assets=["BTCUSDT", "ETHUSDT"],
            timeframe="5m",
            target_candles=300,
            data_dir=tmpdir,
            output_dir=tmpdir,
            force_fetch=False,
        )

        assert res["master_verdict"] in ["NOT_SUPPORTED", "SUPPORTED", "INSUFFICIENT_SAMPLE"]
        assert len(res["data_quality"]) == 2
        assert len(res["transfers"]) > 0

        # Check artifact files
        files = list(Path(tmpdir).iterdir())
        json_f = [f for f in files if f.name.endswith(".json")]
        csv_f = [f for f in files if f.name.endswith(".csv") and "phase6" in f.name]
        md_f = [f for f in files if f.name.endswith(".md") and "phase6" in f.name]

        assert len(json_f) == 1
        assert len(csv_f) == 1
        assert len(md_f) == 1

        md_text = md_f[0].read_text(encoding="utf-8")
        for i in range(1, 27):
            assert f"## {i}." in md_text
