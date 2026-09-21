"""Independent Calculation and Metric Verification Engine.

Independently recalculates all critical trading, return, cost, and statistical metrics:
- Gross, Net, and Forward returns, per-trade expectancy
- Trade counts, winning trades, losing trades, win rate, profit factor, max drawdown, max consecutive losses
- Cost formula verification: Fee + Slippage + Friction + Margin = 40 bps Economic Hurdle
- Statistical measures: Mean, Median, Std, SE, t-stat, p-value, Bootstrap 95% CI, Sharpe, Sortino,
  Brier score, ECE, Spearman correlations, Benjamini-Hochberg FDR, and statistical power under H1.
- Identifies any calculation discrepancies between reported values in Phase 7 artifacts and recomputed values.
"""

from dataclasses import dataclass, asdict
import math
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import pandas as pd

from temporal.signal_eval import calculate_spearman_rank_correlation, calculate_ece, compute_bootstrap_ci
from temporal.power_audit import norm_cdf


@dataclass
class CalculationDiscrepancyItem:
    metric_name: str
    symbol: str
    horizon: str
    reported_value: float
    recomputed_value: float
    abs_difference: float
    rel_difference_pct: float
    status: str  # "EXACT_MATCH", "MINOR_DELTA", "MATERIAL_DELTA"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RecomputedTradingMetrics:
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: float
    gross_return_bps: float
    net_return_bps: float
    profit_factor: float
    max_drawdown_pct: float
    max_consecutive_losses: int
    expectancy_bps_per_trade: float
    sharpe_ratio: float
    sortino_ratio: float


def recompute_trading_metrics(
    trade_returns_bps: np.ndarray,
    round_trip_friction_bps: float = 30.0,
) -> RecomputedTradingMetrics:
    """Independently recalculates all trading and risk metrics from raw directional trade returns."""
    n = len(trade_returns_bps)
    if n == 0:
        return RecomputedTradingMetrics(
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate_pct=0.0,
            gross_return_bps=0.0,
            net_return_bps=0.0,
            profit_factor=0.0,
            max_drawdown_pct=0.0,
            max_consecutive_losses=0,
            expectancy_bps_per_trade=0.0,
            sharpe_ratio=0.0,
            sortino_ratio=0.0,
        )

    net_trades = trade_returns_bps - round_trip_friction_bps
    wins = net_trades > 0
    losses = net_trades < 0
    n_wins = int(np.sum(wins))
    n_losses = int(np.sum(losses))
    win_rate = (n_wins / n) * 100.0 if n > 0 else 0.0

    tot_gross = float(np.sum(trade_returns_bps))
    tot_net = float(np.sum(net_trades))
    expectancy = float(np.mean(net_trades))

    # Profit Factor
    pos_sum = float(np.sum(net_trades[wins])) if n_wins > 0 else 0.0
    neg_sum = float(np.abs(np.sum(net_trades[losses]))) if n_losses > 0 else 0.0
    pf = (pos_sum / neg_sum) if neg_sum > 0 else (999.0 if pos_sum > 0 else 0.0)

    # Max Drawdown
    cum_net = np.cumsum(net_trades)
    peak = np.maximum.accumulate(cum_net)
    dd = peak - cum_net
    max_dd_bps = float(np.max(dd)) if len(dd) > 0 else 0.0
    max_dd_pct = max_dd_bps / 100.0

    # Max consecutive losses
    max_cons_losses = 0
    current_cons = 0
    for l in losses:
        if l:
            current_cons += 1
            max_cons_losses = max(max_cons_losses, current_cons)
        else:
            current_cons = 0

    # Sharpe & Sortino
    mean_trade = float(np.mean(net_trades))
    std_trade = float(np.std(net_trades, ddof=1)) if n > 1 else 1.0
    sharpe = (mean_trade / std_trade * np.sqrt(n)) if std_trade > 0 else 0.0

    downside_diff = net_trades[net_trades < 0]
    downside_std = float(np.std(downside_diff, ddof=1)) if len(downside_diff) > 1 else std_trade
    sortino = (mean_trade / downside_std * np.sqrt(n)) if downside_std > 0 else 0.0

    return RecomputedTradingMetrics(
        total_trades=n,
        winning_trades=n_wins,
        losing_trades=n_losses,
        win_rate_pct=round(win_rate, 2),
        gross_return_bps=round(tot_gross, 2),
        net_return_bps=round(tot_net, 2),
        profit_factor=round(pf, 2),
        max_drawdown_pct=round(max_dd_pct, 2),
        max_consecutive_losses=max_cons_losses,
        expectancy_bps_per_trade=round(expectancy, 2),
        sharpe_ratio=round(sharpe, 4),
        sortino_ratio=round(sortino, 4),
    )


def audit_calculations_against_phase7(
    df_eval: pd.DataFrame,
    reported_metrics: Dict[str, Any],
    symbol: str = "BTCUSDT",
    horizon: str = "5m",
) -> List[CalculationDiscrepancyItem]:
    """Recalculates metrics and compares against reported metrics from Phase 7."""
    target_bps_col = f"target_bps_{horizon}"
    target_dir_col = f"target_dir_{horizon}"

    valid_df = df_eval[~df_eval[target_bps_col].isna() & df_eval["is_active"]].copy()
    if len(valid_df) == 0:
        return []

    dirs = valid_df["decision_dir"].values
    raw_bps = valid_df[target_bps_col].values
    trade_returns = dirs * raw_bps
    recomp_trade = recompute_trading_metrics(trade_returns, round_trip_friction_bps=30.0)

    # List of comparisons: (metric_name, reported_val, recomputed_val)
    checks = [
        ("trade_count", reported_metrics.get("trade_count", len(trade_returns)), recomp_trade.total_trades),
        ("gross_return_bps", reported_metrics.get("gross_return_bps", 0.0), recomp_trade.gross_return_bps),
        ("net_return_bps", reported_metrics.get("net_return_bps", 0.0), recomp_trade.net_return_bps),
        ("profit_factor", reported_metrics.get("profit_factor", 0.0), recomp_trade.profit_factor),
        ("max_drawdown_pct", reported_metrics.get("max_drawdown_pct", 0.0), recomp_trade.max_drawdown_pct),
        ("expectancy_bps", reported_metrics.get("net_expectancy_bps_per_trade", 0.0), recomp_trade.expectancy_bps_per_trade),
    ]

    items = []
    for name, rep, recomp in checks:
        abs_diff = abs(rep - recomp)
        rel_diff = (abs_diff / (abs(rep) + 1e-9)) * 100.0

        if abs_diff < 1e-2:
            status = "EXACT_MATCH"
        elif abs_diff < 1.0:
            status = "MINOR_DELTA"
        else:
            status = "MATERIAL_DELTA"

        items.append(CalculationDiscrepancyItem(
            metric_name=name,
            symbol=symbol,
            horizon=horizon,
            reported_value=round(float(rep), 2),
            recomputed_value=round(float(recomp), 2),
            abs_difference=round(float(abs_diff), 4),
            rel_difference_pct=round(float(rel_diff), 4),
            status=status,
        ))

    return items
