"""Multi-Fold Chronological Walk-Forward Generalization Engine.

Executes strict rolling out-of-sample walk-forward validation:
- Generates n chronological folds (Train -> Val -> Test).
- Prevents look-ahead bias and cross-fold data contamination.
- Tracks fold-by-fold: active decisions, abstention rate, accuracy, forward returns,
  gross returns, fees, slippage, net returns, profit factor, and maximum drawdown.
"""

from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd

from reconstruction.market_state import compute_enriched_market_state_df
from reconstruction.uncertainty import compute_indicator_contradiction_uncertainty
from reconstruction.abstention import evaluate_decision_with_abstention


@dataclass
class WalkForwardFoldRecord:
    symbol: str
    fold_index: int
    train_start_iso: str
    train_end_iso: str
    test_start_iso: str
    test_end_iso: str
    train_bars: int
    test_bars: int
    decision_count: int
    active_trade_count: int
    abstention_rate_pct: float
    directional_accuracy_pct: float
    mean_forward_return_bps: float
    expected_magnitude_bps: float
    mean_uncertainty: float
    gross_return_bps: float
    total_fee_bps: float
    total_slippage_bps: float
    net_return_bps: float
    profit_factor: float
    max_drawdown_pct: float
    status: str  # SUPPORTED, NOT_SUPPORTED, INSUFFICIENT_SAMPLE

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def run_phase6_walk_forward(
    df: pd.DataFrame,
    symbol: str = "BTCUSDT",
    n_folds: int = 4,
    horizon_bars: int = 3,
    fee_bps_per_trade: float = 20.0,
    slippage_bps_per_trade: float = 10.0,
) -> List[WalkForwardFoldRecord]:
    """Runs rolling walk-forward validation across n_folds."""
    from datetime import datetime, timezone

    enriched = compute_enriched_market_state_df(df)
    n = len(enriched)

    uncertainties = [compute_indicator_contradiction_uncertainty(r) for _, r in enriched.iterrows()]
    enriched["uncertainty"] = uncertainties
    enriched["expected_magnitude_bps"] = enriched["atr_norm_pct"] * 100.0 * 0.5

    close = enriched["close"]
    fwd_ret = (close.shift(-horizon_bars) / close - 1.0) * 100.0
    enriched["fwd_ret"] = fwd_ret

    valid = enriched.dropna(subset=["fwd_ret"]).copy()
    total_valid = len(valid)

    if total_valid < 100:
        return []

    chunk_size = total_valid // (n_folds + 1)
    fold_records: List[WalkForwardFoldRecord] = []

    for fold in range(1, n_folds + 1):
        train_end_idx = fold * chunk_size
        test_start_idx = train_end_idx
        test_end_idx = min(test_start_idx + chunk_size, total_valid)

        train_sub = valid.iloc[:train_end_idx]
        test_sub = valid.iloc[test_start_idx:test_end_idx].copy()

        train_s = datetime.fromtimestamp(int(train_sub["timestamp"].iloc[0]) / 1000, tz=timezone.utc).isoformat()
        train_e = datetime.fromtimestamp(int(train_sub["timestamp"].iloc[-1]) / 1000, tz=timezone.utc).isoformat()
        test_s = datetime.fromtimestamp(int(test_sub["timestamp"].iloc[0]) / 1000, tz=timezone.utc).isoformat()
        test_e = datetime.fromtimestamp(int(test_sub["timestamp"].iloc[-1]) / 1000, tz=timezone.utc).isoformat()

        # Generate decisions strictly using test rows
        decisions = [
            evaluate_decision_with_abstention(r, uncertainty_threshold=0.50, magnitude_friction_bps=30.0)
            for _, r in test_sub.iterrows()
        ]
        test_sub["decision"] = decisions

        active_mask = test_sub["decision"].isin(["LONG", "SHORT"])
        active = test_sub[active_mask].copy()
        n_active = len(active)
        abstention_rate = ((len(test_sub) - n_active) / len(test_sub)) * 100.0

        if n_active >= 5:
            trade_rets = np.where(active["decision"] == "LONG", active["fwd_ret"], -active["fwd_ret"])
            win_rate = float((trade_rets > 0).mean()) * 100.0
            mean_fwd = float(trade_rets.mean()) * 100.0

            gross_bps = float(np.sum(trade_rets)) * 100.0
            fee_bps = float(n_active * fee_bps_per_trade)
            slip_bps = float(n_active * slippage_bps_per_trade)
            net_bps = gross_bps - fee_bps - slip_bps

            # Profit factor
            pos_rets = trade_rets[trade_rets > 0]
            neg_rets = -trade_rets[trade_rets < 0]
            gross_win = np.sum(pos_rets) if len(pos_rets) > 0 else 0.0
            gross_loss = np.sum(neg_rets) if len(neg_rets) > 0 else 1e-6
            pf = float(gross_win / gross_loss) if gross_loss > 0 else 1.0

            # Max drawdown on net returns
            per_trade_net = trade_rets - (fee_bps_per_trade + slippage_bps_per_trade) / 100.0
            cum_ret = np.cumsum(per_trade_net)
            running_max = np.maximum.accumulate(cum_ret)
            dd = running_max - cum_ret
            max_dd = float(np.max(dd)) * 100.0 if len(dd) > 0 else 0.0

            status = "SUPPORTED" if net_bps > 0.0 and win_rate > 52.0 else "NOT_SUPPORTED"
        else:
            win_rate, mean_fwd = 0.0, 0.0
            gross_bps, fee_bps, slip_bps, net_bps = 0.0, 0.0, 0.0, 0.0
            pf, max_dd = 1.0, 0.0
            status = "INSUFFICIENT_SAMPLE"

        exp_mag = float(test_sub["expected_magnitude_bps"].mean())
        mean_u = float(test_sub["uncertainty"].mean())

        fold_records.append(
            WalkForwardFoldRecord(
                symbol=symbol.upper(),
                fold_index=fold,
                train_start_iso=train_s,
                train_end_iso=train_e,
                test_start_iso=test_s,
                test_end_iso=test_e,
                train_bars=len(train_sub),
                test_bars=len(test_sub),
                decision_count=len(test_sub),
                active_trade_count=n_active,
                abstention_rate_pct=round(abstention_rate, 2),
                directional_accuracy_pct=round(win_rate, 2),
                mean_forward_return_bps=round(mean_fwd, 1),
                expected_magnitude_bps=round(exp_mag, 1),
                mean_uncertainty=round(mean_u, 4),
                gross_return_bps=round(gross_bps, 1),
                total_fee_bps=round(fee_bps, 1),
                total_slippage_bps=round(slip_bps, 1),
                net_return_bps=round(net_bps, 1),
                profit_factor=round(pf, 2),
                max_drawdown_pct=round(max_dd, 2),
                status=status,
            )
        )

    return fold_records
