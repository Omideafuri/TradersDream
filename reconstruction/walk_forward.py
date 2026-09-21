"""Strict Chronological Walk-Forward Validation Engine.

Implements 4-fold chronological Walk-Forward Validation (Train -> Val -> Test):
- Preserves temporal order strictly: no data leakage, no forward-looking look-ahead.
- Evaluates strategy / decision performance across each fold independently.
- Reports fold-by-fold metrics: returns, trade counts, win rate, and pass/fail status.
"""

from dataclasses import dataclass
from typing import Dict, Any, List
import pandas as pd
import numpy as np


@dataclass
class WalkForwardFoldResult:
    fold_index: int
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    train_bars: int
    test_bars: int
    test_trades: int
    test_win_rate_pct: float
    test_return_bps: float
    test_max_drawdown_pct: float
    status: str  # SUPPORTED, NOT_SUPPORTED, INCONCLUSIVE

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fold_index": self.fold_index,
            "train_start": self.train_start,
            "train_end": self.train_end,
            "test_start": self.test_start,
            "test_end": self.test_end,
            "train_bars": self.train_bars,
            "test_bars": self.test_bars,
            "test_trades": self.test_trades,
            "test_win_rate_pct": round(self.test_win_rate_pct, 2),
            "test_return_bps": round(self.test_return_bps, 1),
            "test_max_drawdown_pct": round(self.test_max_drawdown_pct, 2),
            "status": self.status,
        }


def run_walk_forward_evaluation(
    df: pd.DataFrame,
    n_folds: int = 4,
    horizon_bars: int = 3,
    friction_bps: float = 30.0,
) -> List[WalkForwardFoldResult]:
    """Runs strict chronological rolling walk-forward validation across n_folds."""
    from reconstruction.market_state import compute_enriched_market_state_df
    from reconstruction.regimes import assign_causal_regimes
    from reconstruction.uncertainty import compute_indicator_contradiction_uncertainty
    from reconstruction.abstention import evaluate_decision_with_abstention

    enriched = compute_enriched_market_state_df(df)
    enriched = assign_causal_regimes(enriched)

    uncertainties = [compute_indicator_contradiction_uncertainty(r) for _, r in enriched.iterrows()]
    enriched["uncertainty"] = uncertainties
    enriched["expected_magnitude_bps"] = enriched["atr_norm_pct"] * 100.0 * 0.5

    close = enriched["close"]
    fwd_ret = (close.shift(-horizon_bars) / close - 1.0) * 100.0
    enriched["fwd_ret"] = fwd_ret

    valid = enriched.dropna(subset=["fwd_ret"]).copy()
    n = len(valid)

    if n < 200:
        return []

    fold_results: List[WalkForwardFoldResult] = []
    # Divide into (n_folds + 1) chunks: chunk 0 is initial train, each next chunk is test
    chunk_size = n // (n_folds + 1)

    for fold in range(1, n_folds + 1):
        train_end_idx = fold * chunk_size
        test_start_idx = train_end_idx
        test_end_idx = min(test_start_idx + chunk_size, n)

        train_sub = valid.iloc[:train_end_idx]
        test_sub = valid.iloc[test_start_idx:test_end_idx].copy()

        train_start = str(train_sub.iloc[0].get("timestamp", ""))
        train_end = str(train_sub.iloc[-1].get("timestamp", ""))
        test_start = str(test_sub.iloc[0].get("timestamp", ""))
        test_end = str(test_sub.iloc[-1].get("timestamp", ""))

        # Evaluate decisions on test partition
        decisions = [
            evaluate_decision_with_abstention(r, uncertainty_threshold=0.50, magnitude_friction_bps=friction_bps)
            for _, r in test_sub.iterrows()
        ]
        test_sub["decision"] = decisions

        active = test_sub[test_sub["decision"].isin(["LONG", "SHORT"])].copy()
        n_trades = len(active)

        if n_trades >= 5:
            rets = np.where(active["decision"] == "LONG", active["fwd_ret"], -active["fwd_ret"])
            win_rate = float((rets > 0).mean()) * 100.0
            # Net bps after friction
            net_rets = rets - (friction_bps / 100.0)
            tot_return_bps = float(net_rets.sum()) * 100.0

            # Max drawdown on cumulative return
            cum_ret = np.cumsum(net_rets)
            running_max = np.maximum.accumulate(cum_ret)
            dd = running_max - cum_ret
            max_dd = float(np.max(dd)) if len(dd) > 0 else 0.0

            status = "SUPPORTED" if tot_return_bps > 0 and win_rate > 50.0 else "NOT_SUPPORTED"
        else:
            win_rate = 0.0
            tot_return_bps = 0.0
            max_dd = 0.0
            status = "INSUFFICIENT_SAMPLE"

        fold_results.append(
            WalkForwardFoldResult(
                fold_index=fold,
                train_start=train_start,
                train_end=train_end,
                test_start=test_start,
                test_end=test_end,
                train_bars=len(train_sub),
                test_bars=len(test_sub),
                test_trades=n_trades,
                test_win_rate_pct=win_rate,
                test_return_bps=tot_return_bps,
                test_max_drawdown_pct=max_dd,
                status=status,
            )
        )

    return fold_results
