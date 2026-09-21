"""Deterministic technical indicators and MarketState module for Crypto Trading Bot.

Calculates EMA (20, 50, 200), RSI 14 (Wilder's), ATR 14, Volume Moving Average,
and produces structured, JSON-serializable MarketState objects.
"""

from dataclasses import asdict, dataclass
import json
from typing import Dict, Any, Optional
import numpy as np
import pandas as pd


@dataclass(frozen=True)
class MarketState:
    """Structured, immutable, JSON-serializable market state snapshot."""
    symbol: str
    price: float
    ema20: float
    ema50: float
    ema200: float
    rsi14: float
    atr14: float
    volume_ratio: float
    price_change_pct: float
    timestamp: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Converts MarketState to a clean dictionary matching Phase 1 specs."""
        return {
            "symbol": self.symbol,
            "price": round(self.price, 2),
            "ema20": round(self.ema20, 2),
            "ema50": round(self.ema50, 2),
            "ema200": round(self.ema200, 2),
            "rsi14": round(self.rsi14, 2),
            "atr14": round(self.atr14, 2),
            "volume_ratio": round(self.volume_ratio, 2),
            "price_change_pct": round(self.price_change_pct, 4),
            "timestamp": self.timestamp,
        }

    def to_json(self) -> str:
        """Returns valid JSON string representation."""
        return json.dumps(self.to_dict())


def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    """Calculates Exponential Moving Average (EMA) deterministically."""
    if len(series) == 0:
        return pd.Series(dtype=float)
    return series.ewm(span=period, adjust=False).mean()


def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Calculates Wilder's Relative Strength Index (RSI).
    
    Uses standard Wilder's smoothing (alpha = 1 / period).
    Clamped strictly to [0.0, 100.0].
    """
    if len(series) < period:
        return pd.Series(np.nan, index=series.index)

    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)

    # Wilder's exponential smoothing
    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))

    # Boundary conditions: if loss is 0, RSI is 100; if gain is 0, RSI is 0
    rsi = rsi.where(avg_loss != 0.0, 100.0)
    rsi = rsi.where(avg_gain != 0.0, 0.0)
    return rsi.clip(lower=0.0, upper=100.0)


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculates Average True Range (ATR) using Wilder's smoothing."""
    if len(df) < 2:
        return pd.Series(np.nan, index=df.index)

    high = df["high"]
    low = df["low"]
    prev_close = df["close"].shift(1)

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()

    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = true_range.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    return atr


def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Computes all required Phase 1 indicators and returns an enriched DataFrame."""
    if not {"open", "high", "low", "close", "volume"}.issubset(df.columns):
        raise ValueError("DataFrame must contain OHLCV columns")

    enriched = df.copy()

    # EMAs
    enriched["ema20"] = calculate_ema(enriched["close"], 20)
    enriched["ema50"] = calculate_ema(enriched["close"], 50)
    enriched["ema200"] = calculate_ema(enriched["close"], 200)

    # RSI 14
    enriched["rsi14"] = calculate_rsi(enriched["close"], 14)

    # ATR 14
    enriched["atr14"] = calculate_atr(enriched, 14)

    # Volume Moving Average (SMA 20) & Volume Ratio
    enriched["volume_ma20"] = enriched["volume"].rolling(window=20, min_periods=1).mean()
    enriched["volume_ratio"] = enriched["volume"] / enriched["volume_ma20"].replace(0.0, np.nan)
    enriched["volume_ratio"] = enriched["volume_ratio"].fillna(1.0)

    # Percentage price change (vs previous close)
    enriched["price_change_pct"] = enriched["close"].pct_change().fillna(0.0) * 100.0

    return enriched


def build_market_state(enriched_df: pd.DataFrame, symbol: str = "BTCUSDT") -> MarketState:
    """Extracts the latest row from enriched DataFrame and constructs a MarketState object."""
    if enriched_df.empty:
        raise ValueError("Cannot build MarketState from empty DataFrame")

    latest = enriched_df.iloc[-1]

    return MarketState(
        symbol=symbol,
        price=float(latest["close"]),
        ema20=float(latest.get("ema20", latest["close"])),
        ema50=float(latest.get("ema50", latest["close"])),
        ema200=float(latest.get("ema200", latest["close"])),
        rsi14=float(latest.get("rsi14", 50.0)),
        atr14=float(latest.get("atr14", 0.0)),
        volume_ratio=float(latest.get("volume_ratio", 1.0)),
        price_change_pct=float(latest.get("price_change_pct", 0.0)),
        timestamp=int(latest["timestamp"]) if "timestamp" in latest else None,
    )
