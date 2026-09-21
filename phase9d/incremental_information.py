"""Incremental Information Evaluation Module for Phase 9D.

Implements controlled statistical comparison:
Baseline A (Phase 9C features only) vs Model B (Phase 9C + Microstructure).
Measures:
- Delta AUC
- Delta Brier Score
- Delta Rank IC
- Delta Directional Accuracy
- Delta Gross & Net Expectancy
- Block Bootstrap 95% Confidence Intervals
"""

from dataclasses import dataclass, asdict
from typing import Dict, List, Tuple, Optional, Any
import numpy as np
import pandas as pd

from phase9d.statistical_analysis import (
    compute_auc,
    compute_brier_score,
    block_bootstrap_delta_auc,
    calc_spearman,
)
from phase9d.economic_analysis import DualEconomicGate


@dataclass
class IncrementalComparisonResult:
    target_name: str
    horizon_bars: int
    n_samples: int
    auc_baseline_a: float
    auc_model_b: float
    delta_auc: float
    delta_auc_ci_lower: float
    delta_auc_ci_upper: float
    delta_auc_p_value: float
    brier_baseline_a: float
    brier_model_b: float
    delta_brier: float
    dir_acc_baseline_a: float
    dir_acc_model_b: float
    delta_dir_acc: float
    rank_ic_baseline_a: float
    rank_ic_model_b: float
    delta_rank_ic: float
    gross_edge_baseline_bps: float
    gross_edge_model_bps: float
    delta_gross_edge_bps: float
    net_edge_baseline_bps: float
    net_edge_model_bps: float
    delta_net_edge_bps: float
    is_statistically_incremental: bool
    is_economically_incremental: bool
    classification: str  # SUPPORTED, PARTIALLY_SUPPORTED, ECONOMICALLY_INSUFFICIENT, REJECTED

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SimpleLinearClassifier:
    """Interpretable, deterministic regularized linear model for diagnostic benchmarking."""

    def __init__(self, l2_reg: float = 1.0):
        self.l2_reg = l2_reg
        self.weights: Optional[np.ndarray] = None
        self.bias: float = 0.0

    def fit(self, X: np.ndarray, y: np.ndarray) -> "SimpleLinearClassifier":
        """Fits ridge regression weights on continuous/binary targets."""
        n, p = X.shape
        # Standardize features using training data only
        mean = np.mean(X, axis=0)
        std = np.std(X, axis=0) + 1e-9
        X_norm = (X - mean) / std

        # Closed-form regularized solution
        XtX = X_norm.T @ X_norm + self.l2_reg * np.eye(p)
        Xty = X_norm.T @ y
        self.weights = np.linalg.solve(XtX, Xty) / std
        self.bias = float(np.mean(y) - np.sum(self.weights * mean))
        return self

    def predict_score(self, X: np.ndarray) -> np.ndarray:
        """Outputs continuous linear score / decision value."""
        return X @ self.weights + self.bias

    def predict_prob(self, X: np.ndarray) -> np.ndarray:
        """Converts score to calibrated probability via sigmoid."""
        z = np.clip(self.predict_score(X), -15.0, 15.0)
        return 1.0 / (1.0 + np.exp(-z))


