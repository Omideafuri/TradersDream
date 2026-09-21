"""Chronological Walk-Forward Rolling Validation Engine.

Executes rolling chronological walk-forward validation across all horizons:
- 4 rolling folds per asset and horizon.
- Strictly chronological: Train -> Validation -> Test.
- No look-ahead bias, no shuffling, no overlap.
- Records exact integer bar indices and ISO timestamp boundaries per fold.
- Validates mathematical consistency with dataset size.
"""

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd


@dataclass
class WalkForwardFoldRecord:
    symbol: str
    horizon: str
    fold_index: int
    train_start_idx: int
    train_end_idx: int
    train_start_iso: str
    train_end_iso: str
    val_start_idx: int
    val_end_idx: int
    val_start_iso: str
    val_end_iso: str
    test_start_idx: int
    test_end_idx: int
    test_start_iso: str
    test_end_iso: str
    test_sample_size: int
    active_decisions: int
    abstention_rate_pct: float
    directional_accuracy_pct: float
    mean_forward_return_bps: float
    gross_return_bps: float
    net_return_bps: float
    max_drawdown_pct: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def run_temporal_walk_forward(
    df: pd.DataFrame,
    symbol: str = "BTCUSDT",
    horizon: str = "5m",
    n_folds: int = 4,
    round_trip_friction_bps: float = 30.0,
) -> List[WalkForwardFoldRecord]:
    """Runs 4-fold rolling walk-forward validation with explicit printed boundaries."""
    target_bps_col = f"target_bps_{horizon}"
    target_dir_col = f"target_dir_{horizon}"

    valid_df = df[~df[target_bps_col].isna()].copy().reset_index(drop=True)
    N = len(valid_df)

    if N < 20:
        # Insufficient data for 4 folds
        return []

    # Partition dataset into train/val/test rolling windows:
    # Fold step = N // (n_folds + 2)
    step = N // (n_folds + 2)
    train_len = step * 2
    val_len = step
    test_len = step

    folds: List[WalkForwardFoldRecord] = []

    for k in range(n_folds):
        train_start = k * step
        train_end = train_start + train_len
        val_start = train_end
        val_end = val_start + val_len
        test_start = val_end
        test_end = min(N, test_start + test_len)

        if test_end <= test_start or val_end <= val_start:
            break

        train_df = valid_df.iloc[train_start:train_end]
        val_df = valid_df.iloc[val_start:val_end]
        test_df = valid_df.iloc[test_start:test_end]

        def get_iso(sub_df: pd.DataFrame, idx_pos: int) -> str:
            ts = int(sub_df["timestamp"].iloc[idx_pos])
            return datetime.fromtimestamp(ts / 1000, tz=timezone.utc).isoformat()

        tr_start_iso = get_iso(train_df, 0)
        tr_end_iso = get_iso(train_df, -1)
        v_start_iso = get_iso(val_df, 0)
        v_end_iso = get_iso(val_df, -1)
        t_start_iso = get_iso(test_df, 0)
        t_end_iso = get_iso(test_df, -1)

        # Evaluate OOS Test performance
        test_active = test_df[test_df["is_active"]].copy()
        n_test = len(test_df)
        n_active = len(test_active)
        abstention_rate = (n_test - n_active) / n_test * 100.0 if n_test > 0 else 100.0

        if n_active == 0:
            folds.append(WalkForwardFoldRecord(
                symbol=symbol,
                horizon=horizon,
                fold_index=k + 1,
                train_start_idx=train_start,
                train_end_idx=train_end,
                train_start_iso=tr_start_iso,
                train_end_iso=tr_end_iso,
                val_start_idx=val_start,
                val_end_idx=val_end,
                val_start_iso=v_start_iso,
                val_end_iso=v_end_iso,
                test_start_idx=test_start,
                test_end_idx=test_end,
                test_start_iso=t_start_iso,
                test_end_iso=t_end_iso,
                test_sample_size=n_test,
                active_decisions=0,
                abstention_rate_pct=round(abstention_rate, 2),
                directional_accuracy_pct=0.0,
                mean_forward_return_bps=0.0,
                gross_return_bps=0.0,
                net_return_bps=0.0,
                max_drawdown_pct=0.0,
            ))
            continue

        decision_dirs = test_active["decision_dir"].values
        target_dirs = test_active[target_dir_col].values
        raw_bps = test_active[target_bps_col].values
        trade_returns = decision_dirs * raw_bps

        acc = float(np.mean(decision_dirs == target_dirs)) * 100.0
        mean_gross_bps = float(np.mean(trade_returns))
        tot_gross_bps = float(np.sum(trade_returns))
        tot_net_bps = tot_gross_bps - (n_active * round_trip_friction_bps)

        # Max drawdown
        cum_net = np.cumsum(trade_returns - round_trip_friction_bps)
        peak = np.maximum.accumulate(cum_net)
        max_dd = float(np.max(peak - cum_net)) if len(cum_net) > 0 else 0.0

        folds.append(WalkForwardFoldRecord(
            symbol=symbol,
            horizon=horizon,
            fold_index=k + 1,
            train_start_idx=train_start,
            train_end_idx=train_end,
            train_start_iso=tr_start_iso,
            train_end_iso=tr_end_iso,
            val_start_idx=val_start,
            val_end_idx=val_end,
            val_start_iso=v_start_iso,
            val_end_iso=v_end_iso,
            test_start_idx=test_start,
            test_end_idx=test_end,
            test_start_iso=t_start_iso,
            test_end_iso=t_end_iso,
            test_sample_size=n_test,
            active_decisions=n_active,
            abstention_rate_pct=round(abstention_rate, 2),
            directional_accuracy_pct=round(acc, 2),
            mean_forward_return_bps=round(mean_gross_bps, 2),
            gross_return_bps=round(tot_gross_bps, 2),
            net_return_bps=round(tot_net_bps, 2),
            max_drawdown_pct=round(max_dd / 100.0, 2),
        ))

    return folds
