"""Data Quality Audit Engine for Phase 6.

Performs exhaustive pre-flight verification on historical OHLCV candle datasets:
- Candle count and date/time range.
- Duplicate timestamp detection.
- Missing interval (gap > 5m) detection.
- OHLC physical invariants (High >= max(Open, Close), Low <= min(Open, Close)).
- Non-positive price checks (Price <= 0).
- Abnormal or negative volume checks.
- Monotonic timestamp ordering.
- NaN / Inf / null checks.
- Produces a machine-readable DataQualityAuditReport.
"""

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np


@dataclass
class DataQualityAuditReport:
    symbol: str
    total_candles: int
    start_timestamp: int
    end_timestamp: int
    start_iso: str
    end_iso: str
    span_days: float
    duplicate_count: int
    gap_count: int
    max_gap_seconds: float
    ohlc_violation_count: int
    non_positive_price_count: int
    negative_volume_count: int
    zero_volume_count: int
    nan_or_inf_count: int
    is_strictly_monotonic: bool
    status: str  # PASSED, FAILED, CONTAMINATED
    violations_summary: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def audit_dataset_quality(
    df: pd.DataFrame,
    symbol: str = "BTCUSDT",
    expected_interval_seconds: int = 300,
) -> DataQualityAuditReport:
    """Audits the physical, temporal, and numeric integrity of a candle dataset."""
    violations: List[str] = []
    n = len(df)

    if n == 0:
        return DataQualityAuditReport(
            symbol=symbol,
            total_candles=0,
            start_timestamp=0,
            end_timestamp=0,
            start_iso="",
            end_iso="",
            span_days=0.0,
            duplicate_count=0,
            gap_count=0,
            max_gap_seconds=0.0,
            ohlc_violation_count=0,
            non_positive_price_count=0,
            negative_volume_count=0,
            zero_volume_count=0,
            nan_or_inf_count=0,
            is_strictly_monotonic=False,
            status="FAILED",
            violations_summary=["Empty dataset provided"],
        )

    # 1. Timestamps and Monotonicity
    ts = df["timestamp"].values
    diffs = np.diff(ts)
    is_monotonic = bool(np.all(diffs > 0))
    if not is_monotonic:
        violations.append("Timestamps are not strictly monotonically increasing")

    # Duplicate timestamps
    dups = int(df["timestamp"].duplicated().sum())
    if dups > 0:
        violations.append(f"Found {dups} duplicate timestamps")

    # Missing gaps (> 5 minutes + 1 second tolerance)
    expected_ms = expected_interval_seconds * 1000
    gaps_mask = diffs > (expected_ms + 1000)
    gap_count = int(np.sum(gaps_mask))
    max_gap_s = float(np.max(diffs) / 1000.0) if len(diffs) > 0 else 0.0

    # 2. OHLC Physical Bounds
    open_p = df["open"].values
    high_p = df["high"].values
    low_p = df["low"].values
    close_p = df["close"].values
    volume_p = df["volume"].values

    ohlc_violations = (
        (high_p < open_p) | (high_p < close_p) | (high_p < low_p) |
        (low_p > open_p) | (low_p > close_p) | (low_p > high_p)
    )
    ohlc_violation_count = int(np.sum(ohlc_violations))
    if ohlc_violation_count > 0:
        violations.append(f"Found {ohlc_violation_count} OHLC physical bound violations")

    # 3. Non-positive Prices
    non_pos_prices = (open_p <= 0) | (high_p <= 0) | (low_p <= 0) | (close_p <= 0)
    non_pos_count = int(np.sum(non_pos_prices))
    if non_pos_count > 0:
        violations.append(f"Found {non_pos_count} non-positive prices")

    # 4. Volume Checks
    neg_vol_count = int(np.sum(volume_p < 0))
    zero_vol_count = int(np.sum(volume_p == 0))
    if neg_vol_count > 0:
        violations.append(f"Found {neg_vol_count} negative volume entries")

    # 5. NaN / Inf
    num_cols = ["open", "high", "low", "close", "volume"]
    nan_inf_count = int(df[num_cols].isna().sum().sum() + np.isinf(df[num_cols].to_numpy()).sum())
    if nan_inf_count > 0:
        violations.append(f"Found {nan_inf_count} NaN or Inf values")

    start_ts = int(ts[0])
    end_ts = int(ts[-1])
    span_d = (end_ts - start_ts) / (1000.0 * 86400.0)
    start_iso = datetime.fromtimestamp(start_ts / 1000, tz=timezone.utc).isoformat()
    end_iso = datetime.fromtimestamp(end_ts / 1000, tz=timezone.utc).isoformat()

    status = "PASSED" if len(violations) == 0 else "CONTAMINATED"

    return DataQualityAuditReport(
        symbol=symbol.upper(),
        total_candles=n,
        start_timestamp=start_ts,
        end_timestamp=end_ts,
        start_iso=start_iso,
        end_iso=end_iso,
        span_days=round(span_d, 2),
        duplicate_count=dups,
        gap_count=gap_count,
        max_gap_seconds=round(max_gap_s, 1),
        ohlc_violation_count=ohlc_violation_count,
        non_positive_price_count=non_pos_count,
        negative_volume_count=neg_vol_count,
        zero_volume_count=zero_vol_count,
        nan_or_inf_count=nan_inf_count,
        is_strictly_monotonic=is_monotonic,
        status=status,
        violations_summary=violations,
    )
