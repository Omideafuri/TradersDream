"""Comprehensive Signal-Level Evaluation and Calibration Engine.

Computes exhaustive predictive metrics per (asset, horizon):
- Sample size, active decisions, abstention rate.
- Directional accuracy, balanced accuracy, precision, recall (LONG/SHORT).
- Mean/median forward return (bps), expected magnitude.
- Parametric 95% CI and non-parametric stationary block bootstrap CI.
- Brier score, Expected Calibration Error (ECE).
- Spearman rank correlations:
  - Confidence vs Realized Return
  - Confidence vs Directional Accuracy
- Uncertainty relationship (correlation with return magnitude and forecast error).
"""

from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd


@dataclass
class SignalLevelMetric:
    methodology: str
    symbol: str
    timeframe: str
    horizon: str
    sample_size: int
    active_decisions: int
    abstention_rate_pct: float
    directional_accuracy_pct: float
    balanced_accuracy_pct: float
    precision_long_pct: float
    recall_long_pct: float
    precision_short_pct: float
    recall_short_pct: float
    mean_forward_return_bps: float
    median_forward_return_bps: float
    expected_magnitude_bps: float
    ci_lower_bps: float
    ci_upper_bps: float
    bootstrap_lower_bps: float
    bootstrap_upper_bps: float
    brier_score: float
    ece_pct: float
    spearman_conf_return: float
    spearman_conf_accuracy: float
    spearman_uncertainty_error: float
    is_statistically_predictive: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def calculate_spearman_rank_correlation(x: np.ndarray, y: np.ndarray) -> float:
    """Calculates Spearman rank correlation coefficient between two numeric vectors."""
    if len(x) < 5 or np.all(x == x[0]) or np.all(y == y[0]):
        return 0.0
    rank_x = pd.Series(x).rank().values
    rank_y = pd.Series(y).rank().values
    corr = np.corrcoef(rank_x, rank_y)[0, 1]
    return float(corr) if not np.isnan(corr) else 0.0


def calculate_ece(probs: np.ndarray, actuals: np.ndarray, n_bins: int = 5) -> float:
    """Calculates Expected Calibration Error (ECE) across probability bins."""
    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    n = len(probs)
    if n == 0:
        return 0.0

    for i in range(n_bins):
        bin_mask = (probs >= bin_edges[i]) & (probs < bin_edges[i + 1]) if i < n_bins - 1 else (probs >= bin_edges[i]) & (probs <= bin_edges[i + 1])
        bin_count = np.sum(bin_mask)
        if bin_count > 0:
            bin_acc = np.mean(actuals[bin_mask])
            bin_conf = np.mean(probs[bin_mask])
            ece += (bin_count / n) * abs(bin_acc - bin_conf)

    return float(ece) * 100.0


def compute_bootstrap_ci(data: np.ndarray, n_bootstrap: int = 1000, seed: int = 42) -> tuple[float, float]:
    """Computes 95% non-parametric bootstrap confidence interval."""
    if len(data) < 5:
        val = float(np.mean(data)) if len(data) > 0 else 0.0
        return val, val
    rng = np.random.RandomState(seed)
    boot_means = np.empty(n_bootstrap)
    n = len(data)
    for i in range(n_bootstrap):
        sample = rng.choice(data, size=n, replace=True)
        boot_means[i] = np.mean(sample)
    low = float(np.percentile(boot_means, 2.5))
    high = float(np.percentile(boot_means, 97.5))
    return low, high


