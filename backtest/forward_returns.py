"""Forward Returns and Confidence Bucketing Analysis.

Calculates predictive returns over multiple fixed time horizons:
- 5 minutes (1 period for 5m candles)
- 15 minutes (3 periods)
- 30 minutes (6 periods)
- 1 hour (12 periods)
- 4 hours (48 periods)

Mathematical Formulas:
- LONG Forward Return  = (future_price / entry_price) - 1.0
- SHORT Forward Return = 1.0 - (future_price / entry_price)

Strictly measures empirical performance without look-ahead bias during decision generation.
"""

from dataclasses import dataclass
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd

from backtest.dataset import HistoricalDecision


# Mapping of time horizon label to number of 5m periods
HORIZON_PERIODS = {
    "5m": 1,
    "15m": 3,
    "30m": 6,
    "1h": 12,
    "4h": 48,
}


@dataclass
class BucketMetrics:
    bucket_range: str
    total_count: int
    long_count: int
    short_count: int
    hold_count: int
    win_rate: float
    avg_return_pct: float
    median_return_pct: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bucket_range": self.bucket_range,
            "total_count": self.total_count,
            "long_count": self.long_count,
            "short_count": self.short_count,
            "hold_count": self.hold_count,
            "win_rate": round(self.win_rate, 4),
            "avg_return_pct": round(self.avg_return_pct, 4),
            "median_return_pct": round(self.median_return_pct, 4),
        }


def calculate_directional_return(action: str, entry_price: float, future_price: float) -> Optional[float]:
    """Calculates directional forward return.
    
    Formula:
      LONG:  (future_price / entry_price) - 1.0
      SHORT: 1.0 - (future_price / entry_price)
      HOLD:  None
    """
    if entry_price <= 0 or future_price <= 0:
        return None

    if action == "LONG":
        return (future_price / entry_price) - 1.0
    elif action == "SHORT":
        return 1.0 - (future_price / entry_price)
    return None


def calculate_forward_returns(
    candles_df: pd.DataFrame,
    decisions: List[HistoricalDecision],
) -> pd.DataFrame:
    """Computes forward returns across 5m, 15m, 30m, 1h, 4h horizons for each decision.
    
    Aligns decision timestamp with candle close prices at t + horizon.
    """
    price_series = candles_df.set_index("timestamp")["close"]
    timestamps = candles_df["timestamp"].tolist()
    ts_to_idx = {ts: idx for idx, ts in enumerate(timestamps)}

    records = []
    for d in decisions:
        row: Dict[str, Any] = d.to_dict()

        if d.timestamp not in ts_to_idx:
            continue

        curr_idx = ts_to_idx[d.timestamp]
        entry_price = d.price

        for horizon, offset in HORIZON_PERIODS.items():
            target_idx = curr_idx + offset
            if target_idx < len(timestamps):
                target_ts = timestamps[target_idx]
                future_price = price_series.loc[target_ts]
                fwd_ret = calculate_directional_return(d.action, entry_price, future_price)
                row[f"fwd_ret_{horizon}"] = fwd_ret
            else:
                row[f"fwd_ret_{horizon}"] = np.nan

        records.append(row)

    return pd.DataFrame(records)


def analyze_confidence_buckets(
    df_with_returns: pd.DataFrame,
    horizon: str = "15m",
) -> List[BucketMetrics]:
    """Partitions decisions into confidence ranges and measures performance metrics.
    
    Buckets:
      [0.50, 0.59], [0.60, 0.69], [0.70, 0.79], [0.80, 0.89], [0.90, 1.00]
    """
    ret_col = f"fwd_ret_{horizon}"
    if ret_col not in df_with_returns.columns:
        raise ValueError(f"Column {ret_col} not found in dataset")

    bins = [
        ("0.50-0.59", 0.50, 0.60),
        ("0.60-0.69", 0.60, 0.70),
        ("0.70-0.79", 0.70, 0.80),
        ("0.80-0.89", 0.80, 0.90),
        ("0.90-1.00", 0.90, 1.01),
    ]

    metrics: List[BucketMetrics] = []

    for label, low, high in bins:
        sub = df_with_returns[
            (df_with_returns["confidence"] >= low) & 
            (df_with_returns["confidence"] < high)
        ]

        total = len(sub)
        long_count = int((sub["action"] == "LONG").sum())
        short_count = int((sub["action"] == "SHORT").sum())
        hold_count = int((sub["action"] == "HOLD").sum())

        # Returns on active trades (LONG or SHORT)
        active_returns = sub[sub["action"].isin(["LONG", "SHORT"])][ret_col].dropna()

        if len(active_returns) > 0:
            win_rate = float((active_returns > 0).sum() / len(active_returns)) * 100.0
            avg_ret = float(active_returns.mean()) * 100.0
            med_ret = float(active_returns.median()) * 100.0
        else:
            win_rate = 0.0
            avg_ret = 0.0
            med_ret = 0.0

        metrics.append(
            BucketMetrics(
                bucket_range=label,
                total_count=total,
                long_count=long_count,
                short_count=short_count,
                hold_count=hold_count,
                win_rate=win_rate,
                avg_return_pct=avg_ret,
                median_return_pct=med_ret,
            )
        )

    return metrics
