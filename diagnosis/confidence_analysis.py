"""Confidence Information Content and Out-of-Sample Calibration Reconstruction.

Evaluates:
1. Relative ranking ability: Spearman rank correlation between confidence and returns, MFE, MAE, and accuracy.
2. Platt-style logistic calibration fitted strictly on DEVELOPMENT (60%) data, evaluated on Validation (20%),
   frozen, and evaluated on Sealed Holdout (20%).
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Tuple, Optional
import math
import numpy as np
import pandas as pd

from diagnosis.decomposition import RawDecisionRecord
from diagnosis.excursion import ExcursionRecord


@dataclass
class ConfidenceCorrelationResult:
    target_metric: str
    sample_size: int
    spearman_rho: float
    p_value: float
    has_monotonic_information: bool
    interpretation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_metric": self.target_metric,
            "sample_size": self.sample_size,
            "spearman_rho": round(self.spearman_rho, 4),
            "p_value": round(self.p_value, 4),
            "has_monotonic_information": self.has_monotonic_information,
            "interpretation": self.interpretation,
        }


@dataclass
class CalibrationReconstructionResult:
    method: str
    train_partition: str
    fitted_params: Dict[str, float]
    dev_brier_before: float
    dev_brier_after: float
    val_brier_before: float
    val_brier_after: float
    holdout_brier_before: float
    holdout_brier_after: float
    is_holdout_sealed: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "method": self.method,
            "train_partition": self.train_partition,
            "fitted_params": {k: round(v, 4) for k, v in self.fitted_params.items()},
            "dev_brier_before": round(self.dev_brier_before, 4),
            "dev_brier_after": round(self.dev_brier_after, 4),
            "val_brier_before": round(self.val_brier_before, 4),
            "val_brier_after": round(self.val_brier_after, 4),
            "holdout_brier_before": round(self.holdout_brier_before, 4),
            "holdout_brier_after": round(self.holdout_brier_after, 4),
            "is_holdout_sealed": self.is_holdout_sealed,
        }


def compute_spearman_rank_correlation(x: np.ndarray, y: np.ndarray) -> Tuple[float, float]:
    """Calculates Spearman rank correlation coefficient and asymptotic p-value in pure NumPy."""
    n = len(x)
    if n < 3:
        return 0.0, 1.0

    rank_x = pd.Series(x).rank().to_numpy()
    rank_y = pd.Series(y).rank().to_numpy()

    mean_x = np.mean(rank_x)
    mean_y = np.mean(rank_y)

    cov = np.sum((rank_x - mean_x) * (rank_y - mean_y))
    std_x = np.sqrt(np.sum((rank_x - mean_x) ** 2))
    std_y = np.sqrt(np.sum((rank_y - mean_y) ** 2))

    if std_x == 0 or std_y == 0:
        return 0.0, 1.0

    rho = float(cov / (std_x * std_y))
    rho = max(-1.0, min(1.0, rho))

    # Student t-test approximation for p-value: t = rho * sqrt((n-2)/(1-rho^2))
    if abs(rho) >= 1.0:
        p_val = 0.0
    else:
        t_stat = rho * math.sqrt((n - 2) / (1.0 - rho ** 2))
        # standard normal approximation for two-tailed p-value
        p_val = 2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(t_stat) / math.sqrt(2.0))))

    return rho, float(p_val)


def evaluate_confidence_information_content(
    records: List[RawDecisionRecord],
    excursions: List[ExcursionRecord],
) -> List[ConfidenceCorrelationResult]:
    """Tests whether confidence contains useful relative ranking information."""
    exc_map = {e.timestamp: e for e in excursions}
    active_records = [r for r in records if r.action in ("LONG", "SHORT") and r.directional_returns.get("15m") is not None]

    results: List[ConfidenceCorrelationResult] = []

    confs = np.array([r.confidence for r in active_records])
    rets = np.array([r.directional_returns["15m"] * 100.0 for r in active_records])
    accs = np.array([1.0 if r.is_correct.get("15m") else 0.0 for r in active_records])

    # 1. Conf vs Return
    rho_r, p_r = compute_spearman_rank_correlation(confs, rets)
    results.append(
        ConfidenceCorrelationResult(
            target_metric="15m Directional Return",
            sample_size=len(confs),
            spearman_rho=rho_r,
            p_value=p_r,
            has_monotonic_information=p_r < 0.05 and rho_r > 0,
            interpretation="Higher confidence significantly predicts higher forward return" if (p_r < 0.05 and rho_r > 0) else "No statistically significant rank correlation with return",
        )
    )

    # 2. Conf vs Accuracy
    rho_a, p_a = compute_spearman_rank_correlation(confs, accs)
    results.append(
        ConfidenceCorrelationResult(
            target_metric="15m Directional Accuracy (Win/Loss)",
            sample_size=len(confs),
            spearman_rho=rho_a,
            p_value=p_a,
            has_monotonic_information=p_a < 0.05 and rho_a > 0,
            interpretation="Higher confidence significantly correlates with higher win probability" if (p_a < 0.05 and rho_a > 0) else "Confidence does not reliably separate wins from losses",
        )
    )

    # 3. Conf vs MFE
    mfes = np.array([exc_map[r.timestamp].mfe_pct for r in active_records if r.timestamp in exc_map])
    c_mfe = np.array([r.confidence for r in active_records if r.timestamp in exc_map])
    if len(mfes) > 0:
        rho_mfe, p_mfe = compute_spearman_rank_correlation(c_mfe, mfes)
        results.append(
            ConfidenceCorrelationResult(
                target_metric="Maximum Favorable Excursion (MFE)",
                sample_size=len(mfes),
                spearman_rho=rho_mfe,
                p_value=p_mfe,
                has_monotonic_information=p_mfe < 0.05 and rho_mfe > 0,
                interpretation="High confidence predicts larger favorable moves" if (p_mfe < 0.05 and rho_mfe > 0) else "Confidence does not scale with excursion magnitude",
            )
        )

    # 4. Conf vs MAE
    maes = np.array([exc_map[r.timestamp].mae_pct for r in active_records if r.timestamp in exc_map])
    if len(maes) > 0:
        rho_mae, p_mae = compute_spearman_rank_correlation(c_mfe, maes)
        results.append(
            ConfidenceCorrelationResult(
                target_metric="Maximum Adverse Excursion (MAE)",
                sample_size=len(maes),
                spearman_rho=rho_mae,
                p_value=p_mae,
                has_monotonic_information=p_mae < 0.05 and rho_mae < 0,
                interpretation="High confidence reduces adverse drawdown" if (p_mae < 0.05 and rho_mae < 0) else "Confidence does not mitigate adverse excursions",
            )
        )

    return results


def fit_platt_scaling(
    scores: np.ndarray,
    labels: np.ndarray,
    lr: float = 0.05,
    epochs: int = 200,
) -> Tuple[float, float]:
    """Fits Platt logistic scaling P(y=1 | s) = sigmoid(A * s + B) on development data via SGD."""
    A = 1.0
    B = 0.0
    n = len(scores)
    if n == 0:
        return 1.0, 0.0

    for _ in range(epochs):
        logits = A * scores + B
        # Numerically stable sigmoid
        probs = 1.0 / (1.0 + np.exp(-np.clip(logits, -20.0, 20.0)))
        errors = probs - labels

        grad_A = float(np.mean(errors * scores))
        grad_B = float(np.mean(errors))

        A -= lr * grad_A
        B -= lr * grad_B

    return A, B


def reconstruct_calibration(
    dev_records: List[RawDecisionRecord],
    val_records: List[RawDecisionRecord],
    holdout_records: List[RawDecisionRecord],
) -> CalibrationReconstructionResult:
    """Fits calibration on Development ONLY, validates on Validation, and freezes for Holdout."""
    def extract_s_y(recs):
        active = [r for r in recs if r.action in ("LONG", "SHORT") and r.directional_returns.get("15m") is not None]
        if not active:
            return np.array([]), np.array([])
        scores = np.array([r.confidence for r in active])
        labels = np.array([1.0 if r.directional_returns["15m"] > 0 else 0.0 for r in active])
        return scores, labels

    dev_s, dev_y = extract_s_y(dev_records)
    val_s, val_y = extract_s_y(val_records)
    hld_s, hld_y = extract_s_y(holdout_records)

    # Fit Platt scaling exclusively on Development
    if len(dev_s) > 10:
        A, B = fit_platt_scaling(dev_s, dev_y)
    else:
        A, B = 1.0, 0.0

    def apply_calib(scores):
        if len(scores) == 0:
            return np.array([])
        return 1.0 / (1.0 + np.exp(-np.clip(A * scores + B, -20.0, 20.0)))

    def brier(p, y):
        return float(np.mean((p - y) ** 2)) if len(p) > 0 else 0.0

    dev_b_before = brier(dev_s, dev_y)
    dev_b_after = brier(apply_calib(dev_s), dev_y)

    val_b_before = brier(val_s, val_y)
    val_b_after = brier(apply_calib(val_s), val_y)

    hld_b_before = brier(hld_s, hld_y)
    hld_b_after = brier(apply_calib(hld_s), hld_y)

    return CalibrationReconstructionResult(
        method="Platt Logistic Scaling",
        train_partition="DEVELOPMENT_60%",
        fitted_params={"slope_A": A, "intercept_B": B},
        dev_brier_before=dev_b_before,
        dev_brier_after=dev_b_after,
        val_brier_before=val_b_before,
        val_brier_after=val_b_after,
        holdout_brier_before=hld_b_before,
        holdout_brier_after=hld_b_after,
        is_holdout_sealed=True,
    )
