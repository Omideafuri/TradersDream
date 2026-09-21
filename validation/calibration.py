"""Confidence Calibration and Probabilistic Reliability Analysis for Jev Decisions.

Calculates:
1. Bucket-level empirical accuracy and forward return
2. Reliability curve coordinates (mean predicted confidence vs empirical win rate)
3. Brier Score: Mean squared error of probabilistic predictions relative to binary win/loss
4. Expected Calibration Error (ECE)
5. Flags buckets with sample size N < 30 as statistically unreliable.
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import pandas as pd


@dataclass
class CalibratedBucket:
    bucket_label: str
    min_conf: float
    max_conf: float
    count: int
    mean_confidence: float
    empirical_accuracy_pct: float
    mean_forward_return_pct: float
    is_statistically_reliable: bool
    calibration_gap_pct: float  # |accuracy - mean_confidence|

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bucket_label": self.bucket_label,
            "min_conf": self.min_conf,
            "max_conf": self.max_conf,
            "count": self.count,
            "mean_confidence": round(self.mean_confidence, 4),
            "empirical_accuracy_pct": round(self.empirical_accuracy_pct, 2),
            "mean_forward_return_pct": round(self.mean_forward_return_pct, 4),
            "is_statistically_reliable": self.is_statistically_reliable,
            "calibration_gap_pct": round(self.calibration_gap_pct, 2),
        }


@dataclass
class CalibrationReport:
    brier_score: float
    expected_calibration_error_pct: float  # ECE
    total_evaluated_decisions: int
    reliable_buckets_count: int
    unreliable_buckets_count: int
    buckets: List[CalibratedBucket]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "brier_score": round(self.brier_score, 4),
            "expected_calibration_error_pct": round(self.expected_calibration_error_pct, 2),
            "total_evaluated_decisions": self.total_evaluated_decisions,
            "reliable_buckets_count": self.reliable_buckets_count,
            "unreliable_buckets_count": self.unreliable_buckets_count,
            "buckets": [b.to_dict() for b in self.buckets],
        }


def compute_calibration_analysis(
    df_with_returns: pd.DataFrame,
    horizon: str = "15m",
    min_sample_reliable: int = 30,
) -> CalibrationReport:
    """Evaluates whether Jev confidence correlates with realized empirical outcomes."""
    ret_col = f"fwd_ret_{horizon}"
    if ret_col not in df_with_returns.columns:
        raise ValueError(f"Column {ret_col} missing from dataset")

    # Filter active directional trades (LONG or SHORT) with valid forward returns
    active = df_with_returns[
        df_with_returns["action"].isin(["LONG", "SHORT"]) & df_with_returns[ret_col].notna()
    ].copy()

    total_n = len(active)
    if total_n == 0:
        return CalibrationReport(
            brier_score=0.0,
            expected_calibration_error_pct=0.0,
            total_evaluated_decisions=0,
            reliable_buckets_count=0,
            unreliable_buckets_count=0,
            buckets=[],
        )

    # Standard Phase 2/3 confidence bins
    bin_definitions = [
        ("0.50-0.59", 0.50, 0.60),
        ("0.60-0.69", 0.60, 0.70),
        ("0.70-0.79", 0.70, 0.80),
        ("0.80-0.89", 0.80, 0.90),
        ("0.90-1.00", 0.90, 1.01),
    ]

    active["is_win"] = (active[ret_col] > 0).astype(int)

    # Brier Score across entire active set: mean((confidence - is_win)^2)
    brier_score = float(np.mean((active["confidence"] - active["is_win"]) ** 2))

    bucket_results: List[CalibratedBucket] = []
    weighted_ece = 0.0
    reliable_count = 0
    unreliable_count = 0

    for label, low, high in bin_definitions:
        sub = active[(active["confidence"] >= low) & (active["confidence"] < high)]
        count = len(sub)

        if count > 0:
            mean_conf = float(sub["confidence"].mean())
            emp_acc = float(sub["is_win"].mean()) * 100.0
            mean_ret = float(sub[ret_col].mean()) * 100.0
            gap = abs(emp_acc - (mean_conf * 100.0))
            is_reliable = count >= min_sample_reliable

            weighted_ece += (count / total_n) * gap
        else:
            mean_conf = 0.0
            emp_acc = 0.0
            mean_ret = 0.0
            gap = 0.0
            is_reliable = False

        if is_reliable:
            reliable_count += 1
        else:
            unreliable_count += 1

        bucket_results.append(
            CalibratedBucket(
                bucket_label=label,
                min_conf=low,
                max_conf=high,
                count=count,
                mean_confidence=mean_conf,
                empirical_accuracy_pct=emp_acc,
                mean_forward_return_pct=mean_ret,
                is_statistically_reliable=is_reliable,
                calibration_gap_pct=gap,
            )
        )

    return CalibrationReport(
        brier_score=brier_score,
        expected_calibration_error_pct=weighted_ece,
        total_evaluated_decisions=total_n,
        reliable_buckets_count=reliable_count,
        unreliable_buckets_count=unreliable_count,
        buckets=bucket_results,
    )
