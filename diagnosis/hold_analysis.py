"""HOLD Decision Information Content and Market Regime Analysis.

Evaluates market conditions when Jev outputs HOLD:
1. Subsequent realized volatility (realized price variance over 15m and 1h)
2. Subsequent absolute price movement: |P_future / P_current - 1|
3. Underlying directional drift
4. Comparison of HOLD conditions against active LONG and SHORT conditions
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Tuple
import numpy as np
import pandas as pd

from backtest.dataset import HistoricalDecision
from diagnosis.decomposition import RawDecisionRecord


@dataclass
class HoldBehaviorMetrics:
    decision_type: str  # "HOLD" vs "ACTIVE_TRADE"
    sample_count: int
    mean_abs_return_15m_pct: float
    mean_abs_return_1h_pct: float
    mean_forward_volatility_pct: float  # Realized std dev of 5m returns over next 12 bars (1h)
    directional_drift_pct: float
    dominant_market_character: str      # "LOW_VOLATILITY_CHOP", "HIGH_UNCERTAINTY", "NEUTRAL_DRIFT"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_type": self.decision_type,
            "sample_count": self.sample_count,
            "mean_abs_return_15m_pct": round(self.mean_abs_return_15m_pct, 4),
            "mean_abs_return_1h_pct": round(self.mean_abs_return_1h_pct, 4),
            "mean_forward_volatility_pct": round(self.mean_forward_volatility_pct, 4),
            "directional_drift_pct": round(self.directional_drift_pct, 4),
            "dominant_market_character": self.dominant_market_character,
        }


def analyze_hold_behavior(
    candles_df: pd.DataFrame,
    records: List[RawDecisionRecord],
) -> Dict[str, HoldBehaviorMetrics]:
    """Compares market dynamics following HOLD vs ACTIVE (LONG/SHORT) signals."""
    sorted_candles = candles_df.sort_values("timestamp").reset_index(drop=True)
    prices = sorted_candles["close"].to_numpy()
    timestamps = sorted_candles["timestamp"].to_numpy()
    ts_to_idx = {ts: i for i, ts in enumerate(timestamps)}

    hold_recs = [r for r in records if r.action == "HOLD"]
    active_recs = [r for r in records if r.action in ("LONG", "SHORT")]

    def compute_metrics(recs, label):
        abs_15m = []
        abs_1h = []
        vol_1h = []
        drift = []

        for r in recs:
            idx = ts_to_idx.get(r.timestamp)
            if idx is None or idx + 12 >= len(prices):
                continue

            curr_p = r.price
            p_15m = prices[idx + 3]
            p_1h = prices[idx + 12]

            abs_15m.append(abs((p_15m / curr_p) - 1.0) * 100.0)
            abs_1h.append(abs((p_1h / curr_p) - 1.0) * 100.0)
            drift.append(((p_1h / curr_p) - 1.0) * 100.0)

            # 1-hour realized volatility: std of next 12 bar-to-bar returns
            next_window = prices[idx : idx + 13]
            bar_rets = np.diff(next_window) / next_window[:-1]
            vol_1h.append(float(np.std(bar_rets)) * 100.0)

        n = len(abs_15m)
        if n > 0:
            m_abs15 = float(np.mean(abs_15m))
            m_abs1h = float(np.mean(abs_1h))
            m_vol = float(np.mean(vol_1h))
            m_drift = float(np.mean(drift))
        else:
            m_abs15 = m_abs1h = m_vol = m_drift = 0.0

        if label == "HOLD":
            char = "LOW_VOLATILITY_CHOP" if m_abs15 < 0.20 else "HIGH_UNCERTAINTY_SWINGS"
        else:
            char = "TREND_IMPULSE" if m_abs1h > 0.40 else "CHOP"

        return HoldBehaviorMetrics(
            decision_type=label,
            sample_count=n,
            mean_abs_return_15m_pct=m_abs15,
            mean_abs_return_1h_pct=m_abs1h,
            mean_forward_volatility_pct=m_vol,
            directional_drift_pct=m_drift,
            dominant_market_character=char,
        )

    return {
        "hold_metrics": compute_metrics(hold_recs, "HOLD"),
        "active_metrics": compute_metrics(active_recs, "ACTIVE_TRADE"),
    }