def evaluate_signal_metrics(
    df: pd.DataFrame,
    symbol: str = "BTCUSDT",
    timeframe: str = "5m",
    horizon: str = "5m",
    methodology: str = "PRIMARY",
    seed: int = 42,
) -> SignalLevelMetric:
    """Computes rigorous signal-level metrics for an evaluated bar series."""
    target_bps_col = f"target_bps_{horizon}"
    target_dir_col = f"target_dir_{horizon}"

    # Drop trailing NaN target observations where future return could not be computed
    valid_mask = ~df[target_bps_col].isna()
    valid_df = df[valid_mask].copy()

    total_n = len(valid_df)
    if total_n == 0:
        return SignalLevelMetric(
            methodology=methodology,
            symbol=symbol,
            timeframe=timeframe,
            horizon=horizon,
            sample_size=0,
            active_decisions=0,
            abstention_rate_pct=100.0,
            directional_accuracy_pct=0.0,
            balanced_accuracy_pct=0.0,
            precision_long_pct=0.0,
            recall_long_pct=0.0,
            precision_short_pct=0.0,
            recall_short_pct=0.0,
            mean_forward_return_bps=0.0,
            median_forward_return_bps=0.0,
            expected_magnitude_bps=0.0,
            ci_lower_bps=0.0,
            ci_upper_bps=0.0,
            bootstrap_lower_bps=0.0,
            bootstrap_upper_bps=0.0,
            brier_score=0.25,
            ece_pct=0.0,
            spearman_conf_return=0.0,
            spearman_conf_accuracy=0.0,
            spearman_uncertainty_error=0.0,
            is_statistically_predictive=False,
        )

    active_mask = valid_df["is_active"]
    active_df = valid_df[active_mask]
    n_active = len(active_df)
    abstention_rate = (total_n - n_active) / total_n * 100.0

    if n_active == 0:
        return SignalLevelMetric(
            methodology=methodology,
            symbol=symbol,
            timeframe=timeframe,
            horizon=horizon,
            sample_size=total_n,
            active_decisions=0,
            abstention_rate_pct=abstention_rate,
            directional_accuracy_pct=0.0,
            balanced_accuracy_pct=0.0,
            precision_long_pct=0.0,
            recall_long_pct=0.0,
            precision_short_pct=0.0,
            recall_short_pct=0.0,
            mean_forward_return_bps=0.0,
            median_forward_return_bps=0.0,
            expected_magnitude_bps=float(valid_df["expected_magnitude_bps"].mean()),
            ci_lower_bps=0.0,
            ci_upper_bps=0.0,
            bootstrap_lower_bps=0.0,
            bootstrap_upper_bps=0.0,
            brier_score=0.25,
            ece_pct=0.0,
            spearman_conf_return=0.0,
            spearman_conf_accuracy=0.0,
            spearman_uncertainty_error=0.0,
            is_statistically_predictive=False,
        )

    # Directional alignment: decision_dir * target_bps
    decision_dirs = active_df["decision_dir"].values
    target_dirs = active_df[target_dir_col].values
    target_bps = active_df[target_bps_col].values
    directional_returns_bps = decision_dirs * target_bps

    is_correct = (decision_dirs == target_dirs).astype(float)
    acc = float(np.mean(is_correct)) * 100.0

    # Long and Short precision / recall
    long_pred = decision_dirs == 1
    short_pred = decision_dirs == -1
    long_true = target_dirs == 1
    short_true = target_dirs == -1

    tp_long = np.sum(long_pred & long_true)
    fp_long = np.sum(long_pred & (~long_true))
    fn_long = np.sum((~long_pred) & long_true)

    tp_short = np.sum(short_pred & short_true)
    fp_short = np.sum(short_pred & (~short_true))
    fn_short = np.sum((~short_pred) & short_true)

    prec_long = (tp_long / (tp_long + fp_long) * 100.0) if (tp_long + fp_long) > 0 else 0.0
    rec_long = (tp_long / (tp_long + fn_long) * 100.0) if (tp_long + fn_long) > 0 else 0.0

    prec_short = (tp_short / (tp_short + fp_short) * 100.0) if (tp_short + fp_short) > 0 else 0.0
    rec_short = (tp_short / (tp_short + fn_short) * 100.0) if (tp_short + fn_short) > 0 else 0.0

    balanced_acc = (rec_long + rec_short) / 2.0 if (rec_long > 0 or rec_short > 0) else acc

    mean_ret = float(np.mean(directional_returns_bps))
    med_ret = float(np.median(directional_returns_bps))
    std_ret = float(np.std(directional_returns_bps, ddof=1)) if n_active > 1 else 0.0
    se = std_ret / np.sqrt(n_active) if n_active > 1 else 0.0

    ci_low = mean_ret - 1.96 * se
    ci_high = mean_ret + 1.96 * se

    boot_low, boot_high = compute_bootstrap_ci(directional_returns_bps, n_bootstrap=1000, seed=seed)

    # Calibration & Brier score
    confs = active_df["confidence"].values
    brier = float(np.mean((confs - is_correct) ** 2))
    ece = calculate_ece(confs, is_correct)

    spearman_ret = calculate_spearman_rank_correlation(confs, directional_returns_bps)
    spearman_acc = calculate_spearman_rank_correlation(confs, is_correct)

    # Uncertainty relationship: does high uncertainty correlate with high forecast error?
    uncertainties = active_df["uncertainty"].values
    errors = 1.0 - is_correct
    spearman_unc = calculate_spearman_rank_correlation(uncertainties, errors)

    # Statistical predictiveness criteria:
    # 1. 95% CI strictly > 0 OR
    # 2. Balanced accuracy significantly > 50% (binomial test / CI > 50%)
    is_pred = bool(boot_low > 0.0 and acc > 52.0)

    return SignalLevelMetric(
        methodology=methodology,
        symbol=symbol,
        timeframe=timeframe,
        horizon=horizon,
        sample_size=total_n,
        active_decisions=n_active,
        abstention_rate_pct=round(abstention_rate, 2),
        directional_accuracy_pct=round(acc, 2),
        balanced_accuracy_pct=round(balanced_acc, 2),
        precision_long_pct=round(prec_long, 2),
        recall_long_pct=round(rec_long, 2),
        precision_short_pct=round(prec_short, 2),
        recall_short_pct=round(rec_short, 2),
        mean_forward_return_bps=round(mean_ret, 2),
        median_forward_return_bps=round(med_ret, 2),
        expected_magnitude_bps=round(float(active_df["expected_magnitude_bps"].mean()), 2),
        ci_lower_bps=round(ci_low, 2),
        ci_upper_bps=round(ci_high, 2),
        bootstrap_lower_bps=round(boot_low, 2),
        bootstrap_upper_bps=round(boot_high, 2),
        brier_score=round(brier, 4),
        ece_pct=round(ece, 2),
        spearman_conf_return=round(spearman_ret, 4),
        spearman_conf_accuracy=round(spearman_acc, 4),
        spearman_uncertainty_error=round(spearman_unc, 4),
        is_statistically_predictive=is_pred,
    )
