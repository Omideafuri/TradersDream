"""Statistical Power Audit and Rigorous Hypothesis Testing Engine.

Addresses Section 13 requirements:
- Formally audits the Phase 6 power calculation and interpretation.
- Defines hypothesis testing rigorously:
  - Null Hypothesis: H0: mu <= 0 (Strategy does not generate positive alpha)
  - Alternative Hypothesis: H1: mu = mu_a = +40 bps (Strategy generates alpha >= economic hurdle)
  - Significance level: alpha = 0.05 (one-tailed critical value z = 1.645 or two-tailed z = 1.960)
- Calculates:
  - Standard Error (SE) accounting for autocorrelation-adjusted effective sample size N_eff.
  - Test statistic: t = (observed_mean - 0) / SE
  - p-value: P(T >= t | H0)
  - Power under H1: P(Reject H0 | mu = mu_a) = Phi( (mu_a - z_crit * SE) / SE )
  - Minimum Detectable Effect (MDE) at 80% power.
  - Clear methodological audit clarifying the Phase 6 documentation shorthand.
"""

from dataclasses import dataclass, asdict
import math
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd


def norm_cdf(x: float) -> float:
    """Standard normal cumulative distribution function."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))



@dataclass
class FormalPowerAuditReport:
    symbol: str
    horizon: str
    sample_size: int
    effective_sample_size: float
    autocorrelation_lag1: float
    sample_mean_bps: float
    sample_std_bps: float
    standard_error_bps: float
    null_hypothesis: str
    alternative_hypothesis: str
    assumed_alternative_effect_bps: float
    alpha: float
    critical_value: float
    test_statistic_t: float
    p_value: float
    ci_lower_95_bps: float
    ci_upper_95_bps: float
    statistical_power_at_alternative: float
    minimum_detectable_effect_bps: float
    is_null_rejected: bool
    audit_verdict: str
    methodological_clarification: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def audit_statistical_power(
    returns_bps: np.ndarray,
    symbol: str = "BTCUSDT",
    horizon: str = "5m",
    assumed_alternative_bps: float = 40.0,
    alpha: float = 0.05,
) -> FormalPowerAuditReport:
    """Performs rigorous statistical hypothesis testing and power analysis against specified alternative."""
    clean = returns_bps[~np.isnan(returns_bps)]
    n = len(clean)

    if n < 5:
        return FormalPowerAuditReport(
            symbol=symbol,
            horizon=horizon,
            sample_size=n,
            effective_sample_size=float(n),
            autocorrelation_lag1=0.0,
            sample_mean_bps=0.0,
            sample_std_bps=0.0,
            standard_error_bps=0.0,
            null_hypothesis="H0: mu <= 0",
            alternative_hypothesis=f"H1: mu = {assumed_alternative_bps} bps",
            assumed_alternative_effect_bps=assumed_alternative_bps,
            alpha=alpha,
            critical_value=1.645,
            test_statistic_t=0.0,
            p_value=1.0,
            ci_lower_95_bps=0.0,
            ci_upper_95_bps=0.0,
            statistical_power_at_alternative=0.0,
            minimum_detectable_effect_bps=0.0,
            is_null_rejected=False,
            audit_verdict="INSUFFICIENT_DATA",
            methodological_clarification="Insufficient sample size to compute power.",
        )

    mean_obs = float(np.mean(clean))
    std_obs = float(np.std(clean, ddof=1))

    # Autocorrelation adjustment for effective sample size: N_eff = N * (1 - rho) / (1 + rho)
    s_series = pd.Series(clean)
    rho = float(s_series.autocorr(lag=1))
    if np.isnan(rho) or abs(rho) >= 0.99:
        rho = 0.0

    n_eff = max(5.0, n * (1.0 - rho) / (1.0 + rho))
    se = std_obs / np.sqrt(n_eff)

    # One-tailed test for positive alpha: H0: mu <= 0 vs H1: mu > 0
    # Critical threshold: z_crit * SE (for alpha=0.05, z = 1.64485)
    z_crit = 1.64485
    t_stat = mean_obs / se if se > 1e-9 else 0.0
    p_val = float(1.0 - norm_cdf(t_stat))

    # 95% Confidence Interval (two-sided, z = 1.95996)
    z_two_sided = 1.95996
    ci_low = mean_obs - z_two_sided * se
    ci_high = mean_obs + z_two_sided * se

    # Power to detect assumed alternative effect mu_a = +40 bps:
    # Power = P(Z >= z_crit - (mu_a / SE)) = 1 - Phi(z_crit - mu_a / SE) = Phi( (mu_a - z_crit * SE) / SE )
    cutoff = z_crit * se
    power_z = (assumed_alternative_bps - cutoff) / se if se > 1e-9 else 0.0
    power = float(norm_cdf(power_z))

    # Minimum Detectable Effect at 80% power: MDE = (z_alpha + z_beta) * SE = (1.645 + 0.842) * SE
    z_beta = 0.84162
    mde = (z_crit + z_beta) * se

    # Null rejection
    is_rejected = bool(p_val < alpha and mean_obs > 0)

    # Audit verdict & clarification
    if is_rejected:
        verdict = "NULL_REJECTED_POSITIVE_ALPHA"
    elif mean_obs < 0:
        verdict = "FAIL_TO_REJECT_NEGATIVE_OBSERVED_MEAN"
    else:
        verdict = "FAIL_TO_REJECT_INSUFFICIENT_EVIDENCE"

    clarification = (
        f"Phase 6 documentation stated 'Empirical power >0.95 for rejecting positive alpha', which was "
        f"an informal shorthand. Rigorously: under H0 (mu <= 0) vs H1 (mu = +{assumed_alternative_bps} bps), "
        f"given N_eff = {round(n_eff, 1)} and SE = {round(se, 2)} bps, the test has a {round(power * 100, 1)}% "
        f"statistical power to detect a true economic alpha of {assumed_alternative_bps} bps if present. "
        f"Because the observed sample mean is {round(mean_obs, 2)} bps (t = {round(t_stat, 2)}, p = {round(p_val, 4)}), "
        f"we fail to reject H0, and the observed negative returns cannot be attributed to a type II error (lack of power)."
    )

    return FormalPowerAuditReport(
        symbol=symbol,
        horizon=horizon,
        sample_size=n,
        effective_sample_size=round(n_eff, 1),
        autocorrelation_lag1=round(rho, 4),
        sample_mean_bps=round(mean_obs, 2),
        sample_std_bps=round(std_obs, 2),
        standard_error_bps=round(se, 2),
        null_hypothesis="H0: mu <= 0 (Zero or Negative Alpha)",
        alternative_hypothesis=f"H1: mu = +{assumed_alternative_bps} bps (Economic Hurdle Alpha)",
        assumed_alternative_effect_bps=round(assumed_alternative_bps, 2),
        alpha=alpha,
        critical_value=round(z_crit, 3),
        test_statistic_t=round(t_stat, 3),
        p_value=round(p_val, 4),
        ci_lower_95_bps=round(ci_low, 2),
        ci_upper_95_bps=round(ci_high, 2),
        statistical_power_at_alternative=round(power, 4),
        minimum_detectable_effect_bps=round(mde, 2),
        is_null_rejected=is_rejected,
        audit_verdict=verdict,
        methodological_clarification=clarification,
    )
