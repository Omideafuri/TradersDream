"""Causal Leakage Guard and Perturbation Testing module for Phase 9.

Implements rigorous future-data perturbation tests:
Given an input DataFrame at bar t, modifying future bars t+1...t+k
MUST NOT alter any feature, indicator, market state, or signal computed at bar t.
"""

from typing import Callable, Dict, Any, List
import copy
import numpy as np
import pandas as pd


class LeakageViolationError(Exception):
    """Raised when future data leakage is detected during causality testing."""
    pass


class LeakageGuard:
    """Automated causality and future-information leakage test harness."""

    @staticmethod
    def test_future_perturbation(
        df: pd.DataFrame,
        feature_calculator_fn: Callable[[pd.DataFrame], pd.DataFrame | Dict[str, Any]],
        target_bar_idx: int = 50,
        perturbation_bars: int = 20,
        noise_magnitude: float = 1000.0,
    ) -> Dict[str, Any]:
        """Tests whether perturbing future data (t+1..t+k) changes features calculated at t.
        
        Args:
            df: Historical input DataFrame.
            feature_calculator_fn: Function that takes a DataFrame and returns features/state.
            target_bar_idx: The index t where features should remain invariant.
            perturbation_bars: How many future bars to perturb (t+1 to t+perturbation_bars).
            noise_magnitude: Price shock applied to future bars.
            
        Returns:
            Dict containing test verdict and max observed delta.
        """
        if len(df) <= target_bar_idx + perturbation_bars:
            raise ValueError(
                f"DataFrame length ({len(df)}) must exceed target_bar_idx + perturbation_bars "
                f"({target_bar_idx + perturbation_bars})."
            )

        # 1. Base calculation
        base_df = df.copy()
        base_res = feature_calculator_fn(base_df)

        # 2. Perturbed future calculation
        perturbed_df = df.copy()
        future_slice = slice(target_bar_idx + 1, target_bar_idx + 1 + perturbation_bars)
        # Apply shocks to OHLC and Volume
        perturbed_df.loc[future_slice, "open"] += noise_magnitude
        perturbed_df.loc[future_slice, "high"] += noise_magnitude * 1.5
        perturbed_df.loc[future_slice, "low"] = np.maximum(1.0, perturbed_df.loc[future_slice, "low"] - noise_magnitude * 0.5)
        perturbed_df.loc[future_slice, "close"] += noise_magnitude * 1.2
        if "volume" in perturbed_df.columns:
            perturbed_df.loc[future_slice, "volume"] *= 5.0

        perturbed_res = feature_calculator_fn(perturbed_df)

        # 3. Compare values at target_bar_idx
        max_delta = 0.0
        discrepancies = []

        if isinstance(base_res, pd.DataFrame):
            for col in base_res.columns:
                val_base = base_res[col].iloc[target_bar_idx]
                val_pert = perturbed_res[col].iloc[target_bar_idx]
                if pd.isna(val_base) and pd.isna(val_pert):
                    continue
                if isinstance(val_base, (int, float, np.number)):
                    delta = abs(float(val_base) - float(val_pert))
                    if delta > max_delta:
                        max_delta = delta
                    if delta > 1e-9:
                        discrepancies.append((col, val_base, val_pert, delta))
                else:
                    if val_base != val_pert:
                        discrepancies.append((col, val_base, val_pert, "non_numeric_mismatch"))
        elif isinstance(base_res, dict):
            for k, val_base in base_res.items():
                val_pert = perturbed_res.get(k)
                if isinstance(val_base, (int, float, np.number)):
                    delta = abs(float(val_base) - float(val_pert))
                    if delta > max_delta:
                        max_delta = delta
                    if delta > 1e-9:
                        discrepancies.append((k, val_base, val_pert, delta))
                elif val_base != val_pert:
                    discrepancies.append((k, val_base, val_pert, "mismatch"))

        is_causal = (len(discrepancies) == 0 and max_delta < 1e-9)

        return {
            "is_causal": is_causal,
            "max_delta": max_delta,
            "target_bar_idx": target_bar_idx,
            "perturbation_bars": perturbation_bars,
            "discrepancies": discrepancies,
            "status": "PASS" if is_causal else "FAIL_LEAKAGE_DETECTED",
        }

    @staticmethod
    def verify_timestamp_causality(
        feature_timestamps: np.ndarray | List[int],
        source_timestamps: np.ndarray | List[int],
    ) -> bool:
        """Verifies that no feature timestamp references source data ahead in time."""
        feat_arr = np.asarray(feature_timestamps)
        src_arr = np.asarray(source_timestamps)
        if len(feat_arr) != len(src_arr):
            return False
        # feature at index i must not exceed source timestamp at index i
        return bool(np.all(feat_arr <= src_arr))
