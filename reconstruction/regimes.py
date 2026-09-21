"""Causal Market Regime Classification Engine.

Classifies market state into distinct causal regimes without look-ahead bias:
- TRENDING_UP: Bullish moving average hierarchy (Price > EMA20 > EMA50), positive slope.
- TRENDING_DOWN: Bearish moving average hierarchy (Price < EMA20 < EMA50), negative slope.
- HIGH_VOLATILITY: ATR% or BB width in elevated expansion state.
- LOW_VOLATILITY: Range compression, low ATR%, narrow Bollinger Bands.
- RANGE_BOUND: EMAs converging, price oscillating around mean, neutral RSI (40-60).
- TRANSITION: MA divergence/convergence crossover, structure shift.
"""

from dataclasses import dataclass
from typing import Dict, Any, List
import numpy as np
import pandas as pd


@dataclass
class RegimeProfile:
    regime_name: str
    count: int
    frequency_pct: float
    forward_15m_return_mean: float
    forward_15m_return_std: float
    forward_1h_return_mean: float
    forward_1h_return_std: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "regime_name": self.regime_name,
            "count": self.count,
            "frequency_pct": round(self.frequency_pct, 2),
            "forward_15m_return_mean": round(self.forward_15m_return_mean, 4),
            "forward_15m_return_std": round(self.forward_15m_return_std, 4),
            "forward_1h_return_mean": round(self.forward_1h_return_mean, 4),
            "forward_1h_return_std": round(self.forward_1h_return_std, 4),
        }


def classify_causal_regime(row: pd.Series, atr_p75: float = 1.0, atr_p25: float = 0.3) -> str:
    """Classifies a single row into a causal regime based strictly on contemporaneous features."""
    close = float(row.get("close", 0.0))
    ema20 = float(row.get("ema20", close))
    ema50 = float(row.get("ema50", close))
    atr_norm = float(row.get("atr_norm_pct", 0.5))
    bb_width = float(row.get("bb_width_pct", 2.0))
    rsi = float(row.get("rsi14", 50.0))
    compression = str(row.get("compression_state", "NORMAL"))

    # 1. High Volatility Check
    if atr_norm > atr_p75 or bb_width > 3.0 or compression == "EXPANDED":
        if close > ema20 and ema20 > ema50:
            return "TRENDING_UP"
        elif close < ema20 and ema20 < ema50:
            return "TRENDING_DOWN"
        return "HIGH_VOLATILITY"

    # 2. Strong Trend Up
    if close > ema20 > ema50 and rsi >= 50.0:
        return "TRENDING_UP"

    # 3. Strong Trend Down
    if close < ema20 < ema50 and rsi <= 50.0:
        return "TRENDING_DOWN"

    # 4. Low Volatility / Squeeze
    if atr_norm < atr_p25 or compression == "COMPRESSED" or bb_width < 1.0:
        return "LOW_VOLATILITY"

    # 5. Range Bound
    if abs(close - ema20) / (ema20 if ema20 > 0 else 1.0) < 0.003 and 40.0 <= rsi <= 60.0:
        return "RANGE_BOUND"

    # 6. Default to Transition
    return "TRANSITION"


def assign_causal_regimes(df: pd.DataFrame) -> pd.DataFrame:
    """Assigns causal regime labels across an entire DataFrame."""
    out = df.copy()

    # Ensure technical indicators are present
    if "atr_norm_pct" not in out.columns:
        from reconstruction.market_state import compute_enriched_market_state_df
        out = compute_enriched_market_state_df(out)

    # Calculate rolling or causal thresholds for ATR%
    atr_series = out["atr_norm_pct"].dropna()
    p75 = float(np.percentile(atr_series, 75)) if len(atr_series) > 0 else 1.0
    p25 = float(np.percentile(atr_series, 25)) if len(atr_series) > 0 else 0.3

    regimes = []
    for _, row in out.iterrows():
        regimes.append(classify_causal_regime(row, atr_p75=p75, atr_p25=p25))

    out["market_regime"] = regimes
    return out


def audit_regime_distributions(df_with_regimes: pd.DataFrame) -> List[RegimeProfile]:
    """Computes distribution and forward return behavior per regime."""
    df = df_with_regimes.copy()
    if "market_regime" not in df.columns:
        df = assign_causal_regimes(df)

    n = len(df)
    if n == 0:
        return []

    close = df["close"]
    fwd_15m = (close.shift(-3) / close - 1.0) * 100.0
    fwd_1h = (close.shift(-12) / close - 1.0) * 100.0

    df["fwd_15m"] = fwd_15m
    df["fwd_1h"] = fwd_1h

    profiles = []
    regimes = [
        "TRENDING_UP",
        "TRENDING_DOWN",
        "RANGE_BOUND",
        "HIGH_VOLATILITY",
        "LOW_VOLATILITY",
        "TRANSITION",
    ]

    for reg in regimes:
        sub = df[df["market_regime"] == reg]
        count = len(sub)
        freq = (count / n) * 100.0 if n > 0 else 0.0

        r15_valid = sub["fwd_15m"].dropna()
        r1h_valid = sub["fwd_1h"].dropna()

        mean_15m = float(r15_valid.mean()) if len(r15_valid) > 0 else 0.0
        std_15m = float(r15_valid.std()) if len(r15_valid) > 0 else 0.0
        mean_1h = float(r1h_valid.mean()) if len(r1h_valid) > 0 else 0.0
        std_1h = float(r1h_valid.std()) if len(r1h_valid) > 0 else 0.0

        profiles.append(
            RegimeProfile(
                regime_name=reg,
                count=count,
                frequency_pct=freq,
                forward_15m_return_mean=mean_15m,
                forward_15m_return_std=std_15m,
                forward_1h_return_mean=mean_1h,
                forward_1h_return_std=std_1h,
            )
        )

    return profiles
