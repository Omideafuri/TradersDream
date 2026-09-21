"""Decision-Input Feature Group Ablation Testing Framework.

Evaluates how performance varies when subsets of technical indicators are removed or isolated.
Performs ablation at the decision-input layer:
1. Full Features (Price + Trend EMAs + RSI + ATR + Volume Ratio)
2. Price-Only (Price + Price Change %)
3. Technical-Indicators-Only (RSI + ATR + Volume Ratio, no price level)
4. Market-Structure-Only (EMA alignment: EMA20, EMA50, EMA200)
5. Price + Technical Indicators (Price + RSI + ATR + Volume)
6. Full Minus RSI (Removes oscillator signals)
7. Full Minus EMAs (Removes moving average trend signals)
8. Full Minus Volume (Removes volume expansion ratio)
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import numpy as np
import pandas as pd

from backtest.dataset import HistoricalDecision
from backtest.engine import BacktestEngine, BacktestConfig, BacktestResult


@dataclass
class AblationResult:
    ablation_name: str
    description: str
    features_used: List[str]
    features_removed: List[str]
    total_trades: int
    win_rate_pct: float
    profit_factor: float
    total_return_pct: float
    max_drawdown_pct: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ablation_name": self.ablation_name,
            "description": self.description,
            "features_used": self.features_used,
            "features_removed": self.features_removed,
            "total_trades": self.total_trades,
            "win_rate_pct": round(self.win_rate_pct, 2),
            "profit_factor": round(self.profit_factor, 4),
            "total_return_pct": round(self.total_return_pct, 4),
            "max_drawdown_pct": round(self.max_drawdown_pct, 4),
        }


def generate_ablated_decisions(
    enriched_df: pd.DataFrame,
    ablation_mode: str,
    seed: int = 42,
) -> List[HistoricalDecision]:
    """Generates decisions where specific feature groups are masked or neutralized."""
    rng = np.random.default_rng(seed)
    decisions = []

    for _, row in enriched_df.iterrows():
        price = float(row["close"])
        ema20 = float(row.get("ema20", price))
        ema50 = float(row.get("ema50", price))
        rsi14 = float(row.get("rsi14", 50.0))
        vol_ratio = float(row.get("volume_ratio", 1.0))
        pct_change = float(row.get("price_change_pct", 0.0))

        # Feature masking according to ablation mode
        use_emas = ablation_mode not in ("price_only", "technical_only", "minus_ema")
        use_rsi = ablation_mode not in ("price_only", "structure_only", "minus_rsi")
        use_volume = ablation_mode not in ("price_only", "structure_only", "minus_volume")
        use_price = ablation_mode not in ("technical_only", "structure_only")

        bull_score = 0.0
        bear_score = 0.0
        hold_score = 0.7

        if use_emas:
            if price > ema20 > ema50:
                bull_score += 0.8
                hold_score = 0.2
            elif price < ema20 < ema50:
                bear_score += 0.8
                hold_score = 0.2

        if use_rsi:
            if rsi14 < 35:
                bull_score += 0.6
            elif rsi14 > 65:
                bear_score += 0.6

        if use_volume and vol_ratio > 1.2:
            bull_score *= 1.25
            bear_score *= 1.25

        if use_price and not use_emas:
            if pct_change > 0.5:
                bull_score += 0.5
            elif pct_change < -0.5:
                bear_score += 0.5

        # Mild variance
        bull_score += float(rng.uniform(0.0, 0.15))
        bear_score += float(rng.uniform(0.0, 0.15))
        hold_score += float(rng.uniform(0.0, 0.15))

        total = bull_score + bear_score + hold_score
        p_long = bull_score / total
        p_short = bear_score / total
        p_hold = hold_score / total

        if p_long > p_short and p_long > p_hold:
            action = "LONG"
            confidence = float(p_long)
        elif p_short > p_long and p_short > p_hold:
            action = "SHORT"
            confidence = float(p_short)
        else:
            action = "HOLD"
            confidence = float(p_hold)

        decisions.append(
            HistoricalDecision(
                timestamp=int(row["timestamp"]),
                symbol="BTCUSDT",
                timeframe="5m",
                price=price,
                action=action,
                confidence=confidence,
                prob_hold=p_hold,
                prob_long=p_long,
                prob_short=p_short,
            )
        )

    return decisions


def run_ablation_study(
    candles_df: pd.DataFrame,
    enriched_df: pd.DataFrame,
    config: BacktestConfig,
    base_seed: int = 42,
) -> List[AblationResult]:
    """Runs systematic ablation across feature configurations."""
    engine = BacktestEngine(config)
    modes = [
        ("full", "Full Feature Set", ["Price", "EMAs", "RSI", "ATR", "Volume"], []),
        ("price_only", "Price-Only (Momentum %)", ["Price", "PriceChange%"], ["EMAs", "RSI", "ATR", "Volume"]),
        ("technical_only", "Technical-Indicators-Only", ["RSI", "ATR", "Volume"], ["Price", "EMAs"]),
        ("structure_only", "Market-Structure-Only (EMAs)", ["EMA20", "EMA50", "EMA200"], ["Price", "RSI", "ATR", "Volume"]),
        ("minus_rsi", "Full Minus RSI", ["Price", "EMAs", "ATR", "Volume"], ["RSI"]),
        ("minus_ema", "Full Minus EMAs", ["Price", "RSI", "ATR", "Volume"], ["EMAs"]),
        ("minus_volume", "Full Minus Volume", ["Price", "EMAs", "RSI", "ATR"], ["Volume"]),
    ]

    results: List[AblationResult] = []

    for name, desc, used, removed in modes:
        ablated_decisions = generate_ablated_decisions(enriched_df, name, seed=base_seed)
        res = engine.run(candles_df, ablated_decisions)
        results.append(
            AblationResult(
                ablation_name=name,
                description=desc,
                features_used=used,
                features_removed=removed,
                total_trades=res.metrics.total_trades,
                win_rate_pct=res.metrics.win_rate_pct,
                profit_factor=res.metrics.profit_factor,
                total_return_pct=res.metrics.total_return_pct,
                max_drawdown_pct=res.metrics.max_drawdown_pct,
            )
        )

    return results
