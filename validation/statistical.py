"""Statistical significance testing, expectancy, risk-adjusted metrics, and multiple-testing corrections.

Implements:
1. Strategy Expectancy calculation: E = (WinRate * AvgWin) - (LossRate * AvgLoss)
2. Directional Accuracy one-sample t-test vs 50% random baseline
3. Return t-test vs zero mean null hypothesis
4. Risk-adjusted metrics: Sharpe ratio, Sortino ratio, Calmar ratio (with explicit annualization parameters)
5. Multiple-testing corrections: Bonferroni correction and Benjamini-Hochberg False Discovery Rate (FDR)
"""

from dataclasses import dataclass
import math
from typing import List, Dict, Any, Tuple, Optional
import numpy as np


@dataclass
class SignificanceTestResult:
    test_name: str
    sample_size: int
    observed_value: float
    null_value: float
    t_statistic: float
    raw_p_value: float
    is_statistically_significant: bool  # at alpha = 0.05
    interpretation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_name": self.test_name,
            "sample_size": self.sample_size,
            "observed_value": round(self.observed_value, 4),
            "null_value": round(self.null_value, 4),
            "t_statistic": round(self.t_statistic, 4),
            "raw_p_value": round(self.raw_p_value, 6),
            "is_statistically_significant": self.is_statistically_significant,
            "interpretation": self.interpretation,
        }


def normal_cdf(x: float) -> float:
    """Standard normal cumulative distribution function."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def calculate_t_test_one_sample(
    values: np.ndarray,
    null_mean: float = 0.0,
    alternative: str = "greater",
) -> Tuple[float, float]:
    """Calculates one-sample t-statistic and p-value (using standard normal approximation for large N)."""
    n = len(values)
    if n < 2:
        return 0.0, 1.0

    sample_mean = float(np.mean(values))
    sample_std = float(np.std(values, ddof=1))

    if sample_std <= 0:
        return 0.0, 1.0

    se = sample_std / math.sqrt(n)
    t_stat = (sample_mean - null_mean) / se

    # One-sided or two-sided p-value
    if alternative == "greater":
        p_val = 1.0 - normal_cdf(t_stat)
    elif alternative == "two-sided":
        p_val = 2.0 * (1.0 - normal_cdf(abs(t_stat)))
    else:
        p_val = normal_cdf(t_stat)

    return t_stat, max(0.0, min(1.0, p_val))


def calculate_expectancy(trades_net_pnl: List[float]) -> Dict[str, float]:
    """Calculates trade expectancy: E = (WinRate * AvgWin) - (LossRate * AvgLoss)."""
    if not trades_net_pnl:
        return {"expectancy": 0.0, "win_rate": 0.0, "avg_win": 0.0, "avg_loss": 0.0}

    n = len(trades_net_pnl)
    wins = [p for p in trades_net_pnl if p > 0]
    losses = [abs(p) for p in trades_net_pnl if p < 0]

    win_rate = len(wins) / n
    loss_rate = len(losses) / n
    avg_win = float(np.mean(wins)) if wins else 0.0
    avg_loss = float(np.mean(losses)) if losses else 0.0

    expectancy = (win_rate * avg_win) - (loss_rate * avg_loss)

    return {
        "expectancy": expectancy,
        "win_rate": win_rate * 100.0,
        "loss_rate": loss_rate * 100.0,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
    }


def calculate_risk_adjusted_ratios(
    equity_curve: List[float],
    annualization_factor: float = math.sqrt(252 * 288),  # 5-min candles in crypto year (252*288 periods)
    risk_free_rate: float = 0.0,
) -> Dict[str, float]:
    """Computes Sharpe, Sortino, and Calmar ratios from equity curve."""
    if len(equity_curve) < 2:
        return {"sharpe_ratio": 0.0, "sortino_ratio": 0.0, "calmar_ratio": 0.0}

    eq = np.array(equity_curve)
    returns = np.diff(eq) / eq[:-1]

    mean_ret = float(np.mean(returns))
    std_ret = float(np.std(returns, ddof=1)) if len(returns) > 1 else 0.0

    # Downside deviation for Sortino
    downside_returns = returns[returns < 0]
    downside_std = float(np.std(downside_returns, ddof=1)) if len(downside_returns) > 1 else std_ret

    sharpe = (mean_ret / std_ret * annualization_factor) if std_ret > 0 else 0.0
    sortino = (mean_ret / downside_std * annualization_factor) if downside_std > 0 else 0.0

    # Calmar ratio: Total return / Max drawdown
    peak = np.maximum.accumulate(eq)
    drawdowns = (peak - eq) / peak
    max_dd = float(np.max(drawdowns)) if len(drawdowns) > 0 else 0.0
    total_ret = (eq[-1] - eq[0]) / eq[0]
    calmar = (total_ret / max_dd) if max_dd > 0 else 0.0

    return {
        "sharpe_ratio": round(sharpe, 4),
        "sortino_ratio": round(sortino, 4),
        "calmar_ratio": round(calmar, 4),
    }


def apply_multiple_testing_corrections(
    p_values: List[float],
    alpha: float = 0.05,
) -> Dict[str, Any]:
    """Applies Bonferroni and Benjamini-Hochberg (FDR) corrections to a set of p-values."""
    k = len(p_values)
    if k == 0:
        return {"bonferroni_threshold": alpha, "bonferroni_significant": [], "fdr_significant": []}

    # Bonferroni: alpha / k
    bonferroni_thresh = alpha / k
    bonf_sig = [p <= bonferroni_thresh for p in p_values]

    # Benjamini-Hochberg FDR procedure:
    # Sort p-values: p_(1) <= p_(2) <= ... <= p_(k)
    # Find largest i where p_(i) <= (i / k) * alpha
    sorted_indices = np.argsort(p_values)
    sorted_p = np.array(p_values)[sorted_indices]

    fdr_thresholds = np.array([(i + 1) / k * alpha for i in range(k)])
    qualifying = sorted_p <= fdr_thresholds

    max_sig_idx = -1
    for i in range(k - 1, -1, -1):
        if qualifying[i]:
            max_sig_idx = i
            break

    fdr_sig = [False] * k
    if max_sig_idx >= 0:
        for i in range(max_sig_idx + 1):
            original_idx = sorted_indices[i]
            fdr_sig[original_idx] = True

    return {
        "hypotheses_tested_count": k,
        "nominal_alpha": alpha,
        "bonferroni_threshold": bonferroni_thresh,
        "bonferroni_significant": bonf_sig,
        "fdr_significant": fdr_sig,
        "adjusted_p_values_fdr": [min(1.0, p * k / (i + 1)) for i, p in enumerate(sorted_p)],
    }
