"""Uncertainty Decomposition and Calibration Engine.

Decouples single-scalar confidence into three orthogonal components:
1. Directional Probability: P(Up) in [0.0, 1.0]
2. Expected Magnitude: E[|Delta P / P|] in basis points
3. Epistemic Uncertainty: U in [0.0, 1.0] (measuring model conflict, entropy, or indicator contradiction)

Audits calibration:
- Evaluates whether higher uncertainty corresponds to higher realized variance and lower directional accuracy.
"""

from dataclasses import dataclass
from typing import Dict, Any, List
import numpy as np
import pandas as pd


@dataclass
class DecomposedSignal:
    timestamp: str
    prob_up: float
    expected_magnitude_bps: float
    uncertainty_score: float
    recommended_action: str  # LONG, SHORT, NO_EDGE, HOLD

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "prob_up": round(self.prob_up, 4),
            "expected_magnitude_bps": round(self.expected_magnitude_bps, 1),
            "uncertainty_score": round(self.uncertainty_score, 4),
            "recommended_action": self.recommended_action,
        }


@dataclass
class UncertaintyCalibrationBin:
    bin_name: str
    min_uncertainty: float
    max_uncertainty: float
    sample_count: int
    directional_accuracy_pct: float
    mean_realized_abs_return_bps: float
    variance_realized_return: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bin_name": self.bin_name,
            "min_uncertainty": round(self.min_uncertainty, 2),
            "max_uncertainty": round(self.max_uncertainty, 2),
            "sample_count": self.sample_count,
            "directional_accuracy_pct": round(self.directional_accuracy_pct, 2),
            "mean_realized_abs_return_bps": round(self.mean_realized_abs_return_bps, 1),
            "variance_realized_return": round(self.variance_realized_return, 4),
        }


def compute_indicator_contradiction_uncertainty(row: pd.Series) -> float:
    """Computes an epistemic uncertainty score based on indicator divergence/contradiction.

    Features checked:
    - EMA alignment (dist_ema20 > 0 vs dist_ema50 > 0)
    - RSI direction (rsi > 50 vs < 50)
    - MACD histogram (macd_hist > 0 vs < 0)
    - Market structure (HH_HL vs LH_LL vs MIXED)

    Returns a score between 0.0 (unanimous agreement) and 1.0 (maximal contradiction/uncertainty).
    """
    votes = []

    # Vote 1: EMA20
    d20 = float(row.get("dist_ema20_pct", 0.0))
    votes.append(1 if d20 > 0 else -1)

    # Vote 2: EMA50
    d50 = float(row.get("dist_ema50_pct", 0.0))
    votes.append(1 if d50 > 0 else -1)

    # Vote 3: RSI14
    rsi = float(row.get("rsi14", 50.0))
    if rsi > 52:
        votes.append(1)
    elif rsi < 48:
        votes.append(-1)
    else:
        votes.append(0)

    # Vote 4: MACD Histogram
    macd = float(row.get("macd_hist_norm", 0.0))
    if macd > 0.01:
        votes.append(1)
    elif macd < -0.01:
        votes.append(-1)
    else:
        votes.append(0)

    # Vote 5: Structure
    st = str(row.get("structure_type", "MIXED"))
    if st == "HH_HL":
        votes.append(1)
    elif st == "LH_LL":
        votes.append(-1)
    else:
        votes.append(0)

    pos_votes = sum(1 for v in votes if v > 0)
    neg_votes = sum(1 for v in votes if v < 0)
    total_active = pos_votes + neg_votes

    if total_active == 0:
        return 1.0  # complete ambiguity

    # Agreement ratio: |pos - neg| / total_active in [0, 1]
    agreement = abs(pos_votes - neg_votes) / total_active
    # Uncertainty is 1 - agreement
    uncertainty = 1.0 - agreement
    return float(np.clip(uncertainty, 0.0, 1.0))


def audit_uncertainty_calibration(
    df: pd.DataFrame, horizon_bars: int = 3
) -> List[UncertaintyCalibrationBin]:
    """Audits uncertainty calibration against forward realized returns."""
    close = df["close"]
    fwd_ret = (close.shift(-horizon_bars) / close - 1.0) * 100.0

    # Ensure required indicators exist
    from reconstruction.market_state import compute_enriched_market_state_df
    enriched = compute_enriched_market_state_df(df)

    uncertainties = [compute_indicator_contradiction_uncertainty(row) for _, row in enriched.iterrows()]
    enriched["uncertainty"] = uncertainties
    enriched["fwd_ret"] = fwd_ret

    valid = enriched.dropna(subset=["uncertainty", "fwd_ret"]).copy()
    if len(valid) == 0:
        return []

    bins_def = [
        ("LOW_UNCERTAINTY", 0.0, 0.33),
        ("MODERATE_UNCERTAINTY", 0.33, 0.66),
        ("HIGH_UNCERTAINTY", 0.66, 1.00),
    ]

    results: List[UncertaintyCalibrationBin] = []

    for name, low, high in bins_def:
        if name == "HIGH_UNCERTAINTY":
            mask = (valid["uncertainty"] >= low) & (valid["uncertainty"] <= high)
        else:
            mask = (valid["uncertainty"] >= low) & (valid["uncertainty"] < high)

        sub = valid[mask]
        count = len(sub)

        if count > 5:
            # Predict direction from EMA20
            predicted_up = sub["dist_ema20_pct"] > 0
            actual_up = sub["fwd_ret"] > 0
            acc = float((predicted_up == actual_up).mean()) * 100.0
            abs_ret_bps = float(sub["fwd_ret"].abs().mean()) * 100.0
            var_ret = float(np.var(sub["fwd_ret"]))
        else:
            acc, abs_ret_bps, var_ret = 50.0, 0.0, 0.0

        results.append(
            UncertaintyCalibrationBin(
                bin_name=name,
                min_uncertainty=low,
                max_uncertainty=high,
                sample_count=count,
                directional_accuracy_pct=acc,
                mean_realized_abs_return_bps=abs_ret_bps,
                variance_realized_return=var_ret,
            )
        )

    return results
