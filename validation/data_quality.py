"""Dataset Integrity and Quality Verification for Historical Market Data.

Enforces physical invariants on OHLCV candle datasets:
1. low <= open and low <= close
2. high >= open and high >= close
3. high >= low
4. open > 0, high > 0, low > 0, close > 0, volume >= 0
5. Strictly increasing chronological timestamp order
6. Zero duplicate timestamps
7. Abnormal gap detection (> expected interval)
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple
import pandas as pd


@dataclass
class DataQualityReport:
    symbol: str
    timeframe: str
    is_valid: bool
    total_candles: int
    start_timestamp: int
    end_timestamp: int
    start_iso: str
    end_iso: str
    duplicate_timestamps: int
    out_of_order_timestamps: int
    invalid_ohlc_rows: int
    non_positive_price_rows: int
    negative_volume_rows: int
    abnormal_gaps_count: int
    issues: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        span_ms = self.end_timestamp - self.start_timestamp
        duration_days = span_ms / (1000.0 * 86400.0) if span_ms > 0 else 0.0
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "is_valid": self.is_valid,
            "total_candles": self.total_candles,
            "start_iso": self.start_iso,
            "end_iso": self.end_iso,
            "duration_days": round(duration_days, 2),
            "duplicate_count": self.duplicate_timestamps,
            "duplicate_timestamps": self.duplicate_timestamps,
            "out_of_order_timestamps": self.out_of_order_timestamps,
            "invalid_ohlc_rows": self.invalid_ohlc_rows,
            "physical_violations": self.invalid_ohlc_rows + self.non_positive_price_rows,
            "non_positive_price_rows": self.non_positive_price_rows,
            "negative_volume_rows": self.negative_volume_rows,
            "gap_count": self.abnormal_gaps_count,
            "abnormal_gaps_count": self.abnormal_gaps_count,
            "violation_count": len(self.issues),
            "issues": self.issues,
        }


class DatasetIntegrityChecker:
    """Verifies dataset correctness and enforces integrity invariants."""

    EXPECTED_INTERVAL_MS = {
        "1m": 60_000,
        "5m": 300_000,
        "15m": 900_000,
        "1h": 3_600_000,
        "4h": 14_400_000,
        "1d": 86_400_000,
    }

    def __init__(self, df: pd.DataFrame, symbol: str = "BTCUSDT", timeframe: str = "5m"):
        self.df = df
        self.symbol = symbol
        self.timeframe = timeframe

    def run_all_checks(self) -> DataQualityReport:
        return self.audit(self.df, symbol=self.symbol, timeframe=self.timeframe)

    @classmethod
    def audit(
        cls,
        df: pd.DataFrame,
        symbol: str = "BTCUSDT",
        timeframe: str = "5m",
        max_allowed_gap_multiplier: float = 3.0,
    ) -> DataQualityReport:
        """Audits an OHLCV DataFrame for data cleanliness, structural validity, and gaps."""
        issues: List[str] = []
        n_candles = len(df)

        if n_candles == 0:
            return DataQualityReport(
                symbol=symbol,
                timeframe=timeframe,
                is_valid=False,
                total_candles=0,
                start_timestamp=0,
                end_timestamp=0,
                start_iso="",
                end_iso="",
                duplicate_timestamps=0,
                out_of_order_timestamps=0,
                invalid_ohlc_rows=0,
                non_positive_price_rows=0,
                negative_volume_rows=0,
                abnormal_gaps_count=0,
                issues=["Dataset is empty."],
            )

        required_cols = {"timestamp", "open", "high", "low", "close", "volume"}
        missing_cols = required_cols - set(df.columns)
        if missing_cols:
            raise ValueError(f"Missing required columns in candle data: {missing_cols}")

        ts_series = df["timestamp"]

        # 1. Duplicates
        duplicate_count = int(ts_series.duplicated().sum())
        if duplicate_count > 0:
            issues.append(f"Found {duplicate_count} duplicate timestamp records.")

        # 2. Ordering
        is_monotonic = ts_series.is_monotonic_increasing
        out_of_order = 0 if is_monotonic else int((ts_series.diff() < 0).sum())
        if not is_monotonic:
            issues.append(f"Found {out_of_order} out-of-order timestamp steps.")

        # 3. OHLC Invariants:
        # low <= open, low <= close, high >= open, high >= close, high >= low
        invalid_high = (df["high"] < df["open"]) | (df["high"] < df["close"]) | (df["high"] < df["low"])
        invalid_low = (df["low"] > df["open"]) | (df["low"] > df["close"])
        invalid_ohlc_rows = int((invalid_high | invalid_low).sum())
        if invalid_ohlc_rows > 0:
            issues.append(f"Found {invalid_ohlc_rows} rows violating OHLC relationship invariants.")

        # 4. Non-positive prices & negative volume
        non_positive_prices = int(
            ((df["open"] <= 0) | (df["high"] <= 0) | (df["low"] <= 0) | (df["close"] <= 0)).sum()
        )
        if non_positive_prices > 0:
            issues.append(f"Found {non_positive_prices} rows with zero or negative price.")

        negative_volume = int((df["volume"] < 0).sum())
        if negative_volume > 0:
            issues.append(f"Found {negative_volume} rows with negative volume.")

        # 5. Gap detection
        expected_ms = cls.EXPECTED_INTERVAL_MS.get(timeframe, 300_000)
        gap_threshold = expected_ms * max_allowed_gap_multiplier
        diffs = ts_series.diff().dropna()
        abnormal_gaps = int((diffs > gap_threshold).sum())
        if abnormal_gaps > 0:
            issues.append(f"Found {abnormal_gaps} abnormal gaps larger than {gap_threshold/1000}s.")

        start_ts = int(ts_series.min())
        end_ts = int(ts_series.max())
        start_iso = datetime.fromtimestamp(start_ts / 1000.0, tz=timezone.utc).isoformat()
        end_iso = datetime.fromtimestamp(end_ts / 1000.0, tz=timezone.utc).isoformat()

        is_valid = (
            duplicate_count == 0
            and out_of_order == 0
            and invalid_ohlc_rows == 0
            and non_positive_prices == 0
            and negative_volume == 0
        )

        return DataQualityReport(
            symbol=symbol,
            timeframe=timeframe,
            is_valid=is_valid,
            total_candles=n_candles,
            start_timestamp=start_ts,
            end_timestamp=end_ts,
            start_iso=start_iso,
            end_iso=end_iso,
            duplicate_timestamps=duplicate_count,
            out_of_order_timestamps=out_of_order,
            invalid_ohlc_rows=invalid_ohlc_rows,
            non_positive_price_rows=non_positive_prices,
            negative_volume_rows=negative_volume,
            abnormal_gaps_count=abnormal_gaps,
            issues=issues,
        )
