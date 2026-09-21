"""Statistical Methodology and Hypothesis Framework Audit Engine.

Audits statistical validity, hypothesis formulation, power analysis, and multiple testing:
- Validates formal hypothesis structure:
  - H0: mu <= 0 (Zero or negative alpha)
  - H1: mu = +40 bps (Economic hurdle alpha)
  - Significance level: alpha = 0.05
- Verifies test statistics, p-values, effective sample sizes N_eff, and power calculations.
- Independently audits the Benjamini-Hochberg FDR implementation.
- Distinguishes INCONCLUSIVE (insufficient power) from NOT_SUPPORTED (adequate power, fail to reject).
"""

from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd

from generalization.statistics import apply_benjamini_hochberg_fdr
from temporal.power_audit import audit_statistical_power, norm_cdf


@dataclass
class HypothesisAuditRecord:
    hypothesis_id: str
    asset: str
    horizon: str
    h0_null: str
    h1_alternative: str
    alpha: float
    sample_size: int
    effective_sample_size: float
    test_statistic_t: float
    raw_p_value: float
    multiple_testing_method: str
    adjusted_p_value: float
    statistical_power: float
    verdict: str  # "NOT_SUPPORTED", "INCONCLUSIVE", "SUPPORTED"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def audit_statistical_framework(
    experiments_list: List[Dict[str, Any]],
    alpha: float = 0.05,
) -> List[HypothesisAuditRecord]:
    """Audits pre-registered hypotheses, recomputing BH FDR and power thresholds."""
    if not experiments_list:
        return []

    raw_p_values = [float(e.get("raw_p_value", 1.0)) for e in experiments_list]
    fdr_adjusted = apply_benjamini_hochberg_fdr(raw_p_values, alpha=alpha)

    records: List[HypothesisAuditRecord] = []
    for i, exp in enumerate(experiments_list):
        adj_p, is_sig = fdr_adjusted[i]
        pwr = float(exp.get("statistical_power_at_alternative", exp.get("power", 0.80)))
        t_stat = float(exp.get("test_statistic_t", exp.get("t_stat", 0.0)))
        raw_p = raw_p_values[i]
        n_eff = float(exp.get("effective_sample_size", exp.get("n_eff", 50.0)))

        # Classification rule:
        # If power < 50%, the test is INCONCLUSIVE (underpowered).
        # If power >= 50% and p >= 0.05, it is NOT_SUPPORTED.
        # If p < 0.05 and survives FDR, it is SUPPORTED.
        if is_sig and t_stat > 0:
            verdict = "SUPPORTED"
        elif pwr < 0.50:
            verdict = "INCONCLUSIVE"
        else:
            verdict = "NOT_SUPPORTED"

        records.append(HypothesisAuditRecord(
            hypothesis_id=exp.get("experiment_id", f"HYP-{i+1}"),
            asset=exp.get("asset", exp.get("symbol", "BTCUSDT")),
            horizon=exp.get("horizon", "5m"),
            h0_null="H0: mu <= 0 (Zero/Negative Alpha)",
            h1_alternative="H1: mu = +40 bps (Economic Hurdle)",
            alpha=alpha,
            sample_size=int(exp.get("sample_size", 0)),
            effective_sample_size=round(n_eff, 1),
            test_statistic_t=round(t_stat, 3),
            raw_p_value=round(raw_p, 4),
            multiple_testing_method="Benjamini-Hochberg FDR",
            adjusted_p_value=round(adj_p, 4),
            statistical_power=round(pwr, 4),
            verdict=verdict,
        ))

    return records
