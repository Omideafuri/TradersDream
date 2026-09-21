"""Causal Market Regime Classification and Performance Analysis.

Classifies historical market conditions exclusively using causal indicators available at or before timestamp T:
1. Trending Up: Price > EMA50 and EMA20 > EMA50
2. Trending Down: Price < EMA50 and EMA20 < EMA50
3. Sideways: Neither Trending Up nor Trending Down
4. High Volatility: ATR14 > rolling 20-period median of ATR14
5. Low Volatility: ATR14 <= rolling 20-period median of ATR14
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Tuple
import numpy as np
import pandas as pd

from backtest.dataset import HistoricalDecision
from backtest.engine import BacktestEngine, BacktestConfig, BacktestResult


@dataclass
class RegimePerformance:
    regime_name: str
    observation_count: int
    trade_count: int
    directional_accuracy_pct: float
    mean_forward_return_pct: float  # 15m
    strategy_return_pct: float
    profit_factor: float
    max_drawdown_pct: float
    avg_holding_periods: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "regime_name": self.regime_name,
            "observation_count": self.observation_count,
            "trade_count": self.trade_count,
            "directional_accuracy_pct": round(self.directional_accuracy_pct, 2),
            "mean_forward_return_pct": round(self.mean_forward_return_pct, 4),
            "strategy_return_pct": round(self.strategy_return_pct, 4),
            "profit_factor": round(self.profit_factor, 4),
            "max_drawdown_pct": round(self.max_drawdown_pct, 4),
            "avg_holding_periods": round(self.avg_holding_periods, 2),
        }


def classify_causal_regimes(enriched_df: pd.DataFrame) -> pd.DataFrame:
    """Classifies each candle into trend and volatility regimes causally."""
    df = enriched_df.copy()
    if "ema20" not in df.columns:
        from backtest.dataset import DatasetManager
        df = DatasetManager.compute_causal_indicators(df)

    price = df["close"]
    ema20 = df["ema20"]
    ema50 = df["ema50"]
    atr = df["atr14"]

    # Rolling 20-period median of ATR (strictly backwards looking)
    atr_median = atr.rolling(window=20, min_periods=1).median()

    trend_regime = []
    vol_regime = []

    for p, e20, e50, a, a_med in zip(price, ema20, ema50, atr, atr_median):
        # Trend
        if p > e50 and e20 > e50:
            trend_regime.append("Trending Up")
        elif p < e50 and e20 < e50:
            trend_regime.append("Trending Down")
        else:
            trend_regime.append("Sideways")

        # Volatility
        if a > a_med:
            vol_regime.append("High Volatility")
        else:
            vol_regime.append("Low Volatility")

    df["trend_regime"] = trend_regime
    df["vol_regime"] = vol_regime
    return df


def evaluate_regime_performance(
    classified_df: pd.DataFrame,
    decisions: List[HistoricalDecision],
    config: BacktestConfig,
    horizon_return_col: str = "fwd_ret_15m",
) -> List[RegimePerformance]:
    """Measures predictive accuracy and strategy outcomes across distinct causal regimes."""
    ts_to_trend = dict(zip(classified_df["timestamp"], classified_df["trend_regime"]))
    ts_to_vol = dict(zip(classified_df["timestamp"], classified_df["vol_regime"]))

    # Match decisions with regime
    regime_groups = ["Trending Up", "Trending Down", "Sideways", "High Volatility", "Low Volatility"]
    results: List[RegimePerformance] = []

    engine = BacktestEngine(config)
    full_result = engine.run(classified_df, decisions)

    # Map trades to entry timestamp regime
    trade_map = {t.entry_time: t for t in full_result.trades}

    for regime in regime_groups:
        # Determine which timestamps match
        if regime in ("Trending Up", "Trending Down", "Sideways"):
            matched_ts = {ts for ts, r in ts_to_trend.items() if r == regime}
        else:
            matched_ts = {ts for ts, r in ts_to_vol.items() if r == regime}

        sub_candles = classified_df[classified_df["timestamp"].isin(matched_ts)]
        sub_decisions = [d for d in decisions if d.timestamp in matched_ts]
        sub_trades = [t for ts, t in trade_map.items() if ts in matched_ts]

        obs_count = len(sub_candles)
        trade_count = len(sub_trades)

        # Directional accuracy on trades
        if trade_count > 0:
            wins = sum(1 for t in sub_trades if t.net_pnl > 0)
            acc = (wins / trade_count) * 100.0
            tot_pnl = sum(t.net_pnl for t in sub_trades)
            strat_ret = (tot_pnl / config.initial_balance) * 100.0
            gross_win = sum(t.net_pnl for t in sub_trades if t.net_pnl > 0)
            gross_loss = abs(sum(t.net_pnl for t in sub_trades if t.net_pnl < 0))
            pf = (gross_win / gross_loss) if gross_loss > 0 else (999.99 if gross_win > 0 else 0.0)
            avg_hold = float(np.mean([t.holding_periods for t in sub_trades]))
        else:
            acc = 0.0
            strat_ret = 0.0
            pf = 0.0
            avg_hold = 0.0

        # Mean forward return of active decisions
        active_fwd = []
        # Calculate forward price return for decisions in this regime
        price_map = dict(zip(classified_df["timestamp"], classified_df["close"]))
        ts_list = classified_df["timestamp"].tolist()
        idx_map = {ts: i for i, ts in enumerate(ts_list)}

        for d in sub_decisions:
            if d.action in ("LONG", "SHORT") and d.timestamp in idx_map:
                curr_idx = idx_map[d.timestamp]
                offset_idx = curr_idx + 3  # 15m = 3 bars
                if offset_idx < len(ts_list):
                    fut_p = price_map[ts_list[offset_idx]]
                    if d.action == "LONG":
                        ret = (fut_p / d.price) - 1.0
                    else:
                        ret = (d.price / fut_p) - 1.0
                    active_fwd.append(ret * 100.0)

        mean_fwd = float(np.mean(active_fwd)) if active_fwd else 0.0

        results.append(
            RegimePerformance(
                regime_name=regime,
                observation_count=obs_count,
                trade_count=trade_count,
                directional_accuracy_pct=acc,
                mean_forward_return_pct=mean_fwd,
                strategy_return_pct=strat_ret,
                profit_factor=pf,
                max_drawdown_pct=0.0,  # Segmented drawdown
                avg_holding_periods=avg_hold,
            )
        )

    return results
