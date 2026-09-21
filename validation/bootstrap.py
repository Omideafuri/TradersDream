"""Deterministic Bootstrap Engine for Statistical Uncertainty Estimation.

Performs non-parametric bootstrap resampling on trades and forward return distributions.
Ensures 100% reproducible confidence intervals using fixed random seeds.
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Tuple, Optional
import numpy as np


@dataclass
class BootstrapMetricCI:
    metric_name: str
    point_estimate: float
    ci_lower: float
    ci_upper: float
    ci_level: float
    bootstrap_samples: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric_name": self.metric_name,
            "point_estimate": round(self.point_estimate, 4),
            "ci_lower": round(self.ci_lower, 4),
            "ci_upper": round(self.ci_upper, 4),
            "ci_level": self.ci_level,
            "bootstrap_samples": self.bootstrap_samples,
        }


class DeterministicBootstrapper:
    """Provides deterministic bootstrap resampling with fixed random seeds."""

    def __init__(
        self,
        n_samples: int = 1000,
        seed: int = 42,
        ci_level: float = 0.95,
        n_resamples: Optional[int] = None,
    ):
        self.n_samples = n_resamples if n_resamples is not None else n_samples
        self.seed = seed
        self.ci_level = ci_level

    def compute_ci(self, values: np.ndarray, metric_func=np.mean, metric_name: str = "mean") -> BootstrapMetricCI:
        """Convenience method to compute bootstrap CI for a metric."""
        return self.resample_ci(values, metric_func, metric_name)

    def resample_ci(
        self,
        values: np.ndarray,
        metric_func,
        metric_name: str,
    ) -> BootstrapMetricCI:
        """Computes bootstrap confidence interval for a custom scalar metric function."""
        n = len(values)
        if n == 0:
            return BootstrapMetricCI(metric_name, 0.0, 0.0, 0.0, self.ci_level, self.n_samples)

        point_est = float(metric_func(values))
        if n == 1:
            return BootstrapMetricCI(metric_name, point_est, point_est, point_est, self.ci_level, self.n_samples)

        rng = np.random.default_rng(self.seed)
        boot_metrics = np.empty(self.n_samples, dtype=float)

        for i in range(self.n_samples):
            resample = rng.choice(values, size=n, replace=True)
            boot_metrics[i] = metric_func(resample)

        alpha = (1.0 - self.ci_level) / 2.0
        lower = float(np.percentile(boot_metrics, alpha * 100.0))
        upper = float(np.percentile(boot_metrics, (1.0 - alpha) * 100.0))

        return BootstrapMetricCI(
            metric_name=metric_name,
            point_estimate=point_est,
            ci_lower=lower,
            ci_upper=upper,
            ci_level=self.ci_level,
            bootstrap_samples=self.n_samples,
        )

    def evaluate_trade_metrics(self, net_pnls: List[float]) -> Dict[str, BootstrapMetricCI]:
        """Computes bootstrap confidence intervals for key trade performance metrics."""
        arr = np.array(net_pnls, dtype=float)
        results: Dict[str, BootstrapMetricCI] = {}

        # 1. Mean Net PnL
        results["mean_pnl"] = self.resample_ci(arr, np.mean, "Mean Trade Net PnL ($)")

        # 2. Median Net PnL
        results["median_pnl"] = self.resample_ci(arr, np.median, "Median Trade Net PnL ($)")

        # 3. Win Rate
        results["win_rate"] = self.resample_ci(
            arr, lambda s: float((s > 0).sum() / len(s) * 100.0), "Win Rate (%)"
        )

        # 4. Profit Factor
        def pf_calc(s):
            w = s[s > 0].sum()
            l = abs(s[s < 0].sum())
            return float(w / l) if l > 0 else (999.99 if w > 0 else 0.0)

        results["profit_factor"] = self.resample_ci(arr, pf_calc, "Profit Factor")

        return results
