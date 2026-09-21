"""Cross-Asset Causal Lead-Lag Analysis Engine for Phase 9C.

Evaluates directional lead-lag dynamics and information transmission between
independent asset pairs (BTCUSDT, ETHUSDT, SOLUSDT).
"""

from dataclasses import dataclass, asdict
import math
from typing import Dict, List, Tuple, Any, Optional
import numpy as np
import pandas as pd


def _calc_corr_and_p(x: np.ndarray, y: np.ndarray) -> Tuple[float, float]:
    """Calculates Pearson correlation and two-tailed p-value."""
    if len(x) < 5:
        return 0.0, 1.0
    vx = np.std(x)
    vy = np.std(y)
    if vx < 1e-12 or vy < 1e-12:
        return 0.0, 1.0
    r = float(np.corrcoef(x, y)[0, 1])
    if np.isnan(r):
        return 0.0, 1.0
    r = max(-1.0, min(1.0, r))
    if abs(r) >= 1.0:
        return r, 0.0
    n = len(x)
    t = r * math.sqrt((n - 2) / (1.0 - r**2))
    p_val = math.erfc(abs(t) / math.sqrt(2))
    return r, float(p_val)


def _calc_spearman(x: np.ndarray, y: np.ndarray) -> Tuple[float, float]:
    """Calculates Spearman rank correlation and p-value."""
    if len(x) < 5:
        return 0.0, 1.0
    rx = pd.Series(x).rank().values
    ry = pd.Series(y).rank().values
    return _calc_corr_and_p(rx, ry)


@dataclass
class LeadLagPairResult:
    lead_asset: str
    lag_asset: str
    contemporaneous_corr: float
    contemporaneous_spearman: float
    lead_correlations: Dict[int, float]        # lag_k -> correlation(lead_t, lag_{t+k})
    lead_spearmans: Dict[int, float]           # lag_k -> spearman(lead_t, lag_{t+k})
    lead_p_values: Dict[int, float]
    optimal_lag_bars: int
    optimal_correlation: float
    optimal_p_value: float
    is_predictive: bool                        # statistically significant lag correlation (p < 0.05)
    interpretation: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class LeadLagEngine:
    """Analyzes cross-asset lead-lag relationships across causal temporal horizons."""

    EVALUATION_LAGS = [1, 2, 3, 6, 12, 24, 48]  # 5m, 10m, 15m, 30m, 1h, 2h, 4h

    @classmethod
    def analyze_pair(
        cls,
        df_a: pd.DataFrame,
        df_b: pd.DataFrame,
        asset_a: str = "BTC",
        asset_b: str = "ETH",
        lags: Optional[List[int]] = None,
    ) -> Tuple[LeadLagPairResult, LeadLagPairResult]:
        """Analyzes bidirectional lead-lag dynamics between asset_a and asset_b.
        
        Returns:
            (result_a_leads_b, result_b_leads_a)
        """
        lags = lags or cls.EVALUATION_LAGS

        # Align on timestamps
        merged = pd.merge(
            df_a[["timestamp", "close"]].rename(columns={"close": "close_a"}),
            df_b[["timestamp", "close"]].rename(columns={"close": "close_b"}),
            on="timestamp",
            how="inner",
        ).sort_values("timestamp").reset_index(drop=True)

        ret_a = np.log(merged["close_a"] / merged["close_a"].shift(1))
        ret_b = np.log(merged["close_b"] / merged["close_b"].shift(1))

        valid_mask = ~(ret_a.isna() | ret_b.isna())
        r_a = ret_a[valid_mask].values
        r_b = ret_b[valid_mask].values

        contemp_r, _ = _calc_corr_and_p(r_a, r_b)
        contemp_rho, _ = _calc_spearman(r_a, r_b)

        def _evaluate_directional(lead_ret: np.ndarray, lag_ret: np.ndarray, name_lead: str, name_lag: str) -> LeadLagPairResult:
            lead_corrs = {}
            lead_spears = {}
            lead_pvals = {}

            best_lag = 0
            best_abs_corr = 0.0
            best_corr = 0.0
            best_pval = 1.0

            n = len(lead_ret)
            for k in lags:
                if k >= n:
                    continue
                # Predict lag at t+k using lead at t:
                x = lead_ret[:-k]
                y = lag_ret[k:]
                if len(x) < 30:
                    continue
                r, p_val = _calc_corr_and_p(x, y)
                rho, _ = _calc_spearman(x, y)
                lead_corrs[k] = float(r)
                lead_spears[k] = float(rho)
                lead_pvals[k] = float(p_val)

                if abs(r) > best_abs_corr:
                    best_abs_corr = abs(r)
                    best_corr = float(r)
                    best_lag = k
                    best_pval = float(p_val)

            is_pred = (best_pval < 0.05 and best_abs_corr > 0.02)
            interpretation = (
                f"{name_lead} leads {name_lag} at lag {best_lag} bars (r={best_corr:.4f}, p={best_pval:.4e})"
                if is_pred
                else f"No significant predictive lead from {name_lead} to {name_lag} (max r={best_corr:.4f})"
            )

            return LeadLagPairResult(
                lead_asset=name_lead,
                lag_asset=name_lag,
                contemporaneous_corr=float(contemp_r),
                contemporaneous_spearman=float(contemp_rho),
                lead_correlations=lead_corrs,
                lead_spearmans=lead_spears,
                lead_p_values=lead_pvals,
                optimal_lag_bars=best_lag,
                optimal_correlation=best_corr,
                optimal_p_value=best_pval,
                is_predictive=is_pred,
                interpretation=interpretation,
            )

        res_a_leads_b = _evaluate_directional(r_a, r_b, asset_a, asset_b)
        res_b_leads_a = _evaluate_directional(r_b, r_a, asset_b, asset_a)

        return res_a_leads_b, res_b_leads_a
