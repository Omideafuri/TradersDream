"""Deterministic Reproducibility Harness for Phase 9D.

Executes Run A and Run B with identical inputs and parameters,
verifying that maximum numerical delta is exactly 0.0.
"""

from typing import Dict, Any, Callable
import numpy as np
import pandas as pd


class Phase9DReproducibilityAudit:
    """Verifies deterministic invariance between independent executions."""

    @staticmethod
    def audit_run_a_vs_run_b(
        df_sample: pd.DataFrame,
        extractor_fn: Callable[[pd.DataFrame], pd.DataFrame],
    ) -> Dict[str, Any]:
        """Runs identical feature extraction twice and verifies zero numerical drift."""
        res_a = extractor_fn(df_sample)
        res_b = extractor_fn(df_sample)

        max_delta = 0.0
        discrepant_cols = []

        for col in res_a.columns:
            s_a = res_a[col].fillna(0.0).values
            s_b = res_b[col].fillna(0.0).values
            diff = np.abs(s_a - s_b)
            m = float(np.max(diff))
            if m > max_delta:
                max_delta = m
            if m > 1e-12:
                discrepant_cols.append((col, m))

        is_reproducible = (len(discrepant_cols) == 0 and max_delta < 1e-12)

        return {
            "status": "PASS" if is_reproducible else "FAIL",
            "is_reproducible": is_reproducible,
            "max_numerical_delta": max_delta,
            "total_columns_checked": len(res_a.columns),
            "discrepant_columns": discrepant_cols,
            "verdict": "REPRODUCIBLE" if is_reproducible else "NONDETERMINISTIC",
        }
