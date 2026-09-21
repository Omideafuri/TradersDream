"""Primary Signal-Level Evaluation and Calibration Engine.

Focuses strictly on predictive information before and independent of transaction friction:
- Evaluates across explicit horizons: 5m, 15m, 30m, 1h, 4h.
- Primary metrics:
  - Directional Accuracy & Balanced Accuracy.
  - Precision and Recall per class.
  - Forward Return Mean and Median.
  - Brier Score & Expected Calibration Error (ECE).
  - Spearman Rank Correlation between Confidence and Realized Return.
  - Spearman Rank Correlation between Confidence and Directional Accuracy.
  - Uncertainty Correlation.
  - Abstention Rate.
"""

from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd


@dataclass
class HorizonSignalMetric:
    horizon_name: str
    bar_shift: int
    sample_size: int
    directional_accuracy_pct: float
    balanced_accuracy_pct: float
    precision_long_pct: float
    recall_long_pct: float
    precision_short_pct: float
    recall_short_pct: float
    mean_forward_return_bps: float
    median_forward_return_bps: float
    expected_magnitude_bps: float
    brier_score: float
    ece_pct: float
    spearman_conf_return: float
    spearman_conf_accuracy: float
    abstention_rate_pct: float
    is_statistically_predictive: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def calculate_spearman_rank_correlation(x: np.ndarray, y: np.ndarray) -> float:
    """Calculates Spearman rank correlation coefficient between two numeric vectors."""
    if len(x) < 5 or np.all(x == x[0]) or np.all(y == y[0]):
        return 0.0

    rank_x = pd.Series(x).rank().values
    rank_y = pd.Series(y).rank().values
    corr = np.corrcoef(rank_x, rank_y)[0, 1]
    return float(corr) if not np.isnan(corr) else 0.0


def calculate_ece(probs: np.ndarray, actuals: np.ndarray, n_bins: int = 5) -> float:
    """Calculates Expected Calibration Error (ECE) across probability bins."""
    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    n = len(probs)
    if n == 0:
        return 0.0

    for i in range(n_bins):
        bin_mask = (probs >= bin_edges[i]) & (probs < bin_edges[i + 1]) if i < n_bins - 1 else (probs >= bin_edges[i]) & (probs <= bin_edges[i + 1])
        bin_count = np.sum(bin_mask)
        if bin_count > 0:
            bin_acc = np.mean(actuals[bin_mask])
            bin_conf = np.mean(probs[bin_mask])
            ece += (bin_count / n) * abs(bin_acc - bin_conf)

    return float(ece) * 100.0


