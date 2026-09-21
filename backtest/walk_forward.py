"""Chronological Walk-Forward Splitting and Validation.

Divides time series chronologically without random shuffling:
  TRAIN / CALIBRATION -> OUT-OF-SAMPLE TEST
Ensures test period timestamps strictly succeed calibration period timestamps.
"""

from dataclasses import dataclass
from typing import List, Tuple, Dict, Any
import pandas as pd

from backtest.dataset import HistoricalDecision
from backtest.engine import BacktestEngine, BacktestConfig, BacktestResult


@dataclass
class WalkForwardFoldResult:
    fold: int
    train_start: int
    train_end: int
    test_start: int
    test_end: int
    train_return_pct: float
    test_return_pct: float
    train_trades: int
    test_trades: int
    test_win_rate_pct: float
    test_max_drawdown_pct: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fold": self.fold,
            "train_start": self.train_start,
            "train_end": self.train_end,
            "test_start": self.test_start,
            "test_end": self.test_end,
            "train_return_pct": round(self.train_return_pct, 4),
            "test_return_pct": round(self.test_return_pct, 4),
            "train_trades": self.train_trades,
            "test_trades": self.test_trades,
            "test_win_rate_pct": round(self.test_win_rate_pct, 2),
            "test_max_drawdown_pct": round(self.test_max_drawdown_pct, 4),
        }


def chronological_split(
    candles: pd.DataFrame,
    decisions: List[HistoricalDecision],
    train_ratio: float = 0.70,
) -> Tuple[pd.DataFrame, List[HistoricalDecision], pd.DataFrame, List[HistoricalDecision]]:
    """Splits candles and decisions into strictly chronological Train and Test sets.
    
    Verifies that all train timestamps precede test timestamps.
    """
    sorted_candles = candles.sort_values("timestamp").reset_index(drop=True)
    split_idx = int(len(sorted_candles) * train_ratio)

    train_candles = sorted_candles.iloc[:split_idx].copy()
    test_candles = sorted_candles.iloc[split_idx:].copy()

    split_ts = sorted_candles.iloc[split_idx]["timestamp"]

    train_decisions = [d for d in decisions if d.timestamp < split_ts]
    test_decisions = [d for d in decisions if d.timestamp >= split_ts]

    # Invariant: train strictly before test
    if not train_candles.empty and not test_candles.empty:
        assert train_candles["timestamp"].max() < test_candles["timestamp"].min(), \
            "Data leakage detected: train timestamps overlap test timestamps"

    return train_candles, train_decisions, test_candles, test_decisions


def run_walk_forward_evaluation(
    candles: pd.DataFrame,
    decisions: List[HistoricalDecision],
    config: BacktestConfig,
    folds: int = 3,
    train_ratio: float = 0.60,
) -> List[WalkForwardFoldResult]:
    """Runs rolling/expanding walk-forward splits chronologically."""
    sorted_candles = candles.sort_values("timestamp").reset_index(drop=True)
    n_candles = len(sorted_candles)
    fold_size = n_candles // folds

    results: List[WalkForwardFoldResult] = []
    engine = BacktestEngine(config)

    for i in range(folds):
        train_len = int(fold_size * train_ratio)
        test_len = fold_size - train_len

        start_idx = i * fold_size
        mid_idx = start_idx + train_len
        end_idx = start_idx + fold_size

        if end_idx > n_candles:
            break

        train_c = sorted_candles.iloc[start_idx:mid_idx]
        test_c = sorted_candles.iloc[mid_idx:end_idx]

        min_train_ts = train_c["timestamp"].min()
        max_train_ts = train_c["timestamp"].max()
        min_test_ts = test_c["timestamp"].min()
        max_test_ts = test_c["timestamp"].max()

        train_d = [d for d in decisions if min_train_ts <= d.timestamp <= max_train_ts]
        test_d = [d for d in decisions if min_test_ts <= d.timestamp <= max_test_ts]

        res_train = engine.run(train_c, train_d)
        res_test = engine.run(test_c, test_d)

        results.append(
            WalkForwardFoldResult(
                fold=i + 1,
                train_start=int(min_train_ts),
                train_end=int(max_train_ts),
                test_start=int(min_test_ts),
                test_end=int(max_test_ts),
                train_return_pct=res_train.metrics.total_return_pct,
                test_return_pct=res_test.metrics.total_return_pct,
                train_trades=res_train.metrics.total_trades,
                test_trades=res_test.metrics.total_trades,
                test_win_rate_pct=res_test.metrics.win_rate_pct,
                test_max_drawdown_pct=res_test.metrics.max_drawdown_pct,
            )
        )

    return results
