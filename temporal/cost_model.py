"""Economic Analysis and Transaction Cost Model for Multi-Horizon Evaluation.

Applies the frozen Phase 6 cost parameters:
- Fee per fill: 10 bps (0.10%)
- Slippage per fill: 5 bps (0.05%)
- Round-trip transaction friction: 30 bps (0.30%)
- Economic safety margin: 10 bps (0.10%)
- Required economic hurdle: 40 bps (0.40%)

Classifies outcomes strictly according to economic edge:
- SUPPORTED: net return > 0 and gross return >= 40 bps
- PREDICTIVE_BUT_NOT_ECONOMIC: gross return > 0 but net return <= 0 (or gross < 40 bps)
- NOT_SUPPORTED: gross return <= 0
"""

from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd


@dataclass
class HorizonEconomicReport:
    methodology: str
    symbol: str
    timeframe: str
    horizon: str
    trade_count: int
    turnover: float
    gross_return_bps: float
    fee_burden_bps: float
    slippage_burden_bps: float
    round_trip_friction_bps: float
    safety_margin_bps: float
    net_return_bps: float
    net_expectancy_bps_per_trade: float
    profit_factor: float
    max_drawdown_pct: float
    classification: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def evaluate_horizon_economics(
    df: pd.DataFrame,
    symbol: str = "BTCUSDT",
    timeframe: str = "5m",
    horizon: str = "5m",
    methodology: str = "PRIMARY",
    fee_bps: float = 10.0,
    slippage_bps: float = 5.0,
    safety_margin_bps: float = 10.0,
) -> HorizonEconomicReport:
    """Evaluates cost-adjusted economic performance of active trades across the horizon."""
    target_bps_col = f"target_bps_{horizon}"
    valid_df = df[~df[target_bps_col].isna()].copy()

    active_df = valid_df[valid_df["is_active"]].copy()
    trade_count = len(active_df)
    round_trip_friction = 2.0 * (fee_bps + slippage_bps)  # 30 bps

    if trade_count == 0:
        return HorizonEconomicReport(
            methodology=methodology,
            symbol=symbol,
            timeframe=timeframe,
            horizon=horizon,
            trade_count=0,
            turnover=0.0,
            gross_return_bps=0.0,
            fee_burden_bps=0.0,
            slippage_burden_bps=0.0,
            round_trip_friction_bps=round_trip_friction,
            safety_margin_bps=safety_margin_bps,
            net_return_bps=0.0,
            net_expectancy_bps_per_trade=0.0,
            profit_factor=0.0,
            max_drawdown_pct=0.0,
            classification="NOT_SUPPORTED",
        )

    decision_dirs = active_df["decision_dir"].values
    raw_returns_bps = active_df[target_bps_col].values
    gross_trade_returns = decision_dirs * raw_returns_bps

    # Total and average burdens
    tot_fee_burden = trade_count * (2.0 * fee_bps)
    tot_slip_burden = trade_count * (2.0 * slippage_bps)
    tot_friction = trade_count * round_trip_friction

    total_gross_return_bps = float(np.sum(gross_trade_returns))
    total_net_return_bps = total_gross_return_bps - tot_friction

    mean_gross_bps = float(np.mean(gross_trade_returns))
    mean_net_bps = mean_gross_bps - round_trip_friction

    # Profit factor: sum(positive net trades) / abs(sum(negative net trades))
    net_trades = gross_trade_returns - round_trip_friction
    pos_trades = net_trades[net_trades > 0]
    neg_trades = net_trades[net_trades < 0]

    sum_pos = float(np.sum(pos_trades)) if len(pos_trades) > 0 else 0.0
    sum_neg = float(np.abs(np.sum(neg_trades))) if len(neg_trades) > 0 else 0.0
    profit_factor = (sum_pos / sum_neg) if sum_neg > 0 else (999.0 if sum_pos > 0 else 0.0)

    # Maximum Drawdown on cumulative net returns
    cum_net = np.cumsum(net_trades)
    running_max = np.maximum.accumulate(cum_net)
    drawdowns = running_max - cum_net
    max_dd_bps = float(np.max(drawdowns)) if len(drawdowns) > 0 else 0.0
    max_dd_pct = max_dd_bps / 100.0  # approximate % drawdown

    # Turnover = 2 * trade_count (entry + exit)
    turnover = float(trade_count * 2)

    # Economic Classification
    economic_hurdle = round_trip_friction + safety_margin_bps  # 40 bps
    if total_net_return_bps > 0 and mean_gross_bps >= economic_hurdle:
        classification = "SUPPORTED"
    elif mean_gross_bps > 0:
        classification = "PREDICTIVE_BUT_NOT_ECONOMIC"
    else:
        classification = "NOT_SUPPORTED"

    return HorizonEconomicReport(
        methodology=methodology,
        symbol=symbol,
        timeframe=timeframe,
        horizon=horizon,
        trade_count=trade_count,
        turnover=turnover,
        gross_return_bps=round(total_gross_return_bps, 2),
        fee_burden_bps=round(tot_fee_burden, 2),
        slippage_burden_bps=round(tot_slip_burden, 2),
        round_trip_friction_bps=round(round_trip_friction, 2),
        safety_margin_bps=round(safety_margin_bps, 2),
        net_return_bps=round(total_net_return_bps, 2),
        net_expectancy_bps_per_trade=round(mean_net_bps, 2),
        profit_factor=round(profit_factor, 2),
        max_drawdown_pct=round(max_dd_pct, 2),
        classification=classification,
    )
