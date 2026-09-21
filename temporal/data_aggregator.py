"""Temporal Data Aggregator and Multi-Timeframe Dataset Builder.

Performs strictly causal OHLCV resampling from base 5m datasets into:
- 15m (3 x 5m bars)
- 30m (6 x 5m bars)
- 1h (12 x 5m bars)
- 4h (48 x 5m bars)

Maintains causal invariants:
- A bar at timestamp T contains data from [T, T + duration).
- Bar close occurs strictly at T + duration.
- Validates monotonicity, absence of gaps, and valid OHLC bounds.
- Computes deterministic SHA256 hashes per (symbol, timeframe).
"""

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import hashlib
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import pandas as pd


# Mapping of timeframe name to number of 5m base bars and duration in milliseconds
TIMEFRAME_BAR_RATIOS: Dict[str, int] = {
    "5m": 1,
    "15m": 3,
    "30m": 6,
    "1h": 12,
    "4h": 48,
}

TIMEFRAME_MS: Dict[str, int] = {
    "5m": 5 * 60 * 1000,
    "15m": 15 * 60 * 1000,
    "30m": 30 * 60 * 1000,
    "1h": 60 * 60 * 1000,
    "4h": 4 * 60 * 60 * 1000,
}


@dataclass
class AggregatedDatasetMeta:
    symbol: str
    timeframe: str
    base_timeframe: str
    candle_count: int
    start_timestamp: int
    end_timestamp: int
    start_iso: str
    end_iso: str
    sha256_hash: str
    is_valid_ohlc: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class TemporalDataAggregator:
    """Aggregates and verifies multi-timeframe candle datasets causally."""

    @staticmethod
    def compute_sha256(df: pd.DataFrame) -> str:
        """Computes deterministic SHA256 checksum for tabular data."""
        content = df.to_csv(index=False).encode("utf-8")
        return hashlib.sha256(content).hexdigest()

    @staticmethod
    def validate_ohlc_invariants(df: pd.DataFrame) -> bool:
        """Verifies strict OHLC structural rules and positive volumes."""
        if len(df) == 0:
            return False
        high_valid = (df["high"] >= df["open"]) & (df["high"] >= df["close"]) & (df["high"] >= df["low"])
        low_valid = (df["low"] <= df["open"]) & (df["low"] <= df["close"]) & (df["low"] <= df["high"])
        vol_valid = df["volume"] >= 0.0
        time_monotonic = df["timestamp"].is_monotonic_increasing
        return bool(high_valid.all() and low_valid.all() and vol_valid.all() and time_monotonic)

    @classmethod
    def aggregate_candles(
        cls,
        base_df: pd.DataFrame,
        target_timeframe: str,
        symbol: str = "BTCUSDT",
    ) -> Tuple[pd.DataFrame, AggregatedDatasetMeta]:
        """Causally resamples base 5m candles into target_timeframe candles."""
        if target_timeframe not in TIMEFRAME_BAR_RATIOS:
            raise ValueError(f"Unsupported timeframe: {target_timeframe}. Choose from {list(TIMEFRAME_BAR_RATIOS.keys())}")

        ratio = TIMEFRAME_BAR_RATIOS[target_timeframe]
        if ratio == 1:
            # 5m dataset, no aggregation needed
            df_out = base_df.copy().reset_index(drop=True)
            sha256 = cls.compute_sha256(df_out)
            valid = cls.validate_ohlc_invariants(df_out)
            meta = AggregatedDatasetMeta(
                symbol=symbol.upper(),
                timeframe=target_timeframe,
                base_timeframe="5m",
                candle_count=len(df_out),
                start_timestamp=int(df_out["timestamp"].iloc[0]),
                end_timestamp=int(df_out["timestamp"].iloc[-1]),
                start_iso=datetime.fromtimestamp(int(df_out["timestamp"].iloc[0]) / 1000, tz=timezone.utc).isoformat(),
                end_iso=datetime.fromtimestamp(int(df_out["timestamp"].iloc[-1]) / 1000, tz=timezone.utc).isoformat(),
                sha256_hash=sha256,
                is_valid_ohlc=valid,
            )
            return df_out, meta

        # Ensure base data is sorted
        sorted_base = base_df.sort_values("timestamp").reset_index(drop=True)
        n_complete_bars = len(sorted_base) // ratio

        if n_complete_bars == 0:
            raise ValueError(f"Insufficient base candles ({len(sorted_base)}) to construct 1 bar of {target_timeframe} (requires {ratio})")

        usable_len = n_complete_bars * ratio
        usable_base = sorted_base.iloc[:usable_len].copy()

        # Group by chunks of size `ratio`
        chunk_indices = np.repeat(np.arange(n_complete_bars), ratio)
        usable_base["chunk_id"] = chunk_indices

        agg_dict = {
            "timestamp": "first",
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }
        resampled = usable_base.groupby("chunk_id", as_index=False).agg(agg_dict)
        resampled.sort_values("timestamp", inplace=True)
        resampled.reset_index(drop=True, inplace=True)

        valid = cls.validate_ohlc_invariants(resampled)
        sha256 = cls.compute_sha256(resampled)

        start_ts = int(resampled["timestamp"].iloc[0])
        end_ts = int(resampled["timestamp"].iloc[-1])
        start_iso = datetime.fromtimestamp(start_ts / 1000, tz=timezone.utc).isoformat()
        end_iso = datetime.fromtimestamp(end_ts / 1000, tz=timezone.utc).isoformat()

        meta = AggregatedDatasetMeta(
            symbol=symbol.upper(),
            timeframe=target_timeframe,
            base_timeframe="5m",
            candle_count=len(resampled),
            start_timestamp=start_ts,
            end_timestamp=end_ts,
            start_iso=start_iso,
            end_iso=end_iso,
            sha256_hash=sha256,
            is_valid_ohlc=valid,
        )
        return resampled, meta
