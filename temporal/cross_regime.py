"""Cross-Regime Generalization and Characterization Engine.

Evaluates Jev's predictive behavior across causal market regimes per horizon:
- TRENDING_UP
- TRENDING_DOWN
- RANGE_BOUND
- HIGH_VOLATILITY
- LOW_VOLATILITY
- TRANSITION

Reports per (horizon, regime):
- Sample size
- Active decisions
- Directional accuracy
- Mean forward return (bps)
- Abstention rate (%)
- Mean confidence
- Mean uncertainty
- Net return (bps) after 30 bps round-trip friction
"""

from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd

from reconstruction.regimes import classify_causal_regime


@dataclass
class RegimeHorizonMetric:
    symbol: str
    horizon: str
    regime: str
    sample_size: int
    active_count: int
    abstention_rate_pct: float
    directional_accuracy_pct: float
    mean_forward_return_bps: float
    mean_confidence: float
    mean_uncertainty: float
    net_return_bps: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def audit_regimes_across_horizon(
    df: pd.DataFrame,
    symbol: str = "BTCUSDT",
    horizon: str = "5m",
    round_trip_friction_bps: float = 30.0,
) -> List[RegimeHorizonMetric]:
    """Audits regime breakdown for a specific horizon."""
    target_bps_col = f"target_bps_{horizon}"
    target_dir_col = f"target_dir_{horizon}"

    valid_df = df[~df[target_bps_col].isna()].copy()
    if "regime" not in valid_df.columns:
        valid_df["regime"] = [classify_causal_regime(r) for _, r in valid_df.iterrows()]

    all_regimes = [
        "TRENDING_UP",
        "TRENDING_DOWN",
        "RANGE_BOUND",
        "HIGH_VOLATILITY",
        "LOW_VOLATILITY",
        "TRANSITION",
    ]

    results = []
    for reg in all_regimes:
        reg_df = valid_df[valid_df["regime"] == reg]
        n_sample = len(reg_df)

        if n_sample == 0:
            results.append(RegimeHorizonMetric(
                symbol=symbol,
                horizon=horizon,
                regime=reg,
                sample_size=0,
                active_count=0,
                abstention_rate_pct=100.0,
                directional_accuracy_pct=0.0,
                mean_forward_return_bps=0.0,
                mean_confidence=0.5,
                mean_uncertainty=0.5,
                net_return_bps=0.0,
            ))
            continue

        active_df = reg_df[reg_df["is_active"]]
        n_active = len(active_df)
        abstention_rate = (n_sample - n_active) / n_sample * 100.0

        if n_active == 0:
            results.append(RegimeHorizonMetric(
                symbol=symbol,
                horizon=horizon,
                regime=reg,
                sample_size=n_sample,
                active_count=0,
                abstention_rate_pct=round(abstention_rate, 2),
                directional_accuracy_pct=0.0,
                mean_forward_return_bps=0.0,
                mean_confidence=round(float(reg_df["confidence"].mean()), 3),
                mean_uncertainty=round(float(reg_df["uncertainty"].mean()), 3),
                net_return_bps=0.0,
            ))
            continue

        decision_dirs = active_df["decision_dir"].values
        target_dirs = active_df[target_dir_col].values
        raw_bps = active_df[target_bps_col].values
        directional_bps = decision_dirs * raw_bps

        acc = float(np.mean(decision_dirs == target_dirs)) * 100.0
        mean_gross_bps = float(np.mean(directional_bps))
        tot_gross_bps = float(np.sum(directional_bps))
        tot_net_bps = tot_gross_bps - (n_active * round_trip_friction_bps)

        results.append(RegimeHorizonMetric(
            symbol=symbol,
            horizon=horizon,
            regime=reg,
            sample_size=n_sample,
            active_count=n_active,
            abstention_rate_pct=round(abstention_rate, 2),
            directional_accuracy_pct=round(acc, 2),
            mean_forward_return_bps=round(mean_gross_bps, 2),
            mean_confidence=round(float(active_df["confidence"].mean()), 3),
            mean_uncertainty=round(float(active_df["uncertainty"].mean()), 3),
            net_return_bps=round(tot_net_bps, 2),
        ))

    return results
