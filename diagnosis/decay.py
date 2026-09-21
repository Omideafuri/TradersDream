"""Signal Decay Curve and Temporal Persistence Analysis.

Tracks directional price return paths from signal inception through 5m, 15m, 30m, 1h, 2h, 4h horizons:
- Evaluates whether directional information strengthens, persists, decays, or reverses.
- Quantifies optimal holding window and premature or overextended holding issues.
"""

from dataclasses import dataclass
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd

from diagnosis.decomposition import RawDecisionRecord

DECAY_HORIZONS = [
    ("5m", 1),
    ("15m", 3),
    ("30m", 6),
    ("1h", 12),
    ("2h", 24),
    ("4h", 48),
]


@dataclass
class DecayPoint:
    horizon: str
    bars: int
    mean_return_pct: float
    median_return_pct: float
    directional_accuracy_pct: float
    sample_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "horizon": self.horizon,
            "bars": self.bars,
            "mean_return_pct": round(self.mean_return_pct, 4),
            "median_return_pct": round(self.median_return_pct, 4),
            "directional_accuracy_pct": round(self.directional_accuracy_pct, 2),
            "sample_count": self.sample_count,
        }


@dataclass
class SignalDecayCurve:
    action: str  # LONG, SHORT, POOLED
    points: List[DecayPoint]
    peak_horizon: str
    peak_return_pct: float
    curve_behavior: str  # IMPROVING, STABLE, DECAYING, REVERSING, INCONCLUSIVE
    interpretation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "points": [p.to_dict() for p in self.points],
            "peak_horizon": self.peak_horizon,
            "peak_return_pct": round(self.peak_return_pct, 4),
            "curve_behavior": self.curve_behavior,
            "interpretation": self.interpretation,
        }


def compute_decay_curve(
    candles_df: pd.DataFrame,
    records: List[RawDecisionRecord],
    action_filter: str = "POOLED",  # "LONG", "SHORT", or "POOLED"
) -> SignalDecayCurve:
    """Computes fine-grained trajectory across 5m, 15m, 30m, 1h, 2h, 4h."""
    sorted_candles = candles_df.sort_values("timestamp").reset_index(drop=True)
    prices = sorted_candles["close"].to_numpy()
    timestamps = sorted_candles["timestamp"].to_numpy()
    ts_to_idx = {ts: idx for idx, ts in enumerate(timestamps)}

    target_records = [
        r for r in records
        if (action_filter == "POOLED" and r.action in ("LONG", "SHORT"))
        or r.action == action_filter
    ]

    points: List[DecayPoint] = []

    for hz_label, offset in DECAY_HORIZONS:
        dir_returns = []
        for r in target_records:
            idx = ts_to_idx.get(r.timestamp)
            if idx is None or idx + offset >= len(prices):
                continue
            fut_p = prices[idx + offset]
            curr_p = r.price
            raw_r = (fut_p / curr_p) - 1.0

            if r.action == "LONG":
                dir_returns.append(raw_r * 100.0)
            elif r.action == "SHORT":
                dir_returns.append(-raw_r * 100.0)

        n = len(dir_returns)
        if n > 0:
            arr = np.array(dir_returns)
            m_ret = float(np.mean(arr))
            med_ret = float(np.median(arr))
            acc = float((arr > 0).sum() / n) * 100.0
        else:
            m_ret = med_ret = acc = 0.0

        points.append(
            DecayPoint(
                horizon=hz_label,
                bars=offset,
                mean_return_pct=m_ret,
                median_return_pct=med_ret,
                directional_accuracy_pct=acc,
                sample_count=n,
            )
        )

    # Classify curve behavior
    means = [p.mean_return_pct for p in points if p.sample_count > 0]
    if len(means) < 2:
        behavior = "INCONCLUSIVE"
        interpretation = "Insufficient data points across horizons."
        peak_hz = "N/A"
        peak_ret = 0.0
    else:
        max_idx = int(np.argmax(means))
        peak_hz = points[max_idx].horizon
        peak_ret = means[max_idx]

        first_val = means[0]
        last_val = means[-1]

        if all(x <= y for x, y in zip(means, means[1:])) and last_val > 0:
            behavior = "IMPROVING"
            interpretation = "Signal strengthens monotonically as holding horizon expands."
        elif first_val > 0 and last_val < 0:
            behavior = "REVERSING"
            interpretation = "Signal is positive in early bars but turns systematically negative at longer horizons."
        elif max_idx < len(means) - 1 and means[max_idx] > 0 and last_val < means[max_idx] * 0.5:
            behavior = "DECAYING"
            interpretation = f"Signal peaks at {peak_hz} and subsequently degrades over time."
        elif max(means) - min(means) < 0.05:
            behavior = "STABLE"
            interpretation = "Signal exhibits flat trajectory with negligible horizon drift."
        else:
            behavior = "INCONCLUSIVE"
            interpretation = f"Irregular trajectory peaking at {peak_hz} ({peak_ret:.3f}%)."

    return SignalDecayCurve(
        action=action_filter,
        points=points,
        peak_horizon=peak_hz,
        peak_return_pct=peak_ret,
        curve_behavior=behavior,
        interpretation=interpretation,
    )
