"""Extended Directional Forward-Return Analysis for Phase 3.

Calculates forward price movements across 5m, 15m, 30m, 1h, 4h horizons.
Separately evaluates:
- LONG:  (future_price / current_price) - 1.0
- SHORT: (current_price / future_price) - 1.0
- HOLD:  (future_price / current_price) - 1.0 (underlying market drift)

Computes statistical moments and bootstrap confidence intervals.
"""

from dataclasses import dataclass
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd

from backtest.dataset import HistoricalDecision
from backtest.forward_returns import calculate_forward_returns, HORIZON_PERIODS


@dataclass
class DirectionalHorizonStats:
    horizon: str
    action: str  # LONG, SHORT, HOLD
    count: int
    mean_return_pct: float
    median_return_pct: float
    std_return_pct: float
    win_rate_pct: float
    downside_prob_pct: float
    ci_lower_pct: float
    ci_upper_pct: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "horizon": self.horizon,
            "action": self.action,
            "count": self.count,
            "mean_return_pct": round(self.mean_return_pct, 4),
            "median_return_pct": round(self.median_return_pct, 4),
            "std_return_pct": round(self.std_return_pct, 4),
            "win_rate_pct": round(self.win_rate_pct, 2),
            "downside_prob_pct": round(self.downside_prob_pct, 2),
            "ci_lower_pct": round(self.ci_lower_pct, 4),
            "ci_upper_pct": round(self.ci_upper_pct, 4),
        }


def compute_bootstrap_ci(
    values: np.ndarray,
    n_resamples: int = 500,
    ci_level: float = 0.95,
    seed: int = 42,
) -> tuple[float, float]:
    """Computes deterministic bootstrap confidence interval on the sample mean."""
    if len(values) == 0:
        return 0.0, 0.0
    if len(values) == 1:
        return float(values[0]), float(values[0])

    rng = np.random.default_rng(seed)
    boot_means = np.empty(n_resamples, dtype=float)
    n = len(values)

    for i in range(n_resamples):
        sample = rng.choice(values, size=n, replace=True)
        boot_means[i] = np.mean(sample)

    alpha = (1.0 - ci_level) / 2.0
    lower = float(np.percentile(boot_means, alpha * 100.0))
    upper = float(np.percentile(boot_means, (1.0 - alpha) * 100.0))
    return lower, upper


def evaluate_directional_forward_returns(
    candles_df: pd.DataFrame,
    decisions: List[HistoricalDecision],
    n_bootstrap: int = 500,
    seed: int = 42,
) -> Dict[str, List[DirectionalHorizonStats]]:
    """Calculates granular forward return statistics across all horizons and actions."""
    df_fwd = calculate_forward_returns(candles_df, decisions)

    # Calculate HOLD underlying returns
    price_series = candles_df.set_index("timestamp")["close"]
    timestamps = candles_df["timestamp"].tolist()
    ts_to_idx = {ts: idx for idx, ts in enumerate(timestamps)}

    for horizon, offset in HORIZON_PERIODS.items():
        col = f"fwd_ret_{horizon}"
        # For HOLD decisions, compute raw underlying return
        for idx_row, row in df_fwd.iterrows():
            if row["action"] == "HOLD":
                ts = int(row["timestamp"])
                if ts in ts_to_idx:
                    curr_i = ts_to_idx[ts]
                    target_i = curr_i + offset
                    if target_i < len(timestamps):
                        fut_p = price_series.loc[timestamps[target_i]]
                        curr_p = row["price"]
                        df_fwd.at[idx_row, col] = (fut_p / curr_p) - 1.0

    stats_by_horizon: Dict[str, List[DirectionalHorizonStats]] = {}

    for horizon in HORIZON_PERIODS.keys():
        col = f"fwd_ret_{horizon}"
        horizon_stats: List[DirectionalHorizonStats] = []

        for action in ["LONG", "SHORT", "HOLD"]:
            sub = df_fwd[df_fwd["action"] == action][col].dropna()
            count = len(sub)

            if count > 0:
                vals = sub.to_numpy() * 100.0  # percentage
                mean_r = float(np.mean(vals))
                median_r = float(np.median(vals))
                std_r = float(np.std(vals))
                win_rate = float((vals > 0).sum() / count) * 100.0
                downside_prob = float((vals < 0).sum() / count) * 100.0
                ci_low, ci_high = compute_bootstrap_ci(vals, n_resamples=n_bootstrap, seed=seed)
            else:
                mean_r = median_r = std_r = win_rate = downside_prob = ci_low = ci_high = 0.0

            horizon_stats.append(
                DirectionalHorizonStats(
                    horizon=horizon,
                    action=action,
                    count=count,
                    mean_return_pct=mean_r,
                    median_return_pct=median_r,
                    std_return_pct=std_r,
                    win_rate_pct=win_rate,
                    downside_prob_pct=downside_prob,
                    ci_lower_pct=ci_low,
                    ci_upper_pct=ci_high,
                )
            )

        stats_by_horizon[horizon] = horizon_stats

    return stats_by_horizon