def evaluate_signal_across_horizons(
    df: pd.DataFrame,
    symbol: str = "BTCUSDT",
) -> List[HorizonSignalMetric]:
    """Computes comprehensive predictive signal metrics across all candidate horizons."""
    from reconstruction.market_state import compute_enriched_market_state_df
    from reconstruction.uncertainty import compute_indicator_contradiction_uncertainty
    from reconstruction.abstention import evaluate_decision_with_abstention

    enriched = compute_enriched_market_state_df(df)
    n = len(enriched)

    uncertainties = [compute_indicator_contradiction_uncertainty(r) for _, r in enriched.iterrows()]
    enriched["uncertainty"] = uncertainties
    enriched["expected_magnitude_bps"] = enriched["atr_norm_pct"] * 100.0 * 0.5

    decisions = [
        evaluate_decision_with_abstention(r, uncertainty_threshold=0.50, magnitude_friction_bps=30.0)
        for _, r in enriched.iterrows()
    ]
    enriched["decision"] = decisions

    # Simulated model confidence based on indicator alignment
    confidences = 1.0 - np.array(uncertainties) * 0.5  # maps uncertainty in [0, 1] to confidence in [0.5, 1.0]
    enriched["confidence"] = confidences

    horizons_map = {
        "5m": 1,
        "15m": 3,
        "30m": 6,
        "1h": 12,
        "4h": 48,
    }

    results: List[HorizonSignalMetric] = []
    close = enriched["close"]

    for h_name, shift in horizons_map.items():
        fwd_ret = (close.shift(-shift) / close - 1.0) * 100.0
        enriched["fwd_ret"] = fwd_ret

        valid = enriched.dropna(subset=["fwd_ret"]).copy()
        if len(valid) < 20:
            continue

        actual_up = (valid["fwd_ret"] > 0).astype(int).values
        pred_long = (valid["decision"] == "LONG").values
        pred_short = (valid["decision"] == "SHORT").values
        active_mask = pred_long | pred_short

        active_count = int(np.sum(active_mask))
        abstention_rate = ((len(valid) - active_count) / len(valid)) * 100.0

        if active_count >= 10:
            active_actual = actual_up[active_mask]
            active_preds = np.where(pred_long[active_mask], 1, 0)
            active_rets = np.where(pred_long[active_mask], valid.loc[active_mask, "fwd_ret"], -valid.loc[active_mask, "fwd_ret"])

            # Accuracy
            acc = float(np.mean(active_preds == active_actual)) * 100.0

            # Balanced Accuracy
            tp = np.sum((active_preds == 1) & (active_actual == 1))
            tn = np.sum((active_preds == 0) & (active_actual == 0))
            fp = np.sum((active_preds == 1) & (active_actual == 0))
            fn = np.sum((active_preds == 0) & (active_actual == 1))

            sens = (tp / (tp + fn)) if (tp + fn) > 0 else 0.5
            spec = (tn / (tn + fp)) if (tn + fp) > 0 else 0.5
            bal_acc = float(0.5 * (sens + spec)) * 100.0

            prec_l = float(tp / (tp + fp) * 100.0) if (tp + fp) > 0 else 0.0
            rec_l = float(tp / (tp + fn) * 100.0) if (tp + fn) > 0 else 0.0
            prec_s = float(tn / (tn + fn) * 100.0) if (tn + fn) > 0 else 0.0
            rec_s = float(tn / (tn + fp) * 100.0) if (tn + fp) > 0 else 0.0

            mean_ret_bps = float(np.mean(active_rets)) * 100.0
            median_ret_bps = float(np.median(active_rets)) * 100.0
            exp_mag_bps = float(np.mean(np.abs(active_rets))) * 100.0

            # Calibration
            active_conf = valid.loc[active_mask, "confidence"].values
            # Directional alignment: probability of correct choice
            prob_choice = np.where(active_preds == 1, active_conf, 1.0 - active_conf)
            brier = float(np.mean((prob_choice - active_actual) ** 2))
            ece = calculate_ece(prob_choice, active_actual, n_bins=5)

            # Correlations
            spearman_ret = calculate_spearman_rank_correlation(active_conf, active_rets)
            correct_vec = (active_preds == active_actual).astype(float)
            spearman_acc = calculate_spearman_rank_correlation(active_conf, correct_vec)
        else:
            acc, bal_acc, prec_l, rec_l, prec_s, rec_s = 50.0, 50.0, 0.0, 0.0, 0.0, 0.0
            mean_ret_bps, median_ret_bps, exp_mag_bps = 0.0, 0.0, 0.0
            brier, ece = 0.25, 0.0
            spearman_ret, spearman_acc = 0.0, 0.0

        is_predictive = bool(acc > 53.0 and bal_acc > 52.0 and spearman_acc > 0.05)

        results.append(
            HorizonSignalMetric(
                horizon_name=h_name,
                bar_shift=shift,
                sample_size=len(valid),
                directional_accuracy_pct=round(acc, 2),
                balanced_accuracy_pct=round(bal_acc, 2),
                precision_long_pct=round(prec_l, 2),
                recall_long_pct=round(rec_l, 2),
                precision_short_pct=round(prec_s, 2),
                recall_short_pct=round(rec_s, 2),
                mean_forward_return_bps=round(mean_ret_bps, 1),
                median_forward_return_bps=round(median_ret_bps, 1),
                expected_magnitude_bps=round(exp_mag_bps, 1),
                brier_score=round(brier, 4),
                ece_pct=round(ece, 2),
                spearman_conf_return=round(spearman_ret, 4),
                spearman_conf_accuracy=round(spearman_acc, 4),
                abstention_rate_pct=round(abstention_rate, 2),
                is_statistically_predictive=is_predictive,
            )
        )

    return results
