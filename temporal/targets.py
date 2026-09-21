"""Temporal Prediction Targets and Forward Excursions.

Constructs strictly causal forward return targets across:
- 5m (1 bar of 5m)
- 15m (3 bars of 5m, or 1 bar of 15m)
- 30m (6 bars of 5m, or 1 bar of 30m)
- 1h (12 bars of 5m, or 1 bar of 1h)
- 4h (48 bars of 5m, or 1 bar of 4h)

Metrics calculated per observation:
- direction (+1 for up, -1 for down, 0 for flat)
- forward_return_pct / forward_return_bps
- abs_forward_return_bps
- max_favorable_excursion_pct (MFE)
- max_adverse_excursion_pct (MAE)
"""

from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd


@dataclass
class ForwardTargetObservation:
    timestamp: int
    entry_price: float
    horizon: str
    shift_bars: int
    exit_price: float
    forward_return_bps: float
    abs_forward_return_bps: float
    direction: int  # +1 (Up), -1 (Down), 0 (Flat)
    mfe_bps: float
    mae_bps: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def calculate_forward_targets(
    df: pd.DataFrame,
    shift_bars: int = 1,
    horizon_name: str = "1_bar",
) -> pd.DataFrame:
    """Calculates forward returns, absolute returns, MFE, and MAE over `shift_bars` ahead."""
    out = df.copy()
    n = len(out)

    # Next close after shift_bars
    future_close = out["close"].shift(-shift_bars)
    entry_close = out["close"]

    forward_ret = (future_close - entry_close) / entry_close
    out[f"target_ret_{horizon_name}"] = forward_ret
    out[f"target_bps_{horizon_name}"] = forward_ret * 10000.0
    out[f"target_abs_bps_{horizon_name}"] = forward_ret.abs() * 10000.0

    # Direction: +1 if return > 0, -1 if return < 0, 0 if 0
    directions = np.zeros(n, dtype=int)
    pos_mask = (forward_ret > 0).values
    neg_mask = (forward_ret < 0).values
    directions[pos_mask] = 1
    directions[neg_mask] = -1
    out[f"target_dir_{horizon_name}"] = directions

    # Rolling future max high and min low for MFE / MAE over the window [t+1, t+shift_bars]
    # For a causal calculation of subsequent excursion:
    mfe_list = []
    mae_list = []

    highs = out["high"].values
    lows = out["low"].values
    closes = entry_close.values

    for i in range(n):
        if i + shift_bars >= n:
            mfe_list.append(np.nan)
            mae_list.append(np.nan)
        else:
            window_high = np.max(highs[i + 1 : i + shift_bars + 1])
            window_low = np.min(lows[i + 1 : i + shift_bars + 1])
            entry = closes[i]

            mfe = (window_high - entry) / entry * 10000.0
            mae = (entry - window_low) / entry * 10000.0
            mfe_list.append(mfe)
            mae_list.append(mae)

    out[f"target_mfe_{horizon_name}"] = mfe_list
    out[f"target_mae_{horizon_name}"] = mae_list

    return out