class IncrementalInformationEvaluator:
    """Evaluates whether microstructure features provide incremental value over Phase 9C."""

    def __init__(self, dual_gate: Optional[DualEconomicGate] = None):
        self.dual_gate = dual_gate or DualEconomicGate()

    def compare_models(
        self,
        features_base_train: pd.DataFrame,
        features_enhanced_train: pd.DataFrame,
        y_train_return: pd.Series,
        features_base_test: pd.DataFrame,
        features_enhanced_test: pd.DataFrame,
        y_test_return: pd.Series,
        target_name: str = "target_dir_1",
        horizon_bars: int = 1,
        spread_bps_test: Optional[pd.Series] = None,
    ) -> IncrementalComparisonResult:
        """Fits Baseline A and Model B on train data and compares performance on test data."""
        # Align training data
        idx_train = features_enhanced_train.dropna().index.intersection(y_train_return.dropna().index)
        X_base_tr = features_base_train.loc[idx_train].values
        X_enh_tr = features_enhanced_train.loc[idx_train].values
        y_tr = y_train_return.loc[idx_train].values
        y_tr_binary = (y_tr > 0).astype(float)

        # Align test data
        idx_test = features_enhanced_test.dropna().index.intersection(y_test_return.dropna().index)
        X_base_te = features_base_test.loc[idx_test].values
        X_enh_te = features_enhanced_test.loc[idx_test].values
        y_te = y_test_return.loc[idx_test].values
        y_te_binary = (y_te > 0).astype(float)

        n_samples = len(idx_test)
        if n_samples < 50:
            raise ValueError(f"Insufficient test samples ({n_samples}) for incremental evaluation.")

        # Fit models strictly on training set
        clf_base = SimpleLinearClassifier(l2_reg=10.0).fit(X_base_tr, y_tr_binary)
        clf_enh = SimpleLinearClassifier(l2_reg=10.0).fit(X_enh_tr, y_tr_binary)

        # Predict on test set
        scores_base = clf_base.predict_score(X_base_te)
        scores_enh = clf_enh.predict_score(X_enh_te)
        probs_base = clf_base.predict_prob(X_base_te)
        probs_enh = clf_enh.predict_prob(X_enh_te)

        # 1. AUC comparison
        auc_base = compute_auc(y_te_binary, scores_base)
        auc_enh = compute_auc(y_te_binary, scores_enh)
        delta_auc, ci_l, ci_u, p_auc = block_bootstrap_delta_auc(
            y_te_binary, scores_base, scores_enh, block_size=24, n_replications=300, seed=42
        )

        # 2. Brier score comparison
        brier_base = compute_brier_score(y_te_binary, probs_base)
        brier_enh = compute_brier_score(y_te_binary, probs_enh)
        delta_brier = brier_enh - brier_base  # negative is improvement

        # 3. Directional accuracy
        dir_base = float(np.mean((scores_base > 0) == y_te_binary))
        dir_enh = float(np.mean((scores_enh > 0) == y_te_binary))
        delta_dir = dir_enh - dir_base

        # 4. Rank IC with forward return
        ic_base, _ = calc_spearman(scores_base, y_te)
        ic_enh, _ = calc_spearman(scores_enh, y_te)
        delta_ic = ic_enh - ic_base

        # 5. Economic expectancies
        gross_base = float(np.mean(np.sign(scores_base) * y_te) * 10000.0)
        gross_enh = float(np.mean(np.sign(scores_enh) * y_te) * 10000.0)
        delta_gross = gross_enh - gross_base

        # Dynamic friction
        mean_spread = float(spread_bps_test.loc[idx_test].mean()) if spread_bps_test is not None else 5.0
        cost_eval = self.dual_gate.compute_dynamic_cost(spread_bps=mean_spread)
        dyn_hurdle = cost_eval.total_dynamic_hurdle_bps

        net_base = gross_base - dyn_hurdle
        net_enh = gross_enh - dyn_hurdle
        delta_net = net_enh - net_base

        is_stat = bool(delta_auc > 0.01 and ci_l > 0.0 and p_auc < 0.05)
        is_econ = bool(net_enh > 0.0 and delta_net > 0.0)

        if is_stat and is_econ:
            classification = "SUPPORTED"
        elif is_stat and not is_econ:
            classification = "ECONOMICALLY_INSUFFICIENT"
        elif delta_auc > 0.005:
            classification = "PARTIALLY_SUPPORTED"
        else:
            classification = "REJECTED"

        return IncrementalComparisonResult(
            target_name=target_name,
            horizon_bars=horizon_bars,
            n_samples=n_samples,
            auc_baseline_a=float(auc_base),
            auc_model_b=float(auc_enh),
            delta_auc=float(delta_auc),
            delta_auc_ci_lower=float(ci_l),
            delta_auc_ci_upper=float(ci_u),
            delta_auc_p_value=float(p_auc),
            brier_baseline_a=float(brier_base),
            brier_model_b=float(brier_enh),
            delta_brier=float(delta_brier),
            dir_acc_baseline_a=float(dir_base),
            dir_acc_model_b=float(dir_enh),
            delta_dir_acc=float(delta_dir),
            rank_ic_baseline_a=float(ic_base),
            rank_ic_model_b=float(ic_enh),
            delta_rank_ic=float(delta_ic),
            gross_edge_baseline_bps=float(gross_base),
            gross_edge_model_bps=float(gross_enh),
            delta_gross_edge_bps=float(delta_gross),
            net_edge_baseline_bps=float(net_base),
            net_edge_model_bps=float(net_enh),
            delta_net_edge_bps=float(delta_net),
            is_statistically_incremental=is_stat,
            is_economically_incremental=is_econ,
            classification=classification,
        )
