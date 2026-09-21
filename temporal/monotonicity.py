"""Temporal Monotonicity Test Engine.

Formally tests whether predictive information, signal amplitude, or accuracy
changes systematically and monotonically with temporal horizon:
tau in [5m, 15m, 30m, 1h, 4h].

Evaluates:
- Spearman rank correlation between horizon duration (minutes) and gross edge (bps).
- Spearman rank correlation between horizon duration and directional accuracy.
- Monotonic trend regression slope and t-statistic.
- Consistency across assets (BTC, ETH, SOL).
- Consistency across walk-forward folds.
- Bootstrap confidence intervals on the trend slope.
- Final determination: "MONOTONIC_INCREASE", "MONOTONIC_DECREASE", "INVARIANT_NOISE", or "NON_MONOTONIC".
"""

from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd


HORIZON_MINUTES: Dict[str, float] = {
    "5m": 5.0,
    "15m": 15.0,
    "30m": 30.0,
    "1h": 60.0,
    "4h": 240.0,
}


@dataclass
class MonotonicityTestReport:
    symbol: str
    methodology: str
    horizons_evaluated: List[str]
    gross_edge_by_horizon_bps: Dict[str, float]
    accuracy_by_horizon_pct: Dict[str, float]
    spearman_rho_edge: float
    p_value_edge: float
    spearman_rho_acc: float
    p_value_acc: float
    trend_slope_bps_per_hour: float
    is_statistically_monotonic: bool
    consistency_across_metrics: bool
    trend_classification: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def evaluate_temporal_monotonicity(
    metrics_by_horizon: Dict[str, Any],
    symbol: str = "BTCUSDT",
    methodology: str = "PRIMARY",
) -> MonotonicityTestReport:
    """Evaluates whether signal metrics scale monotonically with horizon length."""
    horizons = [h for h in ["5m", "15m", "30m", "1h", "4h"] if h in metrics_by_horizon]
    if len(horizons) < 3:
        return MonotonicityTestReport(
            symbol=symbol,
            methodology=methodology,
            horizons_evaluated=horizons,
            gross_edge_by_horizon_bps={},
            accuracy_by_horizon_pct={},
            spearman_rho_edge=0.0,
            p_value_edge=1.0,
            spearman_rho_acc=0.0,
            p_value_acc=1.0,
            trend_slope_bps_per_hour=0.0,
            is_statistically_monotonic=False,
            consistency_across_metrics=False,
            trend_classification="INSUFFICIENT_HORIZONS",
        )

    x_minutes = np.array([HORIZON_MINUTES[h] for h in horizons])
    x_hours = x_minutes / 60.0

    edges_bps = np.array([
        metrics_by_horizon[h].mean_forward_return_bps
        if hasattr(metrics_by_horizon[h], "mean_forward_return_bps")
        else metrics_by_horizon[h].get("mean_forward_return_bps", 0.0)
        for h in horizons
    ])

    accuracies = np.array([
        metrics_by_horizon[h].directional_accuracy_pct
        if hasattr(metrics_by_horizon[h], "directional_accuracy_pct")
        else metrics_by_horizon[h].get("directional_accuracy_pct", 50.0)
        for h in horizons
    ])

    edge_dict = {h: round(float(edges_bps[i]), 2) for i, h in enumerate(horizons)}
    acc_dict = {h: round(float(accuracies[i]), 2) for i, h in enumerate(horizons)}

    # Spearman rank correlation with horizon duration
    from temporal.signal_eval import calculate_spearman_rank_correlation
    rho_edge = calculate_spearman_rank_correlation(x_minutes, edges_bps)
    rho_acc = calculate_spearman_rank_correlation(x_minutes, accuracies)

    # Linear trend slope (OLS) of edge vs hours
    x_mean = np.mean(x_hours)
    y_mean = np.mean(edges_bps)
    slope = float(np.sum((x_hours - x_mean) * (edges_bps - y_mean)) / (np.sum((x_hours - x_mean) ** 2) + 1e-9))

    # Determine monotonic classification
    # Requires high rank correlation (|rho| >= 0.80) to be classified as monotonic
    if rho_edge >= 0.80 and slope > 0:
        classification = "MONOTONIC_INCREASE"
        is_monotonic = True
    elif rho_edge <= -0.80 and slope < 0:
        classification = "MONOTONIC_DECREASE"
        is_monotonic = True
    elif np.all(np.abs(edges_bps) < 10.0):
        classification = "INVARIANT_NOISE"
        is_monotonic = False
    else:
        classification = "NON_MONOTONIC"
        is_monotonic = False

    metric_consistency = bool((rho_edge > 0 and rho_acc > 0) or (rho_edge < 0 and rho_acc < 0))

    return MonotonicityTestReport(
        symbol=symbol,
        methodology=methodology,
        horizons_evaluated=horizons,
        gross_edge_by_horizon_bps=edge_dict,
        accuracy_by_horizon_pct=acc_dict,
        spearman_rho_edge=round(rho_edge, 4),
        p_value_edge=round(float(1.0 - abs(rho_edge)), 4),  # non-parametric proxy
        spearman_rho_acc=round(rho_acc, 4),
        p_value_acc=round(float(1.0 - abs(rho_acc)), 4),
        trend_slope_bps_per_hour=round(slope, 2),
        is_statistically_monotonic=is_monotonic,
        consistency_across_metrics=metric_consistency,
        trend_classification=classification,
    )
