"""Regime-Conditioned Microstructure Analysis Module for Phase 9D.

Evaluates whether microstructure features (imbalance, spread, trade flow)
exhibit conditional performance or regime-dependent predictive accuracy across
the 6 Phase 9C causal market regimes.
"""

from dataclasses import dataclass, asdict
from typing import Dict, List, Tuple, Optional, Any
import numpy as np
import pandas as pd

from phase9d.statistical_analysis import calc_spearman, MultipleTesting
from phase9d.economic_analysis import DualEconomicGate


@dataclass
class RegimeEvaluationResult:
    regime_name: str
    sample_size: int
    signal_frequency: float
    directional_accuracy: float
    rank_ic: float
    raw_p_value: float
    fdr_q_value: float
    mean_gross_return_bps: float
    mean_dynamic_cost_bps: float
    net_return_bps: float
    ci_lower_bps: float
    ci_upper_bps: float
    classification: str  # SUPPORTED, WEAK_OBSERVATION_ONLY, ECONOMICALLY_INSUFFICIENT, REJECTED

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class RegimeMicrostructureAnalyzer:
    """Performs regime-conditioned statistical and economic audits on microstructure signals."""

    REGIMES = [
        "TRENDING_UP",
        "TRENDING_DOWN",
        "RANGE_BOUND",
        "HIGH_VOLATILITY",
        "LOW_VOLATILITY",
        "TRANSITION",
    ]

    def __init__(self, dual_gate: Optional[DualEconomicGate] = None):
        self.dual_gate = dual_gate or DualEconomicGate()

    def evaluate_regimes(
        self,
        signal_series: pd.Series,
        target_return_series: pd.Series,
        regime_code_series: pd.Series,
        spread_series: Optional[pd.Series] = None,
    ) -> List[RegimeEvaluationResult]:
        """Evaluates signal accuracy and net economic performance conditioned on market regime."""
        # Mapping regime code to canonical name
        code_to_name = {
            1.0: "TRENDING_UP",
            2.0: "TRENDING_DOWN",
            3.0: "HIGH_VOLATILITY",
            4.0: "LOW_VOLATILITY",
            5.0: "RANGE_BOUND",
            0.0: "TRANSITION",
        }

        raw_results = []
        raw_p_values = []

        total_bars = len(signal_series)

        for code, name in code_to_name.items():
            reg_mask = (regime_code_series == code)
            x = signal_series[reg_mask].values
            y = target_return_series[reg_mask].values
            n_sub = len(x)

            if n_sub < 30:
                raw_results.append({
                    "name": name, "n": n_sub, "freq": n_sub / (total_bars + 1e-9),
                    "dir_acc": 0.50, "ic": 0.0, "p": 1.0, "gross": 0.0,
                    "cost": 40.0, "net": -40.0, "ci_l": 0.0, "ci_u": 0.0,
                    "status": "WEAK_OBSERVATION_ONLY",
                })
                raw_p_values.append(1.0)
                continue

            # Rank IC
            ic, p_val = calc_spearman(x, y)
            raw_p_values.append(p_val)

            # Directional accuracy
            valid_sign = (x != 0) & ~np.isnan(x) & ~np.isnan(y)
            dir_acc = float(np.mean(np.sign(x[valid_sign]) == np.sign(y[valid_sign]))) if np.sum(valid_sign) > 0 else 0.50

            # Gross trading edge in bps
            gross_bps = float(np.mean(np.sign(x[valid_sign]) * y[valid_sign]) * 10000.0) if np.sum(valid_sign) > 0 else 0.0

            # Dynamic cost in regime
            mean_spread = float(spread_series[reg_mask].mean()) if spread_series is not None and not spread_series.empty else 5.0
            cost_eval = self.dual_gate.compute_dynamic_cost(spread_bps=mean_spread)
            dynamic_cost = cost_eval.total_dynamic_hurdle_bps
            net_bps = gross_bps - dynamic_cost

            # Bootstrap 95% CI of gross return
            if np.sum(valid_sign) >= 20:
                ret_sample = np.sign(x[valid_sign]) * y[valid_sign] * 10000.0
                boot_means = [np.mean(np.random.choice(ret_sample, size=len(ret_sample), replace=True)) for _ in range(200)]
                ci_l = float(np.percentile(boot_means, 2.5))
                ci_u = float(np.percentile(boot_means, 97.5))
            else:
                ci_l, ci_u = gross_bps, gross_bps

            # Classification
            if n_sub < 300:
                status = "WEAK_OBSERVATION_ONLY"
            elif p_val < 0.05 and net_bps > 0.0:
                status = "SUPPORTED"
            elif p_val < 0.05 and gross_bps > 0.0:
                status = "ECONOMICALLY_INSUFFICIENT"
            else:
                status = "REJECTED"

            raw_results.append({
                "name": name, "n": n_sub, "freq": n_sub / (total_bars + 1e-9),
                "dir_acc": dir_acc, "ic": ic, "p": p_val, "gross": gross_bps,
                "cost": dynamic_cost, "net": net_bps, "ci_l": ci_l, "ci_u": ci_u,
                "status": status,
            })

        # Apply FDR correction
        q_vals, _ = MultipleTesting.benjamini_hochberg(raw_p_values, alpha=0.05)

        results = []
        for i, r in enumerate(raw_results):
            results.append(RegimeEvaluationResult(
                regime_name=r["name"],
                sample_size=r["n"],
                signal_frequency=float(r["freq"]),
                directional_accuracy=float(r["dir_acc"]),
                rank_ic=float(r["ic"]),
                raw_p_value=float(r["p"]),
                fdr_q_value=float(q_vals[i]),
                mean_gross_return_bps=float(r["gross"]),
                mean_dynamic_cost_bps=float(r["cost"]),
                net_return_bps=float(r["net"]),
                ci_lower_bps=float(r["ci_l"]),
                ci_upper_bps=float(r["ci_u"]),
                classification=r["status"],
            ))

        return results
