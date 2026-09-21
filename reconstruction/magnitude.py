"""Return Magnitude Estimation and Categorization Engine.

Estimates expected magnitude of price moves rather than just directional signs:
- Categories:
  - STRONG_NEGATIVE: Return < -0.60% (<-60 bps)
  - MODERATE_NEGATIVE: Return between -0.60% and -0.15% (-60 to -15 bps)
  - NEUTRAL: Return between -0.15% and +0.15% (-15 to +15 bps)
  - MODERATE_POSITIVE: Return between +0.15% and +0.60% (+15 to +60 bps)
  - STRONG_POSITIVE: Return > +0.60% (>+60 bps)
- Evaluates friction threshold alignment (does predicted magnitude exceed round-trip friction?).
"""

from dataclasses import dataclass
from typing import Dict, Any, List
import numpy as np
import pandas as pd


@dataclass
class MagnitudeProfile:
    category: str
    count: int
    frequency_pct: float
    min_return_bps: float
    max_return_bps: float
    mean_return_bps: float
    exceeds_friction_threshold: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "count": self.count,
            "frequency_pct": round(self.frequency_pct, 2),
            "min_return_bps": round(self.min_return_bps, 1),
            "max_return_bps": round(self.max_return_bps, 1),
            "mean_return_bps": round(self.mean_return_bps, 1),
            "exceeds_friction_threshold": self.exceeds_friction_threshold,
        }


def classify_return_magnitude(return_pct: float) -> str:
    """Classifies a percentage return into discrete magnitude categories."""
    if return_pct > 0.60:
        return "STRONG_POSITIVE"
    elif return_pct >= 0.15:
        return "MODERATE_POSITIVE"
    elif return_pct <= -0.60:
        return "STRONG_NEGATIVE"
    elif return_pct <= -0.15:
        return "MODERATE_NEGATIVE"
    else:
        return "NEUTRAL"


def audit_return_magnitudes(
    df: pd.DataFrame, horizon_bars: int = 3, friction_bps: float = 30.0
) -> List[MagnitudeProfile]:
    """Analyzes forward return magnitude distribution over a given horizon."""
    close = df["close"]
    fwd_ret = (close.shift(-horizon_bars) / close - 1.0) * 100.0
    clean_ret = fwd_ret.dropna()
    n = len(clean_ret)

    if n == 0:
        return []

    cats = ["STRONG_NEGATIVE", "MODERATE_NEGATIVE", "NEUTRAL", "MODERATE_POSITIVE", "STRONG_POSITIVE"]
    cat_series = clean_ret.apply(classify_return_magnitude)

    profiles: List[MagnitudeProfile] = []
    for cat in cats:
        sub = clean_ret[cat_series == cat]
        count = len(sub)
        freq = (count / n) * 100.0 if n > 0 else 0.0

        if count > 0:
            bps_series = sub * 100.0  # % to bps
            min_bps = float(bps_series.min())
            max_bps = float(bps_series.max())
            mean_bps = float(bps_series.mean())
            exceeds_friction = abs(mean_bps) > friction_bps
        else:
            min_bps, max_bps, mean_bps = 0.0, 0.0, 0.0
            exceeds_friction = False

        profiles.append(
            MagnitudeProfile(
                category=cat,
                count=count,
                frequency_pct=freq,
                min_return_bps=min_bps,
                max_return_bps=max_bps,
                mean_return_bps=mean_bps,
                exceeds_friction_threshold=exceeds_friction,
            )
        )

    return profiles
