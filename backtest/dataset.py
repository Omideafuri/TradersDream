"""Historical Market Data and Jev Decision Dataset Management.

Ensures zero look-ahead bias when generating technical features.
Provides deterministic loading and generation of candle and Jev decision datasets.
"""

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd

from bot.indicators import calculate_indicators, build_market_state, MarketState


@dataclass(frozen=True)
class HistoricalDecision:
    timestamp: int
    symbol: str
    timeframe: str
    price: float
    action: str  # LONG, SHORT, HOLD
    confidence: float
    prob_hold: float
    prob_long: float
    prob_short: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "price": round(self.price, 2),
            "action": self.action,
            "confidence": round(self.confidence, 4),
            "prob_hold": round(self.prob_hold, 4),
            "prob_long": round(self.prob_long, 4),
            "prob_short": round(self.prob_short, 4),
        }


class DatasetManager:
    """Manages historical OHLCV data and offline Jev decision datasets."""

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or (Path(__file__).parent.parent / "data" / "historical")
        self.data_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def compute_causal_indicators(df: pd.DataFrame) -> pd.DataFrame:
        """Computes technical indicators ensuring strictly causal (no look-ahead) evaluation.
        
        Indicators at index t use exclusively rows 0 through t.
        """
        if not {"open", "high", "low", "close", "volume"}.issubset(df.columns):
            raise ValueError("DataFrame must contain OHLCV columns")

        # calculate_indicators uses expanding EWM and rolling windows without future shifting
        enriched = calculate_indicators(df)
        return enriched

    @staticmethod
    def generate_synthetic_history(
        count: int = 1500,
        start_price: float = 65000.0,
        interval_minutes: int = 5,
        seed: int = 42,
    ) -> pd.DataFrame:
        """Generates realistic 5-minute candle history for offline benchmarking and reproducibility."""
        rng = np.random.default_rng(seed)
        interval_ms = interval_minutes * 60 * 1000
        # Start 2 weeks prior
        start_ts = 1704067200000  # 2024-01-01 00:00:00 UTC

        rows = []
        curr_price = start_price
        for i in range(count):
            # Market regime: drift + volatility clustering
            trend = 0.00015 * np.sin(i / 100.0)
            noise = rng.normal(0, 0.0035)
            ret = trend + noise
            open_p = curr_price
            close_p = open_p * (1.0 + ret)
            high_p = max(open_p, close_p) * (1.0 + abs(rng.normal(0.001, 0.0015)))
            low_p = min(open_p, close_p) * (1.0 - abs(rng.normal(0.001, 0.0015)))
            vol = float(rng.uniform(15.0, 120.0)) * (1.5 if abs(ret) > 0.005 else 1.0)

            rows.append({
                "timestamp": start_ts + i * interval_ms,
                "open": round(open_p, 2),
                "high": round(high_p, 2),
                "low": round(low_p, 2),
                "close": round(close_p, 2),
                "volume": round(vol, 4),
            })
            curr_price = close_p

        df = pd.DataFrame(rows)
        df.sort_values("timestamp", inplace=True)
        df.reset_index(drop=True, inplace=True)
        return df

    @staticmethod
    def generate_simulated_decisions(
        enriched_df: pd.DataFrame,
        symbol: str = "BTCUSDT",
        timeframe: str = "5m",
        seed: int = 123,
    ) -> List[HistoricalDecision]:
        """Generates deterministic Jev-style decision stream based on indicators without live API costs.
        
        Calculates probabilities (prob_hold, prob_long, prob_short) and assigns action & confidence.
        """
        rng = np.random.default_rng(seed)
        decisions: List[HistoricalDecision] = []

        for idx, row in enriched_df.iterrows():
            price = float(row["close"])
            ema20 = float(row.get("ema20", price))
            ema50 = float(row.get("ema50", price))
            rsi14 = float(row.get("rsi14", 50.0))
            vol_ratio = float(row.get("volume_ratio", 1.0))

            # Base probabilities derived from momentum and indicator alignment
            bull_score = 0.0
            bear_score = 0.0

            if price > ema20 > ema50:
                bull_score += 0.8
                hold_score = 0.2
            elif price < ema20 < ema50:
                bear_score += 0.8
                hold_score = 0.2
            else:
                hold_score = 0.7

            if rsi14 < 35:
                bull_score += 0.6  # oversold bounce
            elif rsi14 > 65:
                bear_score += 0.6  # overbought drop

            if vol_ratio > 1.2:
                bull_score *= 1.25
                bear_score *= 1.25

            # Add mild variance
            bull_score += float(rng.uniform(0.0, 0.15))
            bear_score += float(rng.uniform(0.0, 0.15))
            hold_score += float(rng.uniform(0.0, 0.15))

            total = bull_score + bear_score + hold_score
            p_long = bull_score / total
            p_short = bear_score / total
            p_hold = hold_score / total

            # Determine dominant choice
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
                    symbol=symbol,
                    timeframe=timeframe,
                    price=price,
                    action=action,
                    confidence=confidence,
                    prob_hold=p_hold,
                    prob_long=p_long,
                    prob_short=p_short,
                )
            )

        return decisions

    def save_decisions_csv(self, decisions: List[HistoricalDecision], filepath: Path) -> None:
        """Saves decisions to CSV."""
        data = [d.to_dict() for d in decisions]
        df = pd.DataFrame(data)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(filepath, index=False)

    def load_decisions_csv(self, filepath: Path) -> List[HistoricalDecision]:
        """Loads decisions from CSV."""
        df = pd.read_csv(filepath)
        decisions = []
        for _, row in df.iterrows():
            decisions.append(
                HistoricalDecision(
                    timestamp=int(row["timestamp"]),
                    symbol=str(row["symbol"]),
                    timeframe=str(row["timeframe"]),
                    price=float(row["price"]),
                    action=str(row["action"]),
                    confidence=float(row["confidence"]),
                    prob_hold=float(row["prob_hold"]),
                    prob_long=float(row["prob_long"]),
                    prob_short=float(row["prob_short"]),
                )
            )
        return decisions
