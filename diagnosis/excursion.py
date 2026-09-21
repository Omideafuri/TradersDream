"""Maximum Adverse Excursion (MAE) and Maximum Favorable Excursion (MFE) Engine.

Evaluates how far price moved favorably vs adversely before signal expiration:
- Distinguishes inherently bad predictions from sound predictions killed by premature stops.
- Analyzes excursion distributions across directions, confidence tiers, and market regimes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import pandas as pd

from backtest.dataset import HistoricalDecision


@dataclass
class ExcursionRecord:
    timestamp: int
    action: str
    confidence: float
    entry_price: float
    mfe_pct: float       # Maximum favorable excursion (%) >= 0
    mae_pct: float       # Maximum adverse excursion (%) >= 0
    end_return_pct: float # Return at final bar of window (%)
    bars_to_mfe: int
    bars_to_mae: int
    hit_stop_first: bool  # Whether MAE hit 1.5% before MFE hit 3.0%
    eventual_win: bool    # Whether end_return_pct > 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "action": self.action,
            "confidence": round(self.confidence, 4),
            "entry_price": round(self.entry_price, 2),
            "mfe_pct": round(self.mfe_pct, 4),
            "mae_pct": round(self.mae_pct, 4),
            "end_return_pct": round(self.end_return_pct, 4),
            "bars_to_mfe": self.bars_to_mfe,
            "bars_to_mae": self.bars_to_mae,
            "hit_stop_first": self.hit_stop_first,
            "eventual_win": self.eventual_win,
        }


@dataclass
class ExcursionSummary:
    group_label: str
    sample_count: int
    mean_mfe_pct: float
    median_mfe_pct: float
    mean_mae_pct: float
    median_mae_pct: float
    mfe_to_mae_ratio: float
    premature_stopout_rate_pct: float  # Hits SL 1.5% but eventual_win is True
    clean_loss_rate_pct: float         # Hits SL and stays negative

    def to_dict(self) -> Dict[str, Any]:
        return {
            "group_label": self.group_label,
            "sample_count": self.sample_count,
            "mean_mfe_pct": round(self.mean_mfe_pct, 4),
            "median_mfe_pct": round(self.median_mfe_pct, 4),
            "mean_mae_pct": round(self.mean_mae_pct, 4),
            "median_mae_pct": round(self.median_mae_pct, 4),
            "mfe_to_mae_ratio": round(self.mfe_to_mae_ratio, 3),
            "premature_stopout_rate_pct": round(self.premature_stopout_rate_pct, 2),
            "clean_loss_rate_pct": round(self.clean_loss_rate_pct, 2),
        }


def compute_excursions(
    candles_df: pd.DataFrame,
    decisions: List[HistoricalDecision],
    window_bars: int = 24,
    sl_pct: float = 1.5,
    tp_pct: float = 3.0,
) -> List[ExcursionRecord]:
    """Calculates MFE and MAE for all active directional signals."""
    sorted_candles = candles_df.sort_values("timestamp").reset_index(drop=True)
    highs = sorted_candles["high"].to_numpy()
    lows = sorted_candles["low"].to_numpy()
    closes = sorted_candles["close"].to_numpy()
    timestamps = sorted_candles["timestamp"].to_numpy()
    ts_to_idx = {ts: i for i, ts in enumerate(timestamps)}

    records: List[ExcursionRecord] = []

    for d in decisions:
        if d.action not in ("LONG", "SHORT"):
            continue
        ts = d.timestamp
        if ts not in ts_to_idx:
            continue
        curr_idx = ts_to_idx[ts]
        curr_p = d.price

        start_idx = curr_idx + 1
        end_idx = min(curr_idx + window_bars + 1, len(sorted_candles))
        if start_idx >= end_idx:
            continue

        window_h = highs[start_idx:end_idx]
        window_l = lows[start_idx:end_idx]
        window_c = closes[start_idx:end_idx]

        hit_sl = False
        hit_tp = False
        sl_first = False

        if d.action == "LONG":
            mfe_idx = int(np.argmax(window_h))
            mae_idx = int(np.argmin(window_l))
            mfe_val = (window_h[mfe_idx] / curr_p - 1.0) * 100.0
            mae_val = (1.0 - window_l[mae_idx] / curr_p) * 100.0
            final_ret = (window_c[-1] / curr_p - 1.0) * 100.0

            # Path check for SL vs TP trigger sequence
            for bar_i in range(len(window_h)):
                bar_drop = (1.0 - window_l[bar_i] / curr_p) * 100.0
                bar_gain = (window_h[bar_i] / curr_p - 1.0) * 100.0
                if not hit_sl and bar_drop >= sl_pct:
                    hit_sl = True
                    if not hit_tp:
                        sl_first = True
                if not hit_tp and bar_gain >= tp_pct:
                    hit_tp = True

        else:  # SHORT
            mfe_idx = int(np.argmin(window_l))
            mae_idx = int(np.argmax(window_h))
            mfe_val = (1.0 - window_l[mfe_idx] / curr_p) * 100.0
            mae_val = (window_h[mae_idx] / curr_p - 1.0) * 100.0
            final_ret = (1.0 - window_c[-1] / curr_p) * 100.0

            for bar_i in range(len(window_h)):
                bar_loss = (window_h[bar_i] / curr_p - 1.0) * 100.0
                bar_gain = (1.0 - window_l[bar_i] / curr_p) * 100.0
                if not hit_sl and bar_loss >= sl_pct:
                    hit_sl = True
                    if not hit_tp:
                        sl_first = True
                if not hit_tp and bar_gain >= tp_pct:
                    hit_tp = True

        records.append(
            ExcursionRecord(
                timestamp=ts,
                action=d.action,
                confidence=d.confidence,
                entry_price=curr_p,
                mfe_pct=max(0.0, mfe_val),
                mae_pct=max(0.0, mae_val),
                end_return_pct=final_ret,
                bars_to_mfe=mfe_idx + 1,
                bars_to_mae=mae_idx + 1,
                hit_stop_first=sl_first,
                eventual_win=final_ret > 0,
            )
        )

    return records


def summarize_excursions(
    records: List[ExcursionRecord],
    group_label: str = "ALL",
) -> ExcursionSummary:
    """Summarizes MFE and MAE metrics for a set of excursion records."""
    n = len(records)
    if n == 0:
        return ExcursionSummary(group_label, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    mfes = np.array([r.mfe_pct for r in records])
    maes = np.array([r.mae_pct for r in records])

    m_mfe = float(np.mean(mfes))
    med_mfe = float(np.median(mfes))
    m_mae = float(np.mean(maes))
    med_mae = float(np.median(maes))

    ratio = (m_mfe / m_mae) if m_mae > 0 else 0.0

    # Premature stopout: Hit SL first, but final return was positive
    premature = sum(1 for r in records if r.hit_stop_first and r.eventual_win)
    premature_rate = (premature / n) * 100.0

    # Clean loss: Hit SL first, and final return was negative
    clean_loss = sum(1 for r in records if r.hit_stop_first and not r.eventual_win)
    clean_loss_rate = (clean_loss / n) * 100.0

    return ExcursionSummary(
        group_label=group_label,
        sample_count=n,
        mean_mfe_pct=m_mfe,
        median_mfe_pct=med_mfe,
        mean_mae_pct=m_mae,
        median_mae_pct=med_mae,
        mfe_to_mae_ratio=ratio,
        premature_stopout_rate_pct=premature_rate,
        clean_loss_rate_pct=clean_loss_rate,
    )


Tuple_Excursions = List[ExcursionRecord]
