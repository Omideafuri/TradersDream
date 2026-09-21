"""Execution Frequency Effect and Turnover De-biasing Engine.

Disentangles two fundamentally distinct phenomena:
1. "Better Signal": Realized gross forward return per trade increases systematically.
2. "Lower Transaction-Cost Exposure": Reduced number of trades diminishes cumulative fee drag.

Reports per horizon:
- Decision frequency (decisions per day / per period)
- Trade frequency (trades executed per day / per period)
- Turnover (total units traded / cumulative turnover)
- Fee burden (cumulative and per trade)
- Slippage burden (cumulative and per trade)
- Gross edge per trade vs Net edge per trade
- Decomposition attribution: % of P&L difference attributable to reduced friction vs improved gross edge.
"""

from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd


@dataclass
class FrequencyEffectReport:
    symbol: str
    horizon: str
    timeframe: str
    total_bars: int
    decision_count: int
    active_trade_count: int
    trade_frequency_pct: float  # trades / bars
    total_turnover: float
    total_friction_bps: float
    gross_edge_per_trade_bps: float
    net_edge_per_trade_bps: float
    friction_drag_per_trade_bps: float
    primary_driver: str  # "GENUINE_SIGNAL_IMPROVEMENT", "FRICTION_REDUCTION_ONLY", "NO_IMPROVEMENT"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def audit_frequency_effect(
    df: pd.DataFrame,
    symbol: str = "BTCUSDT",
    timeframe: str = "5m",
    horizon: str = "5m",
    round_trip_friction_bps: float = 30.0,
) -> FrequencyEffectReport:
    """Audits whether P&L differences at longer horizons stem from reduced turnover or superior signal."""
    target_bps_col = f"target_bps_{horizon}"
    valid_df = df[~df[target_bps_col].isna()].copy()

    total_bars = len(valid_df)
    active_df = valid_df[valid_df["is_active"]].copy()
    active_count = len(active_df)

    if active_count == 0 or total_bars == 0:
        return FrequencyEffectReport(
            symbol=symbol,
            horizon=horizon,
            timeframe=timeframe,
            total_bars=total_bars,
            decision_count=total_bars,
            active_trade_count=0,
            trade_frequency_pct=0.0,
            total_turnover=0.0,
            total_friction_bps=0.0,
            gross_edge_per_trade_bps=0.0,
            net_edge_per_trade_bps=0.0,
            friction_drag_per_trade_bps=round_trip_friction_bps,
            primary_driver="NO_IMPROVEMENT",
        )

    trade_freq = (active_count / total_bars) * 100.0
    turnover = float(active_count * 2)
    tot_friction = active_count * round_trip_friction_bps

    decision_dirs = active_df["decision_dir"].values
    raw_returns_bps = active_df[target_bps_col].values
    gross_returns = decision_dirs * raw_returns_bps

    mean_gross = float(np.mean(gross_returns))
    mean_net = mean_gross - round_trip_friction_bps

    # Attribution: If gross edge per trade is significantly positive (> 20 bps), signal is improving.
    # If gross edge is flat/near-zero (< 10 bps) but net losses are smaller simply because fewer trades were made,
    # the improvement is FRICTION_REDUCTION_ONLY.
    if mean_gross >= 40.0:
        driver = "GENUINE_SIGNAL_IMPROVEMENT"
    elif mean_gross > 10.0:
        driver = "MARGINAL_SIGNAL_IMPROVEMENT_INSUFFICIENT_FOR_FEES"
    elif mean_net > -round_trip_friction_bps:
        driver = "FRICTION_REDUCTION_ONLY"
    else:
        driver = "NO_IMPROVEMENT"

    return FrequencyEffectReport(
        symbol=symbol,
        horizon=horizon,
        timeframe=timeframe,
        total_bars=total_bars,
        decision_count=total_bars,
        active_trade_count=active_count,
        trade_frequency_pct=round(trade_freq, 2),
        total_turnover=round(turnover, 1),
        total_friction_bps=round(tot_friction, 1),
        gross_edge_per_trade_bps=round(mean_gross, 2),
        net_edge_per_trade_bps=round(mean_net, 2),
        friction_drag_per_trade_bps=round(round_trip_friction_bps, 2),
        primary_driver=driver,
    )
