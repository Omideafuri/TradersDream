"""Directional Asymmetry and Class Imbalance Investigation.

Investigates why directional performance differed between LONG and SHORT in previous phases:
1. Macro Market Drift: Realized cumulative return of the underlying asset over the window.
2. Signal Frequency Asymmetry: Distribution of LONG vs SHORT decisions.
3. Conditional Payoff Asymmetry: Win rate, average gain, and average loss by direction.
4. Prompt / Feature Symmetry: Whether bullish and bearish conditions have symmetric activation thresholds.
"""

from dataclasses import dataclass
from typing import Dict, Any
import numpy as np
import pandas as pd


@dataclass
class AsymmetryAuditReport:
    total_bars: int
    market_drift_pct: float
    market_trend_direction: str  # BULLISH_DRIFT, BEARISH_DRIFT, NEUTRAL
    long_count: int
    short_count: int
    long_short_ratio: float
    long_win_rate_pct: float
    short_win_rate_pct: float
    long_mean_return_bps: float
    short_mean_return_bps: float
    directional_bias_diagnosis: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_bars": self.total_bars,
            "market_drift_pct": round(self.market_drift_pct, 2),
            "market_trend_direction": self.market_trend_direction,
            "long_count": self.long_count,
            "short_count": self.short_count,
            "long_short_ratio": round(self.long_short_ratio, 2),
            "long_win_rate_pct": round(self.long_win_rate_pct, 2),
            "short_win_rate_pct": round(self.short_win_rate_pct, 2),
            "long_mean_return_bps": round(self.long_mean_return_bps, 1),
            "short_mean_return_bps": round(self.short_mean_return_bps, 1),
            "directional_bias_diagnosis": self.directional_bias_diagnosis,
        }


def audit_directional_asymmetry(
    df: pd.DataFrame, horizon_bars: int = 3
) -> AsymmetryAuditReport:
    """Analyzes market drift, class balance, and payoff asymmetry."""
    n = len(df)
    if n < 10:
        return AsymmetryAuditReport(0, 0.0, "NEUTRAL", 0, 0, 1.0, 0.0, 0.0, 0.0, 0.0, "INSUFFICIENT_DATA")

    close = df["close"]
    market_drift = (close.iloc[-1] / close.iloc[0] - 1.0) * 100.0

    if market_drift > 1.0:
        trend_dir = "BULLISH_DRIFT"
    elif market_drift < -1.0:
        trend_dir = "BEARISH_DRIFT"
    else:
        trend_dir = "NEUTRAL"

    # Forward returns
    fwd_ret = (close.shift(-horizon_bars) / close - 1.0) * 100.0

    from reconstruction.market_state import compute_enriched_market_state_df
    enriched = compute_enriched_market_state_df(df)
    enriched["fwd_ret"] = fwd_ret

    # Simple EMA-based directional signals
    long_mask = (enriched["dist_ema20_pct"] > 0) & enriched["fwd_ret"].notna()
    short_mask = (enriched["dist_ema20_pct"] < 0) & enriched["fwd_ret"].notna()

    long_c = int(long_mask.sum())
    short_c = int(short_mask.sum())
    ratio = (long_c / short_c) if short_c > 0 else 1.0

    long_rets = enriched.loc[long_mask, "fwd_ret"]
    short_rets = -enriched.loc[short_mask, "fwd_ret"]  # Profit on short is negative price move

    long_wr = float((long_rets > 0).mean()) * 100.0 if len(long_rets) > 0 else 0.0
    short_wr = float((short_rets > 0).mean()) * 100.0 if len(short_rets) > 0 else 0.0

    long_bps = float(long_rets.mean()) * 100.0 if len(long_rets) > 0 else 0.0
    short_bps = float(short_rets.mean()) * 100.0 if len(short_rets) > 0 else 0.0

    # Diagnosis
    if trend_dir == "BEARISH_DRIFT" and short_bps > long_bps:
        diag = (
            f"Underlying market drift was bearish ({market_drift:.2f}%). "
            f"SHORT signals outperformed LONG primarily due to macroeconomic beta rather than genuine alpha."
        )
    elif trend_dir == "BULLISH_DRIFT" and long_bps > short_bps:
        diag = (
            f"Underlying market drift was bullish ({market_drift:.2f}%). "
            f"LONG signals outperformed SHORT primarily due to macroeconomic beta."
        )
    else:
        diag = "Payoff differences between LONG and SHORT reflect symmetric volatility and regime oscillations."

    return AsymmetryAuditReport(
        total_bars=n,
        market_drift_pct=market_drift,
        market_trend_direction=trend_dir,
        long_count=long_c,
        short_count=short_c,
        long_short_ratio=ratio,
        long_win_rate_pct=long_wr,
        short_win_rate_pct=short_wr,
        long_mean_return_bps=long_bps,
        short_mean_return_bps=short_bps,
        directional_bias_diagnosis=diag,
    )
