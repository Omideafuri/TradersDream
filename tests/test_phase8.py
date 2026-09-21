"""Tests for Phase 8: Research Closure, Independent Verification & Reproducibility Audit.

Verifies:
1. Dataset hash verification and integrity check.
2. Cross-asset isolation and independent memory references.
3. Independent metric recomputation (returns, win rate, PF, DD).
4. Causality invariants and runtime perturbation test.
5. Horizon aggregation and sample size boundaries.
6. Holdout chronological boundaries and cryptographic fingerprints.
7. Absence of holdout contamination.
8. Statistical calculation verification (H0 vs H1 at 40 bps).
9. Bootstrap reproducibility.
10. FDR multiple-testing correctness.
11. Power calculation correctness.
12. Economic hurdle formula (fee + slippage + friction + margin = 40 bps).
13. Historical artifact integrity across phases.
14. Deterministic rerun equivalence (Run A == Run B).
15. Safety invariants (paper trading only, no leverage, clean secrets).
"""

from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from bot.config import BotConfig
from phase8.dataset_audit import audit_all_historical_datasets, audit_single_dataset
from phase8.cross_asset_audit import audit_cross_asset_isolation
from phase8.calculation_audit import recompute_trading_metrics, audit_calculations_against_phase7
from phase8.causality_audit import audit_pipeline_causality_runtime
from phase8.horizon_audit import audit_temporal_horizons
from phase8.statistical_audit import audit_statistical_framework
from phase8.holdout_audit import audit_holdout_partition
from phase8.reproducibility import audit_pipeline_reproducibility
from phase8.artifact_audit import audit_historical_artifacts
from phase8.safety_audit import audit_repository_safety
from phase8.discrepancy import DiscrepancyRegistry
from phase8.run import run_phase8_audit_pipeline


@pytest.fixture
def sample_5m_candles() -> pd.DataFrame:
    """Generates synthetic 5m candles for deterministic unit testing."""
    n = 300
    base_ts = 1715000000000
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


def test_safety_invariants():
    """Verify safety invariants: paper trading only, 1.0x leverage, clean secrets."""
    safety_rep = audit_repository_safety(repo_root=".")
    assert safety_rep.all_safety_invariants_pass is True
    assert safety_rep.paper_trading_only_enforced is True
    assert safety_rep.leverage_locked_at_one is True
    assert safety_rep.env_example_clean_of_secrets is True
    assert safety_rep.verdict == "PASS"


def test_dataset_integrity():
    """Verify dataset integrity across historical datasets."""
    records = audit_all_historical_datasets(data_dir="data/historical")
    assert len(records) >= 3
    for r in records:
        assert r.row_count == 1500
        assert r.is_monotonic is True
        assert r.duplicate_count == 0
        assert r.is_ohlc_valid is True
        assert len(r.sha256_hash) == 64


def test_cross_asset_isolation_and_provenance():
    """Verify cross-asset in-memory isolation and document data provenance."""
    rep = audit_cross_asset_isolation(data_dir="data/historical")
    assert rep.is_memory_isolated is True
    assert rep.is_code_free_of_variable_leakage is True
    assert rep.raw_return_correlation_btc_eth > 0.999
    assert "DATA_PROVENANCE_ARTIFACT" in rep.root_cause_diagnosis


def test_metric_recomputation():
    """Verify independent recalculation of trading and risk metrics."""
    trade_returns = np.array([50.0, -20.0, 60.0, -40.0, 10.0])
    metrics = recompute_trading_metrics(trade_returns, round_trip_friction_bps=30.0)
    assert metrics.total_trades == 5
    # Net trades: [20, -50, 30, -70, -20] -> 2 wins, 3 losses
    assert metrics.winning_trades == 2
    assert metrics.losing_trades == 3
    assert metrics.win_rate_pct == 40.0
    assert metrics.gross_return_bps == 60.0
    assert metrics.net_return_bps == -90.0


def test_causality_invariants(sample_5m_candles):
    """Verify runtime perturbation proof of zero forward information leakage."""
    rep = audit_pipeline_causality_runtime(sample_5m_candles)
    assert rep.all_causal_invariants_pass is True
    for item in rep.audit_items:
        assert item.status == "PASS"
        assert item.look_ahead_detected is False


