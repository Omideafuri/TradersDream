"""Temporal Signal Stability and Intermittent Behavior Diagnostics.

Splits dataset into chronological non-overlapping quarters:
- Evaluates whether predictive accuracy and forward returns are persistent, intermittent, or decaying over time.
- Verifies absence of regime-switching collapse.
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Tuple
import numpy as np
import pandas as pd

from backtest.dataset import HistoricalDecision
from backtest.engine import BacktestEngine, BacktestConfig
from diagnosis.decomposition import extract_raw_signal_records


@dataclass
class StabilitySegmentResult:
    segment_index: int
    segment_label: str
    candle_count: int
    start_iso: str
    end_iso: str
    active_signals_count: int
    directional_accuracy_15m_pct: float
    mean_forward_return_15m_pct: float
    strategy_net_return_pct: float
    stability_status: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "segment_index": self.segment_index,
            "segment_label": self.segment_label,
            "candle_count": self.candle_count,
            "start_iso": self.start_iso,
            "end_iso": self.end_iso,
            "active_signals_count": self.active_signals_count,
            "directional_accuracy_15m_pct": round(self.directional_accuracy_15m_pct, 2),
            "mean_forward_return_15m_pct": round(self.mean_forward_return_15m_pct, 4),
            "strategy_net_return_pct": round(self.strategy_net_return_pct, 4),
            "stability_status": self.stability_status,
        }


def evaluate_temporal_stability(
    candles_df: pd.DataFrame,
    decisions: List[HistoricalDecision],
    config: BacktestConfig,
    n_segments: int = 4,
) -> Tuple[List[StabilitySegmentResult], str]:
    """Divides dataset into chronological quarters and measures signal stability."""
    from datetime import datetime, timezone

    sorted_candles = candles_df.sort_values("timestamp").reset_index(drop=True)
    n_candles = len(sorted_candles)
    step = n_candles // n_segments

    engine = BacktestEngine(config)
    segments: List[StabilitySegmentResult] = []

    for i in range(n_segments):
        start_i = i * step
        end_i = (i + 1) * step if i < n_segments - 1 else n_candles

        sub_c = sorted_candles.iloc[start_i:end_i].copy()
        s_ts = int(sub_c["timestamp"].min())
        e_ts = int(sub_c["timestamp"].max())

        sub_d = [d for d in decisions if s_ts <= d.timestamp <= e_ts]

        recs = extract_raw_signal_records(sub_c, sub_d)
        active = [r for r in recs if r.action in ("LONG", "SHORT")]
        fwd15 = [r.directional_returns.get("15m") for r in active if r.directional_returns.get("15m") is not None]

        acc = float(np.mean([f > 0 for f in fwd15])) * 100.0 if fwd15 else 0.0
        m_fwd = float(np.mean(fwd15)) * 100.0 if fwd15 else 0.0

        res = engine.run(sub_c, sub_d)
        net_ret = res.metrics.total_return_pct

        status = "POSITIVE" if net_ret > 0 else "NEGATIVE"

        segments.append(
            StabilitySegmentResult(
                segment_index=i + 1,
                segment_label=f"Q{i + 1} (Bars {start_i}-{end_i})",
                candle_count=len(sub_c),
                start_iso=datetime.fromtimestamp(s_ts / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d %H:%M"),
                end_iso=datetime.fromtimestamp(e_ts / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d %H:%M"),
                active_signals_count=len(active),
                directional_accuracy_15m_pct=acc,
                mean_forward_return_15m_pct=m_fwd,
                strategy_net_return_pct=net_ret,
                stability_status=status,
            )
        )

    # Classify overall temporal stability
    returns = [s.strategy_net_return_pct for s in segments]
    if all(r > 0 for r in returns):
        overall_classification = "PERSISTENT_POSITIVE"
    elif all(r <= 0 for r in returns):
        overall_classification = "PERSISTENT_NEGATIVE"
    elif returns[0] > 0 and returns[-1] < 0:
        overall_classification = "DECAYING"
    else:
        overall_classification = "INTERMITTENT_REGIME_DEPENDENT"

    return segments, overall_classification
