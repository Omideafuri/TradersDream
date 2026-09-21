"""Entry Timing Delay and Temporal Misalignment Diagnostics.

Evaluates whether Jev predictions suffer from premature entry (jumping in before a retracement completes)
or delayed entry (chasing moves after the impulse has concluded).
Tests entry offsets: 0, +1, +2, +3, +6 bars post-signal.
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Tuple, Optional
import numpy as np
import pandas as pd

from backtest.dataset import HistoricalDecision


@dataclass
class TimingOffsetResult:
    offset_bars: int
    delay_minutes: int
    evaluated_trades: int
    mean_forward_return_pct: float  # 15m post-delayed entry
    median_forward_return_pct: float
    directional_accuracy_pct: float
    mean_mfe_pct: float
    mean_mae_pct: float
    mfe_to_mae_ratio: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "offset_bars": self.offset_bars,
            "delay_minutes": self.delay_minutes,
            "evaluated_trades": self.evaluated_trades,
            "mean_forward_return_pct": round(self.mean_forward_return_pct, 4),
            "median_forward_return_pct": round(self.median_forward_return_pct, 4),
            "directional_accuracy_pct": round(self.directional_accuracy_pct, 2),
            "mean_mfe_pct": round(self.mean_mfe_pct, 4),
            "mean_mae_pct": round(self.mean_mae_pct, 4),
            "mfe_to_mae_ratio": round(self.mfe_to_mae_ratio, 3),
        }


def evaluate_entry_timing_delays(
    candles_df: pd.DataFrame,
    decisions: List[HistoricalDecision],
    eval_horizon_bars: int = 3,  # 15m forward from delayed entry
    window_mfe_bars: int = 24,
) -> List[TimingOffsetResult]:
    """Tests hypothetical entry offsets: 0, 1, 2, 3, 6 bars."""
    sorted_candles = candles_df.sort_values("timestamp").reset_index(drop=True)
    opens = sorted_candles["open"].to_numpy()
    highs = sorted_candles["high"].to_numpy()
    lows = sorted_candles["low"].to_numpy()
    closes = sorted_candles["close"].to_numpy()
    timestamps = sorted_candles["timestamp"].to_numpy()
    ts_to_idx = {ts: i for i, ts in enumerate(timestamps)}

    offsets = [
        (0, 0),
        (1, 5),
        (2, 10),
        (3, 15),
        (6, 30),
    ]

    results: List[TimingOffsetResult] = []

    for offset, delay_mins in offsets:
        rets = []
        mfes = []
        maes = []

        for d in decisions:
            if d.action not in ("LONG", "SHORT"):
                continue
            ts = d.timestamp
            if ts not in ts_to_idx:
                continue
            curr_idx = ts_to_idx[ts]

            entry_idx = curr_idx + offset
            target_idx = entry_idx + eval_horizon_bars
            mfe_end_idx = min(entry_idx + window_mfe_bars, len(sorted_candles))

            if target_idx >= len(sorted_candles) or entry_idx >= len(sorted_candles):
                continue

            entry_p = closes[entry_idx]
            exit_p = closes[target_idx]

            raw_ret = (exit_p / entry_p) - 1.0

            sub_h = highs[entry_idx + 1 : mfe_end_idx]
            sub_l = lows[entry_idx + 1 : mfe_end_idx]

            if len(sub_h) == 0 or len(sub_l) == 0:
                continue

            if d.action == "LONG":
                dir_ret = raw_ret * 100.0
                mfe_val = (np.max(sub_h) / entry_p - 1.0) * 100.0
                mae_val = (1.0 - np.min(sub_l) / entry_p) * 100.0
            else:  # SHORT
                dir_ret = -raw_ret * 100.0
                mfe_val = (1.0 - np.min(sub_l) / entry_p) * 100.0
                mae_val = (np.max(sub_h) / entry_p - 1.0) * 100.0

            rets.append(dir_ret)
            mfes.append(max(0.0, mfe_val))
            maes.append(max(0.0, mae_val))

        n = len(rets)
        if n > 0:
            arr_r = np.array(rets)
            arr_mfe = np.array(mfes)
            arr_mae = np.array(maes)

            m_ret = float(np.mean(arr_r))
            med_ret = float(np.median(arr_r))
            acc = float((arr_r > 0).sum() / n) * 100.0
            m_mfe = float(np.mean(arr_mfe))
            m_mae = float(np.mean(arr_mae))
            ratio = (m_mfe / m_mae) if m_mae > 0 else 0.0
        else:
            m_ret = med_ret = acc = m_mfe = m_mae = ratio = 0.0

        results.append(
            TimingOffsetResult(
                offset_bars=offset,
                delay_minutes=delay_mins,
                evaluated_trades=n,
                mean_forward_return_pct=m_ret,
                median_forward_return_pct=med_ret,
                directional_accuracy_pct=acc,
                mean_mfe_pct=m_mfe,
                mean_mae_pct=m_mae,
                mfe_to_mae_ratio=ratio,
            )
        )

    return results
