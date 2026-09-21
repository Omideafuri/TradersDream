"""Data Quality and Synthetic-Data Detection module for Phase 9.

Implements rigorous mathematical audits for:
1. Timestamp monotonicity, continuity, and gap detection.
2. OHLC invariant validation.
3. Statistical return/volume anomaly profiling.
4. Mathematical independence and synthetic/scaled relationship detection across asset pairs.
"""

from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Tuple, Optional
import numpy as np
import pandas as pd


@dataclass
class TimestampAuditResult:
    is_monotonic: bool
    has_duplicates: bool
    duplicate_count: int
    total_rows: int
    interval_ms: int
    gap_count: int
    gaps: List[Dict[str, Any]]
    is_valid: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OHLCAuditResult:
    total_rows: int
    violations_high: int
    violations_low: int
    violations_positive: int
    violations_volume: int
    is_valid: bool
    violation_indices: List[int]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class StatisticalProfileResult:
    total_bars: int
    mean_return: float
    std_return: float
    zero_return_pct: float
    max_return: float
    min_return: float
    extreme_return_count: int  # > 5 std dev
    zero_volume_count: int
    mean_volume: float
    max_volume: float
    volume_spikes_count: int  # > 10x mean

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AssetIndependenceResult:
    asset_a: str
    asset_b: str
    overlapping_rows: int
    pearson_return_corr: float
    spearman_return_corr: float
    price_corr: float
    max_abs_return_diff: float
    mean_abs_return_diff: float
    identical_return_ratio: float  # abs diff < 1e-6
    volatility_ratio: float
    volume_corr: float
    price_ratio_std: float  # if price A / price B has std ~ 0 => linear scaling
    is_suspicious: bool
    verdict: str  # INDEPENDENT, SUSPICIOUS, or SYNTHETIC_SCALED

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def audit_timestamps(df: pd.DataFrame, expected_interval_ms: int = 300_000) -> TimestampAuditResult:
    """Audits timestamp monotonicity, duplicates, and gaps."""
    if "timestamp" not in df.columns:
        raise ValueError("DataFrame must contain 'timestamp' column.")

    ts = df["timestamp"].values
    n = len(ts)
    if n == 0:
        return TimestampAuditResult(
            is_monotonic=True, has_duplicates=False, duplicate_count=0,
            total_rows=0, interval_ms=expected_interval_ms, gap_count=0, gaps=[], is_valid=True
        )

    # Check monotonicity
    diffs = np.diff(ts)
    is_monotonic = bool(np.all(diffs > 0))
    has_duplicates = bool(np.any(diffs == 0))
    duplicate_count = int(np.sum(diffs == 0))

    # Gap detection
    gaps = []
    gap_indices = np.where(diffs > expected_interval_ms)[0]
    for idx in gap_indices:
        gaps.append({
            "from_timestamp": int(ts[idx]),
            "to_timestamp": int(ts[idx + 1]),
            "gap_ms": int(diffs[idx]),
            "missing_bars": int(diffs[idx] // expected_interval_ms) - 1,
        })

    is_valid = is_monotonic and not has_duplicates and (len(gaps) == 0)

    return TimestampAuditResult(
        is_monotonic=is_monotonic,
        has_duplicates=has_duplicates,
        duplicate_count=duplicate_count,
        total_rows=n,
        interval_ms=expected_interval_ms,
        gap_count=len(gaps),
        gaps=gaps,
        is_valid=is_valid,
    )


def audit_ohlc(df: pd.DataFrame) -> OHLCAuditResult:
    """Audits OHLC invariants and non-negativity."""
    required = ["open", "high", "low", "close", "volume"]
    for col in required:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    o = df["open"].values
    h = df["high"].values
    l = df["low"].values
    c = df["close"].values
    v = df["volume"].values
    n = len(df)

    # Invariants
    high_violations = np.where((h < o) | (h < c) | (h < l))[0]
    low_violations = np.where((l > o) | (l > c) | (l > h))[0]
    pos_violations = np.where((o <= 0) | (h <= 0) | (l <= 0) | (c <= 0))[0]
    vol_violations = np.where(v < 0)[0]

    all_violations = sorted(list(set(
        high_violations.tolist() + low_violations.tolist() +
        pos_violations.tolist() + vol_violations.tolist()
    )))

    is_valid = (
        len(high_violations) == 0 and
        len(low_violations) == 0 and
        len(pos_violations) == 0 and
        len(vol_violations) == 0
    )

    return OHLCAuditResult(
        total_rows=n,
        violations_high=len(high_violations),
        violations_low=len(low_violations),
        violations_positive=len(pos_violations),
        violations_volume=len(vol_violations),
        is_valid=is_valid,
        violation_indices=all_violations[:100],
    )


def compute_statistical_profile(df: pd.DataFrame) -> StatisticalProfileResult:
    """Profiles return distribution, volatility, zero returns, and volume anomalies."""
    if "close" not in df.columns or "volume" not in df.columns or len(df) < 2:
        return StatisticalProfileResult(
            total_bars=len(df), mean_return=0.0, std_return=0.0, zero_return_pct=0.0,
            max_return=0.0, min_return=0.0, extreme_return_count=0, zero_volume_count=0,
            mean_volume=0.0, max_volume=0.0, volume_spikes_count=0
        )

    closes = df["close"].values
    vols = df["volume"].values
    returns = np.diff(closes) / closes[:-1]

    mean_ret = float(np.mean(returns))
    std_ret = float(np.std(returns)) if len(returns) > 1 else 0.0
    zero_ret_pct = float(np.mean(returns == 0.0) * 100.0)
    max_ret = float(np.max(returns)) if len(returns) > 0 else 0.0
    min_ret = float(np.min(returns)) if len(returns) > 0 else 0.0

    # Extreme returns (> 5 std deviations from mean)
    extreme_count = 0
    if std_ret > 1e-9:
        z_scores = np.abs((returns - mean_ret) / std_ret)
        extreme_count = int(np.sum(z_scores > 5.0))

    # Volume anomalies
    zero_vol_count = int(np.sum(vols == 0.0))
    mean_vol = float(np.mean(vols))
    max_vol = float(np.max(vols)) if len(vols) > 0 else 0.0
    spike_count = int(np.sum(vols > (10.0 * mean_vol))) if mean_vol > 0 else 0

    return StatisticalProfileResult(
        total_bars=len(df),
        mean_return=mean_ret,
        std_return=std_ret,
        zero_return_pct=zero_ret_pct,
        max_return=max_ret,
        min_return=min_ret,
        extreme_return_count=extreme_count,
        zero_volume_count=zero_vol_count,
        mean_volume=mean_vol,
        max_volume=max_vol,
        volume_spikes_count=spike_count,
    )


def evaluate_asset_independence(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    asset_a: str = "ASSET_A",
    asset_b: str = "ASSET_B",
    correlation_threshold: float = 0.999,
) -> AssetIndependenceResult:
    """Tests mathematical independence between two asset series.
    
    Identifies deterministic scaling (e.g., DISC-001 where ETH/SOL were scaled from BTC),
    identical return vectors, or extreme return correlations (r > 0.999).
    """
    # Merge on timestamp
    merged = pd.merge(
        df_a[["timestamp", "close", "volume"]],
        df_b[["timestamp", "close", "volume"]],
        on="timestamp",
        suffixes=("_a", "_b")
    )
    n = len(merged)
    if n < 5:
        return AssetIndependenceResult(
            asset_a=asset_a, asset_b=asset_b, overlapping_rows=n,
            pearson_return_corr=0.0, spearman_return_corr=0.0, price_corr=0.0,
            max_abs_return_diff=1.0, mean_abs_return_diff=1.0, identical_return_ratio=0.0,
            volatility_ratio=1.0, volume_corr=0.0, price_ratio_std=1.0,
            is_suspicious=False, verdict="INSUFFICIENT_OVERLAP"
        )

    # Returns
    ret_a = np.diff(merged["close_a"].values) / merged["close_a"].values[:-1]
    ret_b = np.diff(merged["close_b"].values) / merged["close_b"].values[:-1]

    # Pearson correlation
    pearson_corr = float(np.corrcoef(ret_a, ret_b)[0, 1]) if (np.std(ret_a) > 1e-9 and np.std(ret_b) > 1e-9) else 0.0

    # Spearman rank correlation
    rank_a = pd.Series(ret_a).rank()
    rank_b = pd.Series(ret_b).rank()
    spearman_corr = float(np.corrcoef(rank_a, rank_b)[0, 1]) if (rank_a.std() > 1e-9 and rank_b.std() > 1e-9) else 0.0

    # Price correlation
    price_corr = float(np.corrcoef(merged["close_a"], merged["close_b"])[0, 1])

    # Return differences
    abs_diffs = np.abs(ret_a - ret_b)
    max_diff = float(np.max(abs_diffs))
    mean_diff = float(np.mean(abs_diffs))
    identical_ratio = float(np.mean(abs_diffs < 1e-5))

    # Volatility ratio
    std_a = float(np.std(ret_a))
    std_b = float(np.std(ret_b))
    vol_ratio = (std_a / std_b) if std_b > 1e-9 else 1.0

    # Volume correlation
    vol_corr = float(np.corrcoef(merged["volume_a"], merged["volume_b"])[0, 1]) if (
        np.std(merged["volume_a"]) > 1e-9 and np.std(merged["volume_b"]) > 1e-9
    ) else 0.0

    # Deterministic price scaling test: Price_A / Price_B
    price_ratios = merged["close_a"].values / merged["close_b"].values
    normalized_ratios = price_ratios / np.mean(price_ratios)
    ratio_std = float(np.std(normalized_ratios))

    # Assessment
    is_scaled = bool(ratio_std < 1e-3 and pearson_corr > 0.999)
    is_suspicious = bool(pearson_corr > correlation_threshold or identical_ratio > 0.5 or is_scaled)

    if is_scaled:
        verdict = "SYNTHETIC_SCALED"
    elif is_suspicious:
        verdict = "SUSPICIOUS"
    else:
        verdict = "INDEPENDENT"

    return AssetIndependenceResult(
        asset_a=asset_a,
        asset_b=asset_b,
        overlapping_rows=n,
        pearson_return_corr=pearson_corr,
        spearman_return_corr=spearman_corr,
        price_corr=price_corr,
        max_abs_return_diff=max_diff,
        mean_abs_return_diff=mean_diff,
        identical_return_ratio=identical_ratio,
        volatility_ratio=vol_ratio,
        volume_corr=vol_corr,
        price_ratio_std=ratio_std,
        is_suspicious=is_suspicious,
        verdict=verdict,
    )


@dataclass
class CrossSourceComparisonResult:
    source_a: str
    source_b: str
    asset: str
    overlapping_bars: int
    pearson_return_corr: float
    price_mean_pct_diff: float
    price_max_pct_diff: float
    volume_corr: float
    timestamp_alignment_pct: float
    is_consistent: bool
    notes: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def compare_cross_source_datasets(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    source_a: str = "SOURCE_A",
    source_b: str = "SOURCE_B",
    asset: str = "BTC",
) -> CrossSourceComparisonResult:
    """Compares price and volume behavior across two exchanges for the same asset over overlapping timestamps."""
    merged = pd.merge(
        df_a[["timestamp", "close", "volume"]],
        df_b[["timestamp", "close", "volume"]],
        on="timestamp",
        suffixes=("_a", "_b")
    )
    n = len(merged)
    if n < 5:
        return CrossSourceComparisonResult(
            source_a=source_a,
            source_b=source_b,
            asset=asset,
            overlapping_bars=n,
            pearson_return_corr=0.0,
            price_mean_pct_diff=0.0,
            price_max_pct_diff=0.0,
            volume_corr=0.0,
            timestamp_alignment_pct=0.0,
            is_consistent=False,
            notes="Insufficient overlapping bars across sources.",
        )

    # Percentage price difference
    price_pct_diffs = np.abs(merged["close_a"] - merged["close_b"]) / merged["close_a"] * 100.0
    mean_pct_diff = float(np.mean(price_pct_diffs))
    max_pct_diff = float(np.max(price_pct_diffs))

    # Return correlation
    ret_a = np.diff(merged["close_a"].values) / merged["close_a"].values[:-1]
    ret_b = np.diff(merged["close_b"].values) / merged["close_b"].values[:-1]
    pearson_corr = float(np.corrcoef(ret_a, ret_b)[0, 1]) if (np.std(ret_a) > 1e-9 and np.std(ret_b) > 1e-9) else 0.0

    # Volume correlation
    vol_corr = float(np.corrcoef(merged["volume_a"], merged["volume_b"])[0, 1]) if (
        np.std(merged["volume_a"]) > 1e-9 and np.std(merged["volume_b"]) > 1e-9
    ) else 0.0

    # Typical crypto exchanges exhibit return correlation > 0.85 and price deviations < 1.0%
    is_consistent = (pearson_corr > 0.80 and mean_pct_diff < 1.5)

    return CrossSourceComparisonResult(
        source_a=source_a,
        source_b=source_b,
        asset=asset,
        overlapping_bars=n,
        pearson_return_corr=pearson_corr,
        price_mean_pct_diff=mean_pct_diff,
        price_max_pct_diff=max_pct_diff,
        volume_corr=vol_corr,
        timestamp_alignment_pct=100.0,
        is_consistent=is_consistent,
        notes="High consistency" if is_consistent else "Cross-source deviation detected",
    )

