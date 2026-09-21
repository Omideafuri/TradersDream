"""Prediction Horizon Disentanglement Engine.

Evaluates directional returns and predictability across explicit time horizons:
- 5m (1 bar)
- 15m (3 bars)
- 30m (6 bars)
- 1h (12 bars)
- 4h (48 bars)
"""

from dataclasses import dataclass
from typing import Dict, Any, List
import numpy as np
import pandas as pd


@dataclass
class HorizonEvaluation:
    horizon_name: str
    bar_shift: int
    mean_return_pct: float
    std_return_pct: float
    up_fraction_pct: float
    autocorrelation_lag1: float
    signal_noise_ratio: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "horizon_name": self.horizon_name,
            "bar_shift": self.bar_shift,
            "mean_return_pct": round(self.mean_return_pct, 4),
            "std_return_pct": round(self.std_return_pct, 4),
            "up_fraction_pct": round(self.up_fraction_pct, 2),
            "autocorrelation_lag1": round(self.autocorrelation_lag1, 4),
            "signal_noise_ratio": round(self.signal_noise_ratio, 4),
        }


HORIZON_MAP = {
    "5m": 1,
    "15m": 3,
    "30m": 6,
    "1h": 12,
    "4h": 48,
}


def evaluate_prediction_horizons(df: pd.DataFrame) -> List[HorizonEvaluation]:
    """Computes statistical return dynamics across all candidate prediction horizons."""
    close = df["close"]
    n = len(close)
    evaluations: List[HorizonEvaluation] = []

    for name, shift in HORIZON_MAP.items():
        if n <= shift:
            continue

        fwd_returns = (close.shift(-shift) / close - 1.0) * 100.0
        clean_ret = fwd_returns.dropna()

        if len(clean_ret) < 10:
            continue

        mean_r = float(clean_ret.mean())
        std_r = float(clean_ret.std())
        up_frac = float((clean_ret > 0).mean()) * 100.0

        # Lag-1 autocorrelation of forward returns
        lag1_corr = float(clean_ret.autocorr(lag=1)) if len(clean_ret) > 20 else 0.0

        # Signal to noise ratio = |mean| / std
        snr = abs(mean_r) / (std_r if std_r > 0 else 1.0)

        evaluations.append(
            HorizonEvaluation(
                horizon_name=name,
                bar_shift=shift,
                mean_return_pct=mean_r,
                std_return_pct=std_r,
                up_fraction_pct=up_frac,
                autocorrelation_lag1=lag1_corr if not np.isnan(lag1_corr) else 0.0,
                signal_noise_ratio=snr,
            )
        )

    return evaluations
