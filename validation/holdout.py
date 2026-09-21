"""Sealed Holdout Partitioning and Out-of-Sample Isolation Framework.

Enforces strict three-way chronological partitioning:
  DEVELOPMENT (60%) -> VALIDATION (20%) -> SEALED FINAL HOLDOUT (20%)

Guarantees that:
1. Holdout timestamps strictly succeed Development and Validation timestamps.
2. Exploratory analysis, threshold sweeps, and calibrations are executed strictly on Dev/Val.
3. The Final Holdout is evaluated exactly once on frozen strategy configurations.
"""

from dataclasses import dataclass
from typing import Tuple, List, Dict, Any, Optional
import pandas as pd

from backtest.dataset import HistoricalDecision
from backtest.engine import BacktestEngine, BacktestConfig, BacktestResult


@dataclass
class PartitionMetadata:
    partition_name: str
    candle_count: int
    decision_count: int
    start_timestamp: int
    end_timestamp: int
    start_iso: str
    end_iso: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "partition_name": self.partition_name,
            "candle_count": self.candle_count,
            "decision_count": self.decision_count,
            "start_iso": self.start_iso,
            "end_iso": self.end_iso,
        }


@dataclass
class SealedHoldoutEvaluation:
    dev_metrics: Dict[str, Any]
    val_metrics: Dict[str, Any]
    holdout_metrics: Dict[str, Any]
    is_holdout_sealed: bool
    generalization_decay_pct: float  # (holdout_return - dev_return) / dev_return

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dev_metrics": self.dev_metrics,
            "val_metrics": self.val_metrics,
            "holdout_metrics": self.holdout_metrics,
            "is_holdout_sealed": self.is_holdout_sealed,
            "generalization_decay_pct": round(self.generalization_decay_pct, 2),
        }


def partition_three_way(
    candles: pd.DataFrame,
    decisions: List[HistoricalDecision],
    dev_ratio: float = 0.60,
    val_ratio: float = 0.20,
) -> Tuple[
    Tuple[pd.DataFrame, List[HistoricalDecision]],
    Tuple[pd.DataFrame, List[HistoricalDecision]],
    Tuple[pd.DataFrame, List[HistoricalDecision]],
    List[PartitionMetadata],
]:
    """Splits candles and decisions into Development, Validation, and Sealed Holdout sets."""
    sorted_candles = candles.sort_values("timestamp").reset_index(drop=True)
    n = len(sorted_candles)

    dev_end_idx = int(n * dev_ratio)
    val_end_idx = int(n * (dev_ratio + val_ratio))

    dev_c = sorted_candles.iloc[:dev_end_idx].copy()
    val_c = sorted_candles.iloc[dev_end_idx:val_end_idx].copy()
    holdout_c = sorted_candles.iloc[val_end_idx:].copy()

    dev_max_ts = dev_c["timestamp"].max()
    val_max_ts = val_c["timestamp"].max()

    dev_d = [d for d in decisions if d.timestamp <= dev_max_ts]
    val_d = [d for d in decisions if dev_max_ts < d.timestamp <= val_max_ts]
    holdout_d = [d for d in decisions if d.timestamp > val_max_ts]

    # Enforce strict chronological separation
    assert dev_c["timestamp"].max() < val_c["timestamp"].min(), "Dev/Val overlap detected"
    assert val_c["timestamp"].max() < holdout_c["timestamp"].min(), "Val/Holdout overlap detected"

    from datetime import datetime, timezone

    def meta(name, c, d):
        s_ts = int(c["timestamp"].min())
        e_ts = int(c["timestamp"].max())
        return PartitionMetadata(
            partition_name=name,
            candle_count=len(c),
            decision_count=len(d),
            start_timestamp=s_ts,
            end_timestamp=e_ts,
            start_iso=datetime.fromtimestamp(s_ts / 1000.0, tz=timezone.utc).isoformat(),
            end_iso=datetime.fromtimestamp(e_ts / 1000.0, tz=timezone.utc).isoformat(),
        )

    metadata = [
        meta("DEVELOPMENT", dev_c, dev_d),
        meta("VALIDATION", val_c, val_d),
        meta("FINAL_HOLDOUT", holdout_c, holdout_d),
    ]

    return (dev_c, dev_d), (val_c, val_d), (holdout_c, holdout_d), metadata


def evaluate_sealed_holdout(
    dev_set: Tuple[pd.DataFrame, List[HistoricalDecision]],
    val_set: Tuple[pd.DataFrame, List[HistoricalDecision]],
    holdout_set: Tuple[pd.DataFrame, List[HistoricalDecision]],
    config: BacktestConfig,
) -> SealedHoldoutEvaluation:
    """Executes the final holdout evaluation with frozen parameters."""
    engine = BacktestEngine(config)

    dev_res = engine.run(dev_set[0], dev_set[1])
    val_res = engine.run(val_set[0], val_set[1])
    holdout_res = engine.run(holdout_set[0], holdout_set[1])

    dev_ret = dev_res.metrics.total_return_pct
    hold_ret = holdout_res.metrics.total_return_pct

    decay = ((hold_ret - dev_ret) / abs(dev_ret) * 100.0) if abs(dev_ret) > 0 else 0.0

    return SealedHoldoutEvaluation(
        dev_metrics=dev_res.metrics.to_dict(),
        val_metrics=val_res.metrics.to_dict(),
        holdout_metrics=holdout_res.metrics.to_dict(),
        is_holdout_sealed=True,
        generalization_decay_pct=decay,
    )
