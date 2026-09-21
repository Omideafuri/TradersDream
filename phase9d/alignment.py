"""Temporal Alignment and Causal Lookback Module for Phase 9D.

Enforces strict timestamp alignment:
Given a candle ending at timestamp t, only microstructure records with
timestamp <= t and within the pre-registered causal lookback window [t - W, t]
may be accessed.
"""

from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd


class TemporalAlignment:
    """Manages causal timestamp alignment and window slicing for microstructure observations."""

    # Pre-registered aggregation windows in milliseconds
    WINDOWS_MS = {
        "30s": 30_000,
        "1m": 60_000,
        "3m": 180_000,
        "5m": 300_000,
    }

    @classmethod
    def slice_causal_trades(
        cls,
        trades_df: pd.DataFrame,
        candle_end_ts: int,
        window_name: str = "5m",
    ) -> pd.DataFrame:
        """Extracts trades falling strictly within [candle_end_ts - window_ms, candle_end_ts]."""
        window_ms = cls.WINDOWS_MS.get(window_name, 300_000)
        start_ts = candle_end_ts - window_ms

        if "timestamp" not in trades_df.columns:
            raise ValueError("trades_df must contain 'timestamp' column.")

        # Point-in-time filter: start_ts <= t <= candle_end_ts
        mask = (trades_df["timestamp"] >= start_ts) & (trades_df["timestamp"] <= candle_end_ts)
        return trades_df.loc[mask].copy()

    @classmethod
    def get_latest_causal_orderbook(
        cls,
        snapshots_df: pd.DataFrame,
        candle_end_ts: int,
    ) -> pd.DataFrame:
        """Finds the most recent order-book snapshot with timestamp <= candle_end_ts."""
        if snapshots_df.empty or "timestamp" not in snapshots_df.columns:
            return pd.DataFrame()

        past_snaps = snapshots_df[snapshots_df["timestamp"] <= candle_end_ts]
        if past_snaps.empty:
            return pd.DataFrame()

        latest_ts = past_snaps["timestamp"].max()
        return past_snaps[past_snaps["timestamp"] == latest_ts].copy()

    @staticmethod
    def verify_no_lookahead_leakage(
        aligned_features_df: pd.DataFrame,
        candle_timestamps: np.ndarray | List[int],
    ) -> bool:
        """Verifies that no microstructure feature timestamp exceeds the candle boundary."""
        if "feature_timestamp" not in aligned_features_df.columns:
            return True

        f_ts = aligned_features_df["feature_timestamp"].values
        c_ts = np.asarray(candle_timestamps)
        return bool(np.all(f_ts <= c_ts))
