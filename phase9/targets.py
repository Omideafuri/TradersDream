"""Multi-Horizon Forward Target Generation Module for Phase 9C.

Provides target variables for scientific evaluation of predictive hypotheses:
- Forward Log Returns
- Forward Directional Movement (-1 / +1)
- Forward Absolute Realized Return
- Forward Volatility

IMPORTANT: Target variables represent future outcomes and must NEVER be consumed
by feature engineering or preprocessing pipelines.
"""

from typing import Dict, List, Optional
import numpy as np
import pandas as pd


class TargetGenerator:
    """Generates multi-horizon forward outcome targets for evaluation."""

    SUPPORTED_HORIZONS = [1, 3, 6, 12, 24, 48]  # 5m, 15m, 30m, 1h, 2h, 4h

    @classmethod
    def compute_forward_targets(
        cls,
        df: pd.DataFrame,
        horizons: Optional[List[int]] = None,
    ) -> pd.DataFrame:
        """Computes multi-horizon forward targets from close prices.
        
        Args:
            df: DataFrame containing 'close'.
            horizons: List of bar horizons (default [1, 3, 6, 12, 24, 48]).
            
        Returns:
            DataFrame containing forward returns, direction, absolute returns, and volatility.
        """
        if "close" not in df.columns:
            raise ValueError("Input DataFrame must contain 'close' column.")

        horizons = horizons or cls.SUPPORTED_HORIZONS
        targets = pd.DataFrame(index=df.index)
        close = df["close"]
        log_ret_1 = np.log(close / close.shift(1))

        for h in horizons:
            # Future price at t+h
            future_close = close.shift(-h)
            
            # Forward log return from t to t+h
            fwd_ret = np.log(future_close / close)
            targets[f"target_ret_{h}"] = fwd_ret

            # Forward direction: +1 if positive, -1 if negative, 0 if flat
            direction = pd.Series(0.0, index=df.index)
            direction[fwd_ret > 0] = 1.0
            direction[fwd_ret < 0] = -1.0
            direction[fwd_ret.isna()] = np.nan
            targets[f"target_dir_{h}"] = direction

            # Forward absolute return (magnitude of move)
            targets[f"target_abs_ret_{h}"] = fwd_ret.abs()

            # Forward realized volatility: rolling std of 1-bar returns shifted back
            # Calculated over the forward window t+1 to t+h
            # rolling std over h bars shifted by -h aligns future window std to timestamp t
            fwd_vol = log_ret_1.rolling(window=h).std().shift(-h)
            targets[f"target_vol_{h}"] = fwd_vol

        return targets
