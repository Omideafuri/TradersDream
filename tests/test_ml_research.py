"""
Unit and Forensic Invariant Tests for XAU/USD ML Research Track
"""

import subprocess
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from sklearn.preprocessing import StandardScaler

from ml_research.features.feature_pipeline import (
    FEATURE_NAMES,
    WARMUP_BARS,
    compute_features,
    get_feature_matrix,
)
from ml_research.labels.label_generator import (
    HORIZONS,
    calculate_swap_days,
    compute_labels,
)


@pytest.fixture
def sample_ohlcv_data():
    """Generates synthetic 500-bar OHLCV dataframe for fast invariant testing."""
    n = 500
    dates = pd.date_range("2023-01-01", periods=n, freq="1h", tz="UTC")
    np.random.seed(42)
    prices = 1900.0 + np.cumsum(np.random.randn(n) * 2.0)
    highs = prices + np.abs(np.random.randn(n) * 1.5)
    lows = prices - np.abs(np.random.randn(n) * 1.5)
    opens = (highs + lows) / 2.0
    closes = prices
    volumes = np.zeros(n)

    df = pd.DataFrame({
        "timestamp_ms": (dates.astype(np.int64) // 10**6),
        "dt_utc": dates.astype(str),
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes,
    })
    return df


def test_feature_count_and_warmup(sample_ohlcv_data):
    """Verifies that all 24 features are created and warm-up requirements are satisfied."""
    df_feat = compute_features(sample_ohlcv_data)
    for feat in FEATURE_NAMES:
        assert feat in df_feat.columns, f"Feature {feat} missing from output dataframe"

    X, full_df = get_feature_matrix(sample_ohlcv_data)
    assert X.shape[1] == 24
    assert len(X) == len(sample_ohlcv_data) - (WARMUP_BARS - 1)
    assert not X.isna().any().any(), "Features contain unexpected NaN values after warm-up"


def test_feature_causality_perturbation(sample_ohlcv_data):
    """
    Causality Invariant Test:
    Modifying future price at index t + 5 MUST NOT affect any feature at index t.
    """
    df1 = sample_ohlcv_data.copy()
    feat1 = compute_features(df1)

    t_check = 250
    t_future = t_check + 5

    df2 = sample_ohlcv_data.copy()
    df2.loc[t_future, "close"] += 500.0  # Massive future price jump
    df2.loc[t_future, "high"] += 500.0
    feat2 = compute_features(df2)

    for feat in FEATURE_NAMES:
        val1 = feat1.loc[t_check, feat]
        val2 = feat2.loc[t_check, feat]
        assert np.isclose(val1, val2, atol=1e-10), (
            f"Leakage detected! Feature '{feat}' at t={t_check} changed when future bar {t_future} was modified. "
            f"Original: {val1}, Perturbed: {val2}"
        )


def test_label_generation_and_causality(sample_ohlcv_data):
    """Verifies forward label accounting and net return deductions."""
    df_labels = compute_labels(sample_ohlcv_data)

    for h in HORIZONS:
        assert f"ret_gross_{h}h" in df_labels.columns
        assert f"friction_{h}h" in df_labels.columns
        assert f"ret_net_{h}h" in df_labels.columns
        assert f"target_{h}h" in df_labels.columns

        # Verify net return equality
        valid_idx = df_labels[f"ret_gross_{h}h"].dropna().index
        gross = df_labels.loc[valid_idx, f"ret_gross_{h}h"]
        fric = df_labels.loc[valid_idx, f"friction_{h}h"]
        net = df_labels.loc[valid_idx, f"ret_net_{h}h"]
        target = df_labels.loc[valid_idx, f"target_{h}h"]

        assert np.allclose(net, gross - fric, atol=1e-10)
        assert np.all((target == 1.0) == (net > 0.0))


def test_swap_rollover_calculation():
    """Verifies daily 22:00 UTC and Wednesday triple rollover swap counting."""
    # Mon 20:00 to Tue 23:00 -> crosses Mon 22:00 and Tue 22:00 = 2 standard rollovers
    dt1 = pd.Timestamp("2023-01-02 20:00:00", tz="UTC")
    dt2 = pd.Timestamp("2023-01-03 23:00:00", tz="UTC")
    days = calculate_swap_days(dt1, dt2)
    assert days == 2

    # Wed 20:00 to Thu 02:00 -> crosses Wed 22:00 = 1 Wednesday triple rollover = 3 swap days
    dt_wed1 = pd.Timestamp("2023-01-04 20:00:00", tz="UTC")
    dt_wed2 = pd.Timestamp("2023-01-05 02:00:00", tz="UTC")
    days_wed = calculate_swap_days(dt_wed1, dt_wed2)
    assert days_wed == 3


def test_scaler_fit_scope():
    """Verifies StandardScaler fit strictly on train does not alter on val transform."""
    X_train = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]])
    X_val = np.array([[10.0, 20.0], [30.0, 40.0]])

    scaler = StandardScaler()
    scaler.fit(X_train)
    orig_mean = scaler.mean_.copy()
    orig_var = scaler.var_.copy()

    _ = scaler.transform(X_val)
    assert np.allclose(scaler.mean_, orig_mean)
    assert np.allclose(scaler.var_, orig_var)


def test_phase13_firewall_unmodified():
    """
    Verifies that ml_research code does not import or touch phase13.
    """
    repo_root = Path(__file__).resolve().parent.parent
    ml_dir = repo_root / "ml_research"
    for py_file in ml_dir.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        assert "phase13" not in content, f"Firewall breach! 'phase13' referenced in {py_file}"
        assert "PHASE12_STRATEGY_LOCK" not in content, f"Firewall breach! Strategy lock referenced in {py_file}"
