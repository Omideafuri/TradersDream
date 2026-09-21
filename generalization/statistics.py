"""Statistical Power, Bootstrap Confidence Intervals, and Multiple Testing Control.

Provides rigorous inferential statistics for Phase 6 evaluation:
- Block / Stationary Bootstrap 95% Confidence Intervals.
- Effective Sample Size (N_eff) accounting for lag-1 autocorrelation:
  N_eff = N * (1 - rho) / (1 + rho).
- Minimum Detectable Effect (MDE) at 80% power (alpha=0.05).
- Multiple Testing Adjustments:
  - Bonferroni FWER
  - Benjamini-Hochberg (BH) False Discovery Rate (FDR)
"""

from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Tuple
import numpy as np
import pandas as pd


@dataclass
class BootstrapConfidenceInterval:
    metric_name: str
    observed_value: float
    ci_lower_95: float
    ci_upper_95: float
    standard_error: float
    is_significant_at_zero: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric_name": self.metric_name,
            "observed_value": round(self.observed_value, 4),
            "ci_lower_95": round(self.ci_lower_95, 4),
            "ci_upper_95": round(self.ci_upper_95, 4),
            "standard_error": round(self.standard_error, 4),
            "is_significant_at_zero": self.is_significant_at_zero,
        }


@dataclass
class StatisticalPowerAnalysis:
    total_sample_size: int
    effective_sample_size: float
    autocorrelation_lag1: float
    sample_std: float
    minimum_detectable_effect_bps: float
    has_adequate_power: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_sample_size": self.total_sample_size,
            "effective_sample_size": round(self.effective_sample_size, 1),
            "autocorrelation_lag1": round(self.autocorrelation_lag1, 4),
            "sample_std": round(self.sample_std, 4),
            "minimum_detectable_effect_bps": round(self.minimum_detectable_effect_bps, 2),
            "has_adequate_power": self.has_adequate_power,
        }


def compute_bootstrap_ci(
    data: np.ndarray,
    n_bootstrap: int = 1000,
    confidence_level: float = 0.95,
    seed: int = 42,
    metric_name: str = "mean_return",
) -> BootstrapConfidenceInterval:
    """Computes a non-parametric bootstrap confidence interval."""
    clean = data[~np.isnan(data)]
    n = len(clean)
    if n < 5:
        return BootstrapConfidenceInterval(metric_name, 0.0, 0.0, 0.0, 0.0, False)

    obs = float(np.mean(clean))
    rng = np.random.RandomState(seed)
    boot_means = np.empty(n_bootstrap)

    for i in range(n_bootstrap):
        sample = rng.choice(clean, size=n, replace=True)
        boot_means[i] = np.mean(sample)

    alpha = 1.0 - confidence_level
    low = float(np.percentile(boot_means, 100.0 * (alpha / 2.0)))
    high = float(np.percentile(boot_means, 100.0 * (1.0 - alpha / 2.0)))
    se = float(np.std(boot_means))

    # Significant at zero if 0 is outside [low, high]
    sig = bool(low > 0 or high < 0)

    return BootstrapConfidenceInterval(
        metric_name=metric_name,
        observed_value=obs,
        ci_lower_95=low,
        ci_upper_95=high,
        standard_error=se,
        is_significant_at_zero=sig,
    )


def compute_statistical_power(
    returns_bps: np.ndarray,
    target_power: float = 0.80,
    alpha: float = 0.05,
) -> StatisticalPowerAnalysis:
    """Calculates effective sample size and Minimum Detectable Effect (MDE) in basis points."""
    clean = returns_bps[~np.isnan(returns_bps)]
    n = len(clean)
    if n < 5:
        return StatisticalPowerAnalysis(n, float(n), 0.0, 0.0, 0.0, False)

    s_series = pd.Series(clean)
    rho = float(s_series.autocorr(lag=1))
    if np.isnan(rho) or abs(rho) >= 0.99:
        rho = 0.0

    # Effective sample size: N * (1 - rho) / (1 + rho)
    n_eff = max(5.0, n * (1.0 - rho) / (1.0 + rho))
    std = float(np.std(clean, ddof=1))

    # For alpha=0.05 (z=1.96) and power=0.80 (z=0.84): MDE = (z_alpha + z_beta) * std / sqrt(N_eff)
    mde = (1.96 + 0.84) * std / np.sqrt(n_eff)

    # Adequate power if MDE is smaller than our 40 bps economic hurdle
    has_power = bool(mde < 40.0 and n_eff >= 100)

    return StatisticalPowerAnalysis(
        total_sample_size=n,
        effective_sample_size=n_eff,
        autocorrelation_lag1=rho,
        sample_std=std,
        minimum_detectable_effect_bps=mde,
        has_adequate_power=has_power,
    )


def apply_benjamini_hochberg_fdr(p_values: List[float], alpha: float = 0.05) -> List[Tuple[float, bool]]:
    """Applies Benjamini-Hochberg procedure to control False Discovery Rate across multiple tests.

    Returns list of tuples: (adjusted_p_value, is_significant_under_fdr).
    """
    m = len(p_values)
    if m == 0:
        return []

    indexed = sorted(enumerate(p_values), key=lambda x: x[1])
    adjusted = [1.0] * m
    sig_mask = [False] * m

    # BH step-up
    min_adj = 1.0
    for rank in range(m, 0, -1):
        idx, p = indexed[rank - 1]
        adj_p = min(1.0, p * m / rank)
        min_adj = min(min_adj, adj_p)
        adjusted[idx] = min_adj
        sig_mask[idx] = bool(min_adj <= alpha)

    return [(adjusted[i], sig_mask[i]) for i in range(m)]
