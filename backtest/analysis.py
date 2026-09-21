"""Benchmark Comparisons and Confidence Threshold Sensitivity Analysis.

Provides objective side-by-side numerical comparisons against:
1. Buy & Hold BTC
2. Always HOLD
3. Existing RuleBasedJev Baseline

Evaluates sensitivity across confidence thresholds (0.50 to 0.80) without modifying production settings.
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import pandas as pd

from backtest.dataset import HistoricalDecision, DatasetManager
from backtest.engine import BacktestEngine, BacktestConfig, BacktestResult
from bot.decision import RuleBasedJev


@dataclass
class ThresholdComparisonRow:
    threshold: float
    total_trades: int
    win_rate_pct: float
    profit_factor: float
    total_return_pct: float
    max_drawdown_pct: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "threshold": self.threshold,
            "total_trades": self.total_trades,
            "win_rate_pct": round(self.win_rate_pct, 2),
            "profit_factor": round(self.profit_factor, 4),
            "total_return_pct": round(self.total_return_pct, 4),
            "max_drawdown_pct": round(self.max_drawdown_pct, 4),
        }


@dataclass
class BenchmarkComparison:
    strategy_name: str
    total_return_pct: float
    total_trades: int
    win_rate_pct: float
    profit_factor: float
    max_drawdown_pct: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_name": self.strategy_name,
            "total_return_pct": round(self.total_return_pct, 4),
            "total_trades": self.total_trades,
            "win_rate_pct": round(self.win_rate_pct, 2),
            "profit_factor": round(self.profit_factor, 4),
            "max_drawdown_pct": round(self.max_drawdown_pct, 4),
        }


def run_threshold_sweep(
    candles: pd.DataFrame,
    decisions: List[HistoricalDecision],
    base_config: BacktestConfig,
    thresholds: Optional[List[float]] = None,
) -> List[ThresholdComparisonRow]:
    """Sweeps confidence thresholds from 0.50 to 0.80 to measure impact on trade frequency and performance."""
    if thresholds is None:
        thresholds = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80]

    rows: List[ThresholdComparisonRow] = []

    for th in thresholds:
        cfg = BacktestConfig(
            initial_balance=base_config.initial_balance,
            fee_rate=base_config.fee_rate,
            slippage_rate=base_config.slippage_rate,
            max_risk_per_trade=base_config.max_risk_per_trade,
            max_position_size=base_config.max_position_size,
            max_daily_loss=base_config.max_daily_loss,
            stop_loss_pct=base_config.stop_loss_pct,
            take_profit_pct=base_config.take_profit_pct,
            max_holding_period=base_config.max_holding_period,
            confidence_threshold=th,
        )

        engine = BacktestEngine(cfg)
        res = engine.run(candles, decisions)

        rows.append(
            ThresholdComparisonRow(
                threshold=th,
                total_trades=res.metrics.total_trades,
                win_rate_pct=res.metrics.win_rate_pct,
                profit_factor=res.metrics.profit_factor,
                total_return_pct=res.metrics.total_return_pct,
                max_drawdown_pct=res.metrics.max_drawdown_pct,
            )
        )

    return rows


async def generate_rule_based_decisions(
    enriched_df: pd.DataFrame,
    symbol: str = "BTCUSDT",
    timeframe: str = "5m",
) -> List[HistoricalDecision]:
    """Generates decisions using the production RuleBasedJev baseline."""
    rule_jev = RuleBasedJev()
    decisions: List[HistoricalDecision] = []

    for _, row in enriched_df.iterrows():
        state_dict = {
            "price": float(row["close"]),
            "ema20": float(row.get("ema20", row["close"])),
            "ema50": float(row.get("ema50", row["close"])),
            "ema200": float(row.get("ema200", row["close"])),
            "rsi14": float(row.get("rsi14", 50.0)),
            "atr14": float(row.get("atr14", 0.0)),
            "volume_ratio": float(row.get("volume_ratio", 1.0)),
            "price_change_pct": float(row.get("price_change_pct", 0.0)),
        }

        res = await rule_jev.decide_raw(state_dict)
        decisions.append(
            HistoricalDecision(
                timestamp=int(row["timestamp"]),
                symbol=symbol,
                timeframe=timeframe,
                price=float(row["close"]),
                action=res.get("action", "HOLD"),
                confidence=float(res.get("confidence", 0.5)),
                prob_hold=0.5,
                prob_long=0.25,
                prob_short=0.25,
            )
        )

    return decisions


def run_benchmark_comparisons(
    candles: pd.DataFrame,
    jev_result: BacktestResult,
    rule_based_decisions: Optional[List[HistoricalDecision]] = None,
) -> List[BenchmarkComparison]:
    """Compares Jev backtest against Buy & Hold, Always HOLD, and RuleBasedJev."""
    benchmarks: List[BenchmarkComparison] = []

    # 1. Jev Strategy
    benchmarks.append(
        BenchmarkComparison(
            strategy_name=f"Jev Strategy (th={jev_result.config.confidence_threshold:.2f})",
            total_return_pct=jev_result.metrics.total_return_pct,
            total_trades=jev_result.metrics.total_trades,
            win_rate_pct=jev_result.metrics.win_rate_pct,
            profit_factor=jev_result.metrics.profit_factor,
            max_drawdown_pct=jev_result.metrics.max_drawdown_pct,
        )
    )

    # 2. Buy and Hold BTC
    first_price = float(candles.iloc[0]["open"])
    last_price = float(candles.iloc[-1]["close"])
    bnh_return = ((last_price - first_price) / first_price) * 100.0

    # BnH max drawdown
    peak_p = first_price
    bnh_max_dd = 0.0
    for p in candles["close"]:
        if p > peak_p:
            peak_p = p
        dd = (peak_p - p) / peak_p * 100.0
        if dd > bnh_max_dd:
            bnh_max_dd = dd

    benchmarks.append(
        BenchmarkComparison(
            strategy_name="Buy & Hold BTC",
            total_return_pct=bnh_return,
            total_trades=1,
            win_rate_pct=100.0 if bnh_return > 0 else 0.0,
            profit_factor=999.99 if bnh_return > 0 else 0.0,
            max_drawdown_pct=bnh_max_dd,
        )
    )

    # 3. Always HOLD
    benchmarks.append(
        BenchmarkComparison(
            strategy_name="Always HOLD",
            total_return_pct=0.0,
            total_trades=0,
            win_rate_pct=0.0,
            profit_factor=0.0,
            max_drawdown_pct=0.0,
        )
    )

    # 4. RuleBasedJev baseline
    if rule_based_decisions is not None:
        rb_engine = BacktestEngine(jev_result.config)
        rb_res = rb_engine.run(candles, rule_based_decisions)
        benchmarks.append(
            BenchmarkComparison(
                strategy_name="RuleBasedJev Baseline",
                total_return_pct=rb_res.metrics.total_return_pct,
                total_trades=rb_res.metrics.total_trades,
                win_rate_pct=rb_res.metrics.win_rate_pct,
                profit_factor=rb_res.metrics.profit_factor,
                max_drawdown_pct=rb_res.metrics.max_drawdown_pct,
            )
        )

    return benchmarks