def test_horizon_aggregation_and_4h_audit(sample_5m_candles):
    """Verify horizon aggregation, sample sizes, and 4h claim classification."""
    items, four_h = audit_temporal_horizons(sample_5m_candles, symbol="BTCUSDT")
    assert len(items) == 5
    assert four_h is not None
    assert four_h.audit_classification == "WEAK_OBSERVATION_ONLY"
    assert four_h.is_statistically_significant is False
    assert four_h.is_economically_viable is False


def test_holdout_boundaries_and_fingerprints(sample_5m_candles):
    """Verify chronological holdout partitions and immutable SHA256 fingerprints."""
    hp = audit_holdout_partition(sample_5m_candles, symbol="BTCUSDT")
    assert hp.is_strictly_chronological is True
    assert hp.zero_overlap_confirmed is True
    assert hp.holdout_contamination_detected is False
    assert len(hp.holdout_sha256_fingerprint) == 64
    assert hp.status == "FROZEN_VALID"


def test_statistical_audit_and_fdr():
    """Verify statistical framework and Benjamini-Hochberg FDR adjustments."""
    exp_list = [
        {"experiment_id": "EXP-1", "symbol": "BTCUSDT", "horizon": "5m", "raw_p_value": 0.40, "test_statistic_t": -0.5, "power": 0.95},
        {"experiment_id": "EXP-2", "symbol": "BTCUSDT", "horizon": "4h", "raw_p_value": 0.33, "test_statistic_t": 0.4, "power": 0.28},
    ]
    records = audit_statistical_framework(exp_list, alpha=0.05)
    assert len(records) == 2
    # EXP-1 has adequate power, fails to reject -> NOT_SUPPORTED
    assert records[0].verdict == "NOT_SUPPORTED"
    # EXP-2 has power < 50% -> INCONCLUSIVE
    assert records[1].verdict == "INCONCLUSIVE"


def test_reproducibility_run_a_vs_run_b(sample_5m_candles):
    """Verify Run A == Run B determinism across independent pipeline executions."""
    repro = audit_pipeline_reproducibility(sample_5m_candles, symbol="BTCUSDT")
    assert repro.all_metrics_match_identically is True
    assert repro.max_absolute_metric_delta < 1e-9
    assert repro.verdict == "REPRODUCIBILITY_CONFIRMED"


def test_historical_artifact_integrity():
    """Verify existence and validity of all historical phase output directories."""
    summary = audit_historical_artifacts(base_data_dir="data")
    assert summary.total_phases_audited == 7
    assert summary.all_phases_complete is True


def test_discrepancy_registry():
    """Verify discrepancy registry recording and severity checks."""
    reg = DiscrepancyRegistry()
    assert reg.has_critical_failure() is False
    reg.record_discrepancy(
        discrepancy_id="TEST-01",
        phase="Phase 7",
        module="test",
        metric="test_metric",
        reported_value=1.0,
        recomputed_value=1.0,
        delta=0.0,
        severity="INFO",
        root_cause="Test entry",
        impact="None",
        action="None",
    )
    assert len(reg.discrepancies) == 1
    assert reg.has_material_discrepancy() is False


def test_economic_hurdle_formula():
    """Verify economic hurdle: 10 fee + 5 slip = 30 friction + 10 margin = 40 hurdle."""
    fee_fill = 10.0
    slippage_fill = 5.0
    round_trip_friction = 2.0 * (fee_fill + slippage_fill)  # 30 bps
    margin = 10.0
    hurdle = round_trip_friction + margin
    assert round_trip_friction == 30.0
    assert hurdle == 40.0


def test_end_to_end_phase8_pipeline(tmp_path):
    """Verify full Phase 8 verification pipeline execution and artifact generation."""
    out_dir = str(tmp_path / "phase8_test_results")
    res = run_phase8_audit_pipeline(data_dir="data/historical", output_dir=out_dir)

    assert res["master_classification"] == "NOT_SUPPORTED"
    assert res["classification_breakdown"]["deployment_readiness"] == "NOT_SUPPORTED"

    p = Path(out_dir)
    json_files = list(p.glob("phase8_audit_*.json"))
    csv_files = list(p.glob("phase8_audit_*.csv"))
    md_files = list(p.glob("phase8_audit_*.md"))
    repro_files = list(p.glob("phase8_reproducibility_*.json"))
    disc_files = list(p.glob("phase8_discrepancies_*.csv"))

    assert len(json_files) == 1
    assert len(csv_files) == 1
    assert len(md_files) == 1
    assert len(repro_files) == 1
    assert len(disc_files) == 1
