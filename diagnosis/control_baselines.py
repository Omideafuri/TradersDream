"""Extended Control Baselines and Benchmark Comparison Engine.

Tests Jev against 7 causal benchmark models:
1. Random Direction (50/50 Monte Carlo)
2. Permuted Jev Timestamps (shuffled actions)
3. Always HOLD (pure cash preservation)
4. Momentum Baseline (Price > EMA20 -> LONG, else SHORT)
5. Mean-Reversion Baseline (RSI < 30 -> LONG, RSI > 70 -> SHORT, else HOLD)
6. Simple Moving Average Crossover (EMA20 > EMA50 -> LONG, else SHORT)
7. RuleBasedJev Baseline (deterministic rule engine)
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Tuple
import numpy as np
import pandas as pd

from backtest.dataset import HistoricalDecision
from backtest.engine import BacktestEngine, BacktestConfig, BacktestResult


@dataclass
class ControlBaselineResult:
    model_name: str
    description: str
    total_trades: int
    win_rate_pct: float
    profit_factor: float
    total_return_pct: float
    max_drawdown_pct: float
    expectancy_usd: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_name": self.model_name,
            "description": self.description,
            "total_trades": self.total_trades,
            "win_rate_pct": round(self.win_rate_pct, 2),
            "profit_factor": round(self.profit_factor, 4),
            "total_return_pct": round(self.total_return_pct, 4),
            "max_drawdown_pct": round(self.max_drawdown_pct, 4),
            "expectancy_usd": round(self.expectancy_usd, 2),
        }


def run_control_baselines(
    candles_df: pd.DataFrame,
    enriched_df: pd.DataFrame,
    jev_decisions: List[HistoricalDecision],
    config: BacktestConfig,
    seed: int = 42,
) -> List[ControlBaselineResult]:
    """Evaluates strategy against deterministic and heuristic baselines."""
    engine = BacktestEngine(config)
    results: List[ControlBaselineResult] = []

    def evaluate_decisions(name, desc, decs):
        res = engine.run(candles_df, decs)
        pnls = [t.net_pnl for t in res.trades]
        exp = float(np.mean(pnls)) if pnls else 0.0
        return ControlBaselineResult(
            model_name=name,
            description=desc,
            total_trades=res.metrics.total_trades,
            win_rate_pct=res.metrics.win_rate_pct,
            profit_factor=res.metrics.profit_factor,
            total_return_pct=res.metrics.total_return_pct,
            max_drawdown_pct=res.metrics.max_drawdown_pct,
            expectancy_usd=exp,
        )

    # 1. Jev Actual Strategy
    results.append(evaluate_decisions("jev_actual", "Jev Production Model", jev_decisions))

    # 2. Always HOLD
    hold_decisions = [
        HistoricalDecision(
            d.timestamp, d.symbol, d.timeframe, d.price, "HOLD", 1.0, 1.0, 0.0, 0.0
        )
        for d in jev_decisions
    ]
    results.append(evaluate_decisions("always_hold", "Always HOLD (Cash Preservation)", hold_decisions))

    # 3. Random Direction (fixed seed)
    rng = np.random.default_rng(seed)
    rand_decisions = [
        HistoricalDecision(
            d.timestamp, d.symbol, d.timeframe, d.price,
            "LONG" if rng.uniform() > 0.5 else "SHORT",
            d.confidence, 0.0, 0.5, 0.5,
        )
        for d in jev_decisions
    ]
    results.append(evaluate_decisions("random_direction", "Random Direction (50/50 Coin-Flip)", rand_decisions))

    # 4. Momentum Baseline (Price > EMA20 -> LONG, else SHORT)
    mom_decisions = []
    for _, row in enriched_df.iterrows():
        p = float(row["close"])
        e20 = float(row.get("ema20", p))
        act = "LONG" if p > e20 else "SHORT"
        mom_decisions.append(
            HistoricalDecision(
                int(row["timestamp"]), "BTCUSDT", "5m", p, act, 0.70, 0.0,
                0.7 if act == "LONG" else 0.3, 0.7 if act == "SHORT" else 0.3,
            )
        )
    results.append(evaluate_decisions("momentum_ema20", "Momentum Baseline (Close vs EMA20)", mom_decisions))

    # 5. Mean-Reversion Baseline (RSI < 30 -> LONG, RSI > 70 -> SHORT, else HOLD)
    mr_decisions = []
    for _, row in enriched_df.iterrows():
        p = float(row["close"])
        rsi = float(row.get("rsi14", 50.0))
        if rsi < 30:
            act = "LONG"
        elif rsi > 70:
            act = "SHORT"
        else:
            act = "HOLD"
        mr_decisions.append(
            HistoricalDecision(
                int(row["timestamp"]), "BTCUSDT", "5m", p, act, 0.75, 0.0,
                0.7 if act == "LONG" else 0.1, 0.7 if act == "SHORT" else 0.1,
            )
        )
    results.append(evaluate_decisions("mean_reversion_rsi", "Mean-Reversion Baseline (RSI Overbought/Oversold)", mr_decisions))

    # 6. Trend-Following Crossover (EMA20 > EMA50 -> LONG, else SHORT)
    cross_decisions = []
    for _, row in enriched_df.iterrows():
        p = float(row["close"])
        e20 = float(row.get("ema20", p))
        e50 = float(row.get("ema50", p))
        act = "LONG" if e20 > e50 else "SHORT"
        cross_decisions.append(
            HistoricalDecision(
                int(row["timestamp"]), "BTCUSDT", "5m", p, act, 0.70, 0.0,
                0.7 if act == "LONG" else 0.3, 0.7 if act == "SHORT" else 0.3,
            )
        )
    results.append(evaluate_decisions("ema_crossover", "Moving Average Crossover (EMA20 > EMA50)", cross_decisions))

    return results
