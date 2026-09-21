"""Feature Quality, Information Gain, and Hypothesis Evaluation for Phase 9C.

Provides statistical auditing, redundancy detection, group ablations, multiple-testing
adjustments (Benjamini-Hochberg FDR, Bonferroni, Holm), and economic hurdle screening.
"""

from dataclasses import dataclass, asdict, field
import math
from typing import Dict, List, Tuple, Optional, Any
import numpy as np
import pandas as pd


def calc_corr_and_p(x: np.ndarray, y: np.ndarray) -> Tuple[float, float]:
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


def calc_spearman(x: np.ndarray, y: np.ndarray) -> Tuple[float, float]:
    """Calculates Spearman rank correlation and p-value."""
    if len(x) < 5:
        return 0.0, 1.0
    rx = pd.Series(x).rank().values
    ry = pd.Series(y).rank().values
    return calc_corr_and_p(rx, ry)


@dataclass
class FeatureQualityMetric:
    feature_name: str
    count: int
    missing_rate: float
    mean: float
    median: float
    std: float
    variance: float
    min_val: float
    max_val: float
    skewness: float
    kurtosis: float
    outlier_rate: float               # Fraction of values outside mean +/- 3*std
    is_constant: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class HypothesisEvaluationResult:
    hypothesis_id: str
    statement: str
    feature_tested: str
    target_tested: str
    horizon_bars: int
    sample_size: int
    pearson_r: float
    spearman_rho: float              # Information Coefficient (IC)
    p_value_raw: float
    p_value_fdr: float = 1.0
    p_value_bonferroni: float = 1.0
    p_value_holm: float = 1.0
    directional_accuracy: float = 0.50
    gross_edge_bps: float = 0.0
    economic_hurdle_bps: float = 40.0
    survives_fdr: bool = False
    survives_economic_gate: bool = False
    classification: str = "NOT_SUPPORTED"  # SUPPORTED, PARTIALLY_SUPPORTED, INCONCLUSIVE, NOT_SUPPORTED
    partition: str = "DEVELOPMENT"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MultipleTestingCorrector:
    """Adjusts p-values for multiple hypothesis testing."""

    @staticmethod
    def benjamini_hochberg(p_values: List[float], alpha: float = 0.05) -> Tuple[List[float], List[bool]]:
        """Benjamini-Hochberg FDR control.
        
        Returns:
            (adjusted_p_values, is_significant)
        """
        n = len(p_values)
        if n == 0:
            return [], []

        sorted_indices = np.argsort(p_values)
        sorted_p = np.array(p_values)[sorted_indices]
        
        # Calculate FDR adjusted p-values (q-values)
        q_values = np.zeros(n)
        q_values[-1] = sorted_p[-1]
        for i in range(n - 2, -1, -1):
            rank = i + 1
            adjusted = (sorted_p[i] * n) / rank
            q_values[i] = min(adjusted, q_values[i + 1])
        q_values = np.clip(q_values, 0.0, 1.0)

        # Restore original order
        adj_p = np.zeros(n)
        adj_p[sorted_indices] = q_values
        is_sig = [bool(p <= alpha) for p in adj_p]

        return list(adj_p), is_sig

    @staticmethod
    def bonferroni(p_values: List[float], alpha: float = 0.05) -> Tuple[List[float], List[bool]]:
        """Conservative Bonferroni family-wise error rate control."""
        n = len(p_values)
        adj_p = [min(1.0, p * n) for p in p_values]
        is_sig = [bool(p <= alpha) for p in adj_p]
        return adj_p, is_sig

    @staticmethod
    def holm_bonferroni(p_values: List[float], alpha: float = 0.05) -> Tuple[List[float], List[bool]]:
        """Holm step-down procedure."""
        n = len(p_values)
        if n == 0:
            return [], []
        sorted_indices = np.argsort(p_values)
        sorted_p = np.array(p_values)[sorted_indices]
        
        adj_sorted = np.zeros(n)
        for i in range(n):
            adj_sorted[i] = min(1.0, sorted_p[i] * (n - i))
        
        # Enforce monotonicity
        for i in range(1, n):
            adj_sorted[i] = max(adj_sorted[i], adj_sorted[i - 1])
            
        adj_p = np.zeros(n)
        adj_p[sorted_indices] = adj_sorted
        is_sig = [bool(p <= alpha) for p in adj_p]
        return list(adj_p), is_sig


