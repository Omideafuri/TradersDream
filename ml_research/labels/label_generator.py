"""
XAU/USD ML Research Track — Label Generator
Computes forward gross and net returns after realistic transaction costs and financing.
"""

from typing import Dict, List, Tuple
import numpy as np
import pandas as pd

HORIZONS: List[int] = [4, 12, 24]

# Cost Model Parameters
SPREAD_ROUNDTRIP_RATE: float = 0.0004     # 4.0 bps (2.0 bps entry + 2.0 bps exit)
SLIPPAGE_ROUNDTRIP_RATE: float = 0.0004   # 4.0 bps (2.0 bps entry + 2.0 bps exit)
COMMISSION_PER_OZ_PER_FILL: float = 0.02 # $0.02 / oz flat fee per fill ($0.04 RT)
ANNUAL_SWAP_RATE: float = 0.035          # 3.5% annualized financing interest


def calculate_swap_days(entry_dt: pd.Timestamp, exit_dt: pd.Timestamp) -> int:
    """
    Calculate financing rollover days between entry and exit timestamps.
    Rollover cut occurs daily at 22:00 UTC.
    Wednesday 22:00 UTC incurs triple rollover (covers weekend settlement).
    """
    cur = entry_dt.floor("D") + pd.Timedelta(hours=22)
    if cur <= entry_dt:
        cur += pd.Timedelta(days=1)

    standard_count = 0
    wednesday_count = 0

    while cur <= exit_dt:
        wd = cur.weekday()
        if wd == 2:  # Wednesday
            wednesday_count += 1
        elif wd in (0, 1, 3, 4):  # Mon, Tue, Thu, Fri
            standard_count += 1
        cur += pd.Timedelta(days=1)

    return standard_count + 3 * wednesday_count


def compute_labels(df: pd.DataFrame, horizons: List[int] = HORIZONS) -> pd.DataFrame:
    """
    Generates causal forward labels for bar t:
    - Entry at Open(t+1)
    - Exit at Open(t+1+H)
    - Modeled transaction friction: 8.0 bps RT + $0.04/oz commission + overnight financing

    Output columns for each H in horizons:
    - ret_gross_{H}h: gross forward return
    - friction_{H}h: total modeled round-trip friction
    - ret_net_{H}h: net forward return after friction
    - target_{H}h: binary target (1 if ret_net > 0, else 0)
    """
    n = len(df)
    opens = df["open"].to_numpy()
    dts = pd.to_datetime(df["dt_utc"], utc=True).to_numpy()

    df_labels = pd.DataFrame(index=df.index)

    for h in horizons:
        ret_gross = np.full(n, np.nan, dtype=float)
        friction = np.full(n, np.nan, dtype=float)
        ret_net = np.full(n, np.nan, dtype=float)
        target = np.full(n, np.nan, dtype=float)

        # For bar t, entry is at index t+1, exit is at index t+1+h
        # Maximum valid t is n - 1 - (1 + h) = n - 2 - h
        for t in range(n - 1 - h):
            entry_idx = t + 1
            exit_idx = t + 1 + h

            p_entry = opens[entry_idx]
            p_exit = opens[exit_idx]

            gross = (p_exit - p_entry) / p_entry

            t_entry = pd.Timestamp(dts[entry_idx])
            t_exit = pd.Timestamp(dts[exit_idx])

            swap_days = calculate_swap_days(t_entry, t_exit)
            swap_cost = (ANNUAL_SWAP_RATE / 365.0) * swap_days

            comm_cost = (2.0 * COMMISSION_PER_OZ_PER_FILL) / p_entry
            spread_slip_cost = SPREAD_ROUNDTRIP_RATE + SLIPPAGE_ROUNDTRIP_RATE

            total_fric = spread_slip_cost + comm_cost + swap_cost
            net = gross - total_fric

            ret_gross[t] = gross
            friction[t] = total_fric
            ret_net[t] = net
            target[t] = 1.0 if net > 0.0 else 0.0

        df_labels[f"ret_gross_{h}h"] = ret_gross
        df_labels[f"friction_{h}h"] = friction
        df_labels[f"ret_net_{h}h"] = ret_net
        df_labels[f"target_{h}h"] = target

    return df_labels
