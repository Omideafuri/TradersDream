"""Exit Parameter Ablation and Premature Termination Diagnostics.

Evaluates how performance varies when individual exit rules are isolated:
1. No SL / No TP (pure fixed 24-bar holding exit)
2. Baseline Composite (SL 1.5% + TP 3.0% + Max Hold 24 bars)
3. Stop-Loss Only (SL 1.5%, no TP)
4. Take-Profit Only (TP 3.0%, no SL)
5. Short Time Exit Only (Max Hold 6 bars / 30 mins)
6. Medium Time Exit Only (Max Hold 12 bars / 1 hour)
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Tuple
import pandas as pd

from backtest.dataset import HistoricalDecision
from backtest.engine import BacktestEngine, BacktestConfig, BacktestResult


@dataclass
class ExitAblationResult:
    config_name: str
    description: str
    stop_loss_pct: float
    take_profit_pct: float
    max_holding_period: int
    total_trades: int
    win_rate_pct: float
    profit_factor: float
    total_return_pct: float
    max_drawdown_pct: float
    avg_holding_bars: float
    exit_breakdown: Dict[str, int]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "config_name": self.config_name,
            "description": self.description,
            "stop_loss_pct": round(self.stop_loss_pct, 4),
            "take_profit_pct": round(self.take_profit_pct, 4),
            "max_holding_period": self.max_holding_period,
            "total_trades": self.total_trades,
            "win_rate_pct": round(self.win_rate_pct, 2),
            "profit_factor": round(self.profit_factor, 4),
            "total_return_pct": round(self.total_return_pct, 4),
            "max_drawdown_pct": round(self.max_drawdown_pct, 4),
            "avg_holding_bars": round(self.avg_holding_bars, 2),
            "exit_breakdown": self.exit_breakdown,
        }


def run_exit_ablation(
    candles_df: pd.DataFrame,
    decisions: List[HistoricalDecision],
    base_config: BacktestConfig,
) -> List[ExitAblationResult]:
    """Runs systematic ablation of exit rules while keeping entry signals identical."""
    experiments = [
        ("no_sl_no_tp", "No SL / No TP (24-bar hold)", 0.0, 0.0, 24),
        ("baseline_composite", "Baseline (SL 1.5% + TP 3.0% + Hold 24)", 0.015, 0.030, 24),
        ("sl_only", "Stop-Loss Only (SL 1.5%, No TP)", 0.015, 0.0, 24),
        ("tp_only", "Take-Profit Only (TP 3.0%, No SL)", 0.0, 0.030, 24),
        ("time_only_6bars", "Time Exit Only: 6 bars (30m)", 0.0, 0.0, 6),
        ("time_only_12bars", "Time Exit Only: 12 bars (1h)", 0.0, 0.0, 12),
    ]

    results: List[ExitAblationResult] = []

    for name, desc, sl, tp, max_hold in experiments:
        cfg = BacktestConfig(
            initial_balance=base_config.initial_balance,
            fee_rate=base_config.fee_rate,
            slippage_rate=base_config.slippage_rate,
            max_risk_per_trade=base_config.max_risk_per_trade,
            max_position_size=base_config.max_position_size,
            max_daily_loss=base_config.max_daily_loss,
            stop_loss_pct=sl,
            take_profit_pct=tp,
            max_holding_period=max_hold,
            confidence_threshold=base_config.confidence_threshold,
        )

        engine = BacktestEngine(cfg)
        res = engine.run(candles_df, decisions)

        # Count exit reasons
        exit_counts: Dict[str, int] = {}
        for t in res.trades:
            exit_counts[t.exit_reason] = exit_counts.get(t.exit_reason, 0) + 1

        avg_bars = (
            sum(t.holding_periods for t in res.trades) / len(res.trades)
            if res.trades
            else 0.0
        )

        results.append(
            ExitAblationResult(
                config_name=name,
                description=desc,
                stop_loss_pct=sl * 100.0,
                take_profit_pct=tp * 100.0,
                max_holding_period=max_hold,
                total_trades=res.metrics.total_trades,
                win_rate_pct=res.metrics.win_rate_pct,
                profit_factor=res.metrics.profit_factor,
                total_return_pct=res.metrics.total_return_pct,
                max_drawdown_pct=res.metrics.max_drawdown_pct,
                avg_holding_bars=avg_bars,
                exit_breakdown=exit_counts,
            )
        )

    return results