class FeatureAuditor:
    """Performs comprehensive quality, redundancy, and diagnostic auditing on feature sets."""

    @staticmethod
    def audit_feature_quality(features_df: pd.DataFrame) -> List[FeatureQualityMetric]:
        """Calculates statistical health and distribution metrics for each feature."""
        metrics = []
        n = len(features_df)

        for col in features_df.columns:
            s = features_df[col].dropna()
            missing_rate = float((n - len(s)) / n) if n > 0 else 1.0

            if len(s) == 0:
                metrics.append(FeatureQualityMetric(
                    feature_name=col, count=0, missing_rate=missing_rate,
                    mean=0.0, median=0.0, std=0.0, variance=0.0,
                    min_val=0.0, max_val=0.0, skewness=0.0, kurtosis=0.0,
                    outlier_rate=0.0, is_constant=True,
                ))
                continue

            mean_val = float(s.mean())
            median_val = float(s.median())
            std_val = float(s.std(ddof=1)) if len(s) > 1 else 0.0
            var_val = float(s.var(ddof=1)) if len(s) > 1 else 0.0
            min_val = float(s.min())
            max_val = float(s.max())
            skew_val = float(s.skew()) if len(s) > 2 else 0.0
            kurt_val = float(s.kurtosis()) if len(s) > 3 else 0.0

            if std_val > 1e-12:
                outliers = ((s < mean_val - 3 * std_val) | (s > mean_val + 3 * std_val)).mean()
            else:
                outliers = 0.0

            is_const = (var_val < 1e-12) or (min_val == max_val)

            metrics.append(FeatureQualityMetric(
                feature_name=col,
                count=len(s),
                missing_rate=missing_rate,
                mean=mean_val,
                median=median_val,
                std=std_val,
                variance=var_val,
                min_val=min_val,
                max_val=max_val,
                skewness=skew_val,
                kurtosis=kurt_val,
                outlier_rate=float(outliers),
                is_constant=is_const,
            ))

        return metrics

    @staticmethod
    def identify_redundant_features(
        features_df: pd.DataFrame,
        correlation_threshold: float = 0.85,
    ) -> List[Tuple[str, str, float]]:
        """Finds pairs of features with absolute correlation exceeding threshold."""
        num_cols = [c for c in features_df.columns if pd.api.types.is_numeric_dtype(features_df[c])]
        corr = features_df[num_cols].corr().abs()
        redundant = []
        cols = list(corr.columns)
        for i in range(len(cols)):
            for j in range(i + 1, len(cols)):
                val = corr.iloc[i, j]
                if not np.isnan(val) and val >= correlation_threshold:
                    redundant.append((cols[i], cols[j], float(val)))
        return redundant


class DiagnosticBaselines:
    """Computes reference baseline benchmarks for sanity and falsification checks."""

    @staticmethod
    def evaluate_hold(returns: np.ndarray) -> Dict[str, float]:
        """Always HOLD (zero activity / zero directional edge)."""
        return {"baseline": "ALWAYS_HOLD", "directional_accuracy": 0.50, "mean_return_bps": 0.0}

    @staticmethod
    def evaluate_random(targets: np.ndarray, seed: int = 42) -> Dict[str, float]:
        """Uniform random direction baseline."""
        np.random.seed(seed)
        random_dir = np.random.choice([-1.0, 1.0], size=len(targets))
        accuracy = float(np.mean(random_dir == np.sign(targets)))
        return {"baseline": "RANDOM", "directional_accuracy": accuracy, "mean_return_bps": 0.0}

    @staticmethod
    def evaluate_momentum(past_returns: np.ndarray, forward_returns: np.ndarray) -> Dict[str, float]:
        """Simple momentum: sign(past_return) matches sign(forward_return)."""
        valid = ~(np.isnan(past_returns) | np.isnan(forward_returns))
        p = past_returns[valid]
        f = forward_returns[valid]
        accuracy = float(np.mean(np.sign(p) == np.sign(f))) if len(p) > 0 else 0.5
        mean_pnl = float(np.mean(np.sign(p) * f) * 10000.0) if len(p) > 0 else 0.0
        return {"baseline": "MOMENTUM", "directional_accuracy": accuracy, "mean_return_bps": mean_pnl}

    @staticmethod
    def evaluate_mean_reversion(past_returns: np.ndarray, forward_returns: np.ndarray) -> Dict[str, float]:
        """Simple mean reversion: -sign(past_return) matches sign(forward_return)."""
        valid = ~(np.isnan(past_returns) | np.isnan(forward_returns))
        p = past_returns[valid]
        f = forward_returns[valid]
        accuracy = float(np.mean(-np.sign(p) == np.sign(f))) if len(p) > 0 else 0.5
        mean_pnl = float(np.mean(-np.sign(p) * f) * 10000.0) if len(p) > 0 else 0.0
        return {"baseline": "MEAN_REVERSION", "directional_accuracy": accuracy, "mean_return_bps": mean_pnl}
