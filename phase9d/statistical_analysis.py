"""Statistical Analysis Module for Phase 9D Microstructure Research.

Provides:
1. Block bootstrap confidence intervals
2. Permutation test for incremental AUC
3. Rank correlation & t-test statistics
4. Benjamini-Hochberg FDR and Holm-Bonferroni FWER corrections
5. Calibration metrics (Brier score, ECE)
"""

from dataclasses import dataclass, asdict
import math
from typing import Dict, List, Tuple, Optional, Any
import numpy as np
import pandas as pd


def calc_corr_and_p(x: np.ndarray, y: np.ndarray) -> Tuple[float, float]:
    """Calculates Pearson r and two-tailed p-value."""
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


def compute_auc(y_true_binary: np.ndarray, y_score: np.ndarray) -> float:
    """Computes Area Under the ROC Curve (AUC) via Wilcoxon-Mann-Whitney rank sum."""
    pos_mask = (y_true_binary == 1)
    neg_mask = (y_true_binary == 0)
    n_pos = np.sum(pos_mask)
    n_neg = np.sum(neg_mask)

    if n_pos == 0 or n_neg == 0:
        return 0.50

    ranks = pd.Series(y_score).rank().values
    sum_ranks_pos = np.sum(ranks[pos_mask])
    u = sum_ranks_pos - (n_pos * (n_pos + 1)) / 2.0
    auc = u / (n_pos * n_neg)
    return float(np.clip(auc, 0.0, 1.0))


def compute_brier_score(y_true_binary: np.ndarray, y_prob: np.ndarray) -> float:
    """Mean squared error between binary outcomes and predicted probabilities."""
    return float(np.mean((y_prob - y_true_binary) ** 2))


def block_bootstrap_delta_auc(
    y_true: np.ndarray,
    scores_base: np.ndarray,
    scores_enhanced: np.ndarray,
    block_size: int = 48,
    n_replications: int = 500,
    seed: int = 42,
) -> Tuple[float, float, float, float]:
    """Computes block bootstrap 95% confidence interval for Delta_AUC (Enhanced - Base).
    
    Returns:
        (delta_auc_mean, ci_lower, ci_upper, p_value)
    """
    n = len(y_true)
    if n < block_size * 2:
        return 0.0, 0.0, 0.0, 1.0

    base_auc = compute_auc(y_true, scores_base)
    enh_auc = compute_auc(y_true, scores_enhanced)
    obs_delta = enh_auc - base_auc

    np.random.seed(seed)
    n_blocks = int(np.ceil(n / block_size))
    boot_deltas = []

    for _ in range(n_replications):
        block_starts = np.random.randint(0, n - block_size + 1, size=n_blocks)
        indices = np.concatenate([np.arange(s, s + block_size) for s in block_starts])[:n]

        y_b = y_true[indices]
        s_base_b = scores_base[indices]
        s_enh_b = scores_enhanced[indices]

        if len(np.unique(y_b)) < 2:
            continue

        d = compute_auc(y_b, s_enh_b) - compute_auc(y_b, s_base_b)
        boot_deltas.append(d)

    if not boot_deltas:
        return obs_delta, obs_delta, obs_delta, 1.0

    boot_deltas = np.array(boot_deltas)
    ci_lower = float(np.percentile(boot_deltas, 2.5))
    ci_upper = float(np.percentile(boot_deltas, 97.5))

    # Two-sided empirical p-value for H0: Delta_AUC <= 0
    p_val = float(np.mean(boot_deltas <= 0.0)) * 2.0
    p_val = min(1.0, max(1e-5, p_val))

    return obs_delta, ci_lower, ci_upper, p_val


class MultipleTesting:
    """Multiple hypothesis testing adjustments."""

    @staticmethod
    def benjamini_hochberg(p_values: List[float], alpha: float = 0.05) -> Tuple[List[float], List[bool]]:
        """Benjamini-Hochberg FDR control."""
        n = len(p_values)
        if n == 0:
            return [], []

        sorted_indices = np.argsort(p_values)
        sorted_p = np.array(p_values)[sorted_indices]

        q_values = np.zeros(n)
        q_values[-1] = sorted_p[-1]
        for i in range(n - 2, -1, -1):
            rank = i + 1
            adjusted = (sorted_p[i] * n) / rank
            q_values[i] = min(adjusted, q_values[i + 1])
        q_values = np.clip(q_values, 0.0, 1.0)

        adj_p = np.zeros(n)
        adj_p[sorted_indices] = q_values
        is_sig = [bool(p <= alpha) for p in adj_p]
        return list(adj_p), is_sig

    @staticmethod
    def holm_bonferroni(p_values: List[float], alpha: float = 0.05) -> Tuple[List[float], List[bool]]:
        """Holm step-down FWER control."""
        n = len(p_values)
        if n == 0:
            return [], []
        sorted_indices = np.argsort(p_values)
        sorted_p = np.array(p_values)[sorted_indices]

        adj_sorted = np.zeros(n)
        for i in range(n):
            adj_sorted[i] = min(1.0, sorted_p[i] * (n - i))

        for i in range(1, n):
            adj_sorted[i] = max(adj_sorted[i], adj_sorted[i - 1])

        adj_p = np.zeros(n)
        adj_p[sorted_indices] = adj_sorted
        is_sig = [bool(p <= alpha) for p in adj_p]
        return list(adj_p), is_sig
