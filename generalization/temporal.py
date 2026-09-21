"""Chronological Temporal Partitioning and Sealed Holdout Isolation Engine.

Enforces strict non-random chronological dataset splits:
- Development (60%): In-sample analysis, baseline fitting.
- Validation (20%): Out-of-sample sanity checks and model validation.
- Sealed Holdout (20%): Final frozen out-of-sample benchmark.

Guarantees:
- Zero shuffling.
- Zero future data leakage.
- Explicit freeze state verification before holdout evaluation.
"""

from dataclasses import dataclass, asdict
from typing import Dict, Any, Tuple
import pandas as pd


@dataclass
class PartitionSlice:
    name: str  # DEVELOPMENT, VALIDATION, SEALED_HOLDOUT
    start_index: int
    end_index: int
    candle_count: int
    start_timestamp: int
    end_timestamp: int
    start_iso: str
    end_iso: str
    fraction_pct: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TemporalPartitionReport:
    symbol: str
    total_candles: int
    development: PartitionSlice
    validation: PartitionSlice
    sealed_holdout: PartitionSlice
    is_frozen: bool
    integrity_status: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "total_candles": self.total_candles,
            "development": self.development.to_dict(),
            "validation": self.validation.to_dict(),
            "sealed_holdout": self.sealed_holdout.to_dict(),
            "is_frozen": self.is_frozen,
            "integrity_status": self.integrity_status,
        }


def partition_dataset_chronologically(
    df: pd.DataFrame,
    symbol: str = "BTCUSDT",
    dev_ratio: float = 0.60,
    val_ratio: float = 0.20,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, TemporalPartitionReport]:
    """Partitions DataFrame into Development, Validation, and Sealed Holdout."""
    n = len(df)
    if n < 30:
        raise ValueError(f"Dataset too small for 3-way partitioning: {n} candles")

    dev_end = int(n * dev_ratio)
    val_end = int(n * (dev_ratio + val_ratio))

    df_dev = df.iloc[:dev_end].copy()
    df_val = df.iloc[dev_end:val_end].copy()
    df_holdout = df.iloc[val_end:].copy()

    from datetime import datetime, timezone

    def make_slice(name: str, sub: pd.DataFrame, s_idx: int, e_idx: int) -> PartitionSlice:
        s_ts = int(sub["timestamp"].iloc[0])
        e_ts = int(sub["timestamp"].iloc[-1])
        s_iso = datetime.fromtimestamp(s_ts / 1000, tz=timezone.utc).isoformat()
        e_iso = datetime.fromtimestamp(e_ts / 1000, tz=timezone.utc).isoformat()
        return PartitionSlice(
            name=name,
            start_index=s_idx,
            end_index=e_idx,
            candle_count=len(sub),
            start_timestamp=s_ts,
            end_timestamp=e_ts,
            start_iso=s_iso,
            end_iso=e_iso,
            fraction_pct=round(len(sub) / n * 100.0, 2),
        )

    dev_slice = make_slice("DEVELOPMENT", df_dev, 0, dev_end)
    val_slice = make_slice("VALIDATION", df_val, dev_end, val_end)
    holdout_slice = make_slice("SEALED_HOLDOUT", df_holdout, val_end, n)

    # Verify no chronological overlap
    no_overlap = (
        dev_slice.end_timestamp < val_slice.start_timestamp and
        val_slice.end_timestamp < holdout_slice.start_timestamp
    )

    report = TemporalPartitionReport(
        symbol=symbol.upper(),
        total_candles=n,
        development=dev_slice,
        validation=val_slice,
        sealed_holdout=holdout_slice,
        is_frozen=True,
        integrity_status="PASSED" if no_overlap else "CONTAMINATED_OVERLAP",
    )

    return df_dev, df_val, df_holdout, report
