"""Execution Cost Sensitivity Testing Module.

Evaluates how performance responds to varying levels of exchange fees and execution slippage:
- Scenario A: 0.00% fee / 0.00% slippage (Frictionless Ideal)
- Scenario B: 0.05% fee / 0.02% slippage (Low-Cost Tier)
- Scenario C: 0.10% fee / 0.05% slippage (Standard Base Case)
- Scenario D: 0.15% fee / 0.10% slippage (Elevated Cost)
- Scenario E: 0.20% fee / 0.15% slippage (Adverse Execution)
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Tuple
import pandas as pd

from backtest.dataset import HistoricalDecision
from backtest.engine import BacktestEngine, BacktestConfig, BacktestResult
from validation.statistical import calculate_expectancy


@dataclass
class CostScenarioResult:
    scenario_id: str
    description: str
    fee_rate_pct: float
    slippage_rate_pct: float
    total_trades: int
    total_return_pct: float
    expectancy_usd: float
    win_rate_pct: float
    profit_factor: float
    max_drawdown_pct: float
    total_fees_paid: float
    total_slippage_cost: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "description": self.description,
            "fee_rate_pct": round(self.fee_rate_pct, 4),
            "slippage_rate_pct": round(self.slippage_rate_pct, 4),
            "total_trades": self.total_trades,
            "total_return_pct": round(self.total_return_pct, 4),
            "expectancy_usd": round(self.expectancy_usd, 2),
            "win_rate_pct": round(self.win_rate_pct, 2),
            "profit_factor": round(self.profit_factor, 4),
            "max_drawdown_pct": round(self.max_drawdown_pct, 4),
            "total_fees_paid": round(self.total_fees_paid, 2),
            "total_slippage_cost": round(self.total_slippage_cost, 2),
        }


def run_cost_sensitivity_analysis(
    candles_df: pd.DataFrame,
    decisions: List[HistoricalDecision],
    base_config: BacktestConfig,
) -> List[CostScenarioResult]:
    """Evaluates strategy across Scenarios A through E."""
    scenarios = [
        ("A", "Frictionless Ideal", 0.0000, 0.0000),
        ("B", "Low-Cost Tier", 0.0005, 0.0002),
        ("C", "Standard Base Case", 0.0010, 0.0005),
        ("D", "Elevated Cost", 0.0015, 0.0010),
        ("E", "Adverse Execution", 0.0020, 0.0015),
    ]

    results: List[CostScenarioResult] = []

    for sid, desc, fee, slip in scenarios:
        cfg = BacktestConfig(
            initial_balance=base_config.initial_balance,
            fee_rate=fee,
            slippage_rate=slip,
            max_risk_per_trade=base_config.max_risk_per_trade,
            max_position_size=base_config.max_position_size,
            max_daily_loss=base_config.max_daily_loss,
            stop_loss_pct=base_config.stop_loss_pct,
            take_profit_pct=base_config.take_profit_pct,
            max_holding_period=base_config.max_holding_period,
            confidence_threshold=base_config.confidence_threshold,
        )

        engine = BacktestEngine(cfg)
        res = engine.run(candles_df, decisions)

        net_pnls = [t.net_pnl for t in res.trades]
        exp_data = calculate_expectancy(net_pnls)

        results.append(
            CostScenarioResult(
                scenario_id=sid,
                description=desc,
                fee_rate_pct=fee * 100.0,
                slippage_rate_pct=slip * 100.0,
                total_trades=res.metrics.total_trades,
                total_return_pct=res.metrics.total_return_pct,
                expectancy_usd=exp_data["expectancy"],
                win_rate_pct=res.metrics.win_rate_pct,
                profit_factor=res.metrics.profit_factor,
                max_drawdown_pct=res.metrics.max_drawdown_pct,
                total_fees_paid=res.metrics.total_fees,
                total_slippage_cost=res.metrics.total_slippage,
            )
        )

    return results
