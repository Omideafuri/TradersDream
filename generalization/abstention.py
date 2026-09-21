"""Abstention Generalization and False-Negative Analysis Engine.

Validates whether the Phase 5 explicit NO_EDGE abstention behavior generalizes:
1. Stability of Abstention Rate: Does the ~80% abstention rate replicate across BTC, ETH, SOL?
2. Post-Abstention Dynamics: Did price subsequently move violently (false negative) or oscillate (true negative)?
3. Retained Signal Edge: Does the retained active trade subset exhibit higher win rates and lower drawdowns?
4. Capital Protection Efficiency: Ratio of avoided adverse excursion to missed favorable trends.
"""

from dataclasses import dataclass, asdict
from typing import Dict, Any, List
import numpy as np
import pandas as pd

from reconstruction.market_state import compute_enriched_market_state_df
from reconstruction.uncertainty import compute_indicator_contradiction_uncertainty
from reconstruction.abstention import evaluate_decision_with_abstention


@dataclass
class AbstentionGeneralizationReport:
    symbol: str
    total_bars: int
    active_count: int
    abstention_count: int
    active_rate_pct: float
    abstention_rate_pct: float
    active_win_rate_pct: float
    active_mean_return_bps: float
    abstained_mean_abs_return_bps: float
    false_negative_rate_pct: float  # Fraction of abstained bars where subsequent move exceeded 60 bps
    capital_protection_ratio: float  # Avoided churn losses vs missed trends
    verdict: str  # GENERALIZED, UNSTABLE, INSUFFICIENT_SAMPLE

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def audit_abstention_generalization(
    df: pd.DataFrame,
    symbol: str = "BTCUSDT",
    horizon_bars: int = 3,
    large_move_bps_threshold: float = 60.0,
) -> AbstentionGeneralizationReport:
    """Evaluates whether abstention characteristics generalize across datasets and assets."""
    enriched = compute_enriched_market_state_df(df)
    n = len(enriched)

    uncertainties = [compute_indicator_contradiction_uncertainty(r) for _, r in enriched.iterrows()]
    enriched["uncertainty"] = uncertainties
    enriched["expected_magnitude_bps"] = enriched["atr_norm_pct"] * 100.0 * 0.5

    decisions = [
        evaluate_decision_with_abstention(r, uncertainty_threshold=0.50, magnitude_friction_bps=30.0)
        for _, r in enriched.iterrows()
    ]
    enriched["decision"] = decisions

    close = enriched["close"]
    fwd_ret = (close.shift(-horizon_bars) / close - 1.0) * 100.0
    enriched["fwd_ret"] = fwd_ret

    valid = enriched.dropna(subset=["fwd_ret"]).copy()
    if len(valid) == 0:
        return AbstentionGeneralizationReport(
            symbol=symbol,
            total_bars=0,
            active_count=0,
            abstention_count=0,
            active_rate_pct=0.0,
            abstention_rate_pct=0.0,
            active_win_rate_pct=0.0,
            active_mean_return_bps=0.0,
            abstained_mean_abs_return_bps=0.0,
            false_negative_rate_pct=0.0,
            capital_protection_ratio=1.0,
            verdict="INSUFFICIENT_SAMPLE",
        )

    active_mask = valid["decision"].isin(["LONG", "SHORT"])
    abstained_mask = valid["decision"].isin(["HOLD", "NO_EDGE"])

    active_cnt = int(active_mask.sum())
    abstained_cnt = int(abstained_mask.sum())

    active_rate = (active_cnt / len(valid)) * 100.0
    abstain_rate = (abstained_cnt / len(valid)) * 100.0

    if active_cnt > 0:
        act_sub = valid[active_mask]
        act_rets = np.where(act_sub["decision"] == "LONG", act_sub["fwd_ret"], -act_sub["fwd_ret"])
        act_wr = float((act_rets > 0).mean()) * 100.0
        act_mean_bps = float(act_rets.mean()) * 100.0
    else:
        act_wr, act_mean_bps = 0.0, 0.0

    if abstained_cnt > 0:
        abs_sub = valid[abstained_mask]
        abs_moves_bps = abs_sub["fwd_ret"].abs() * 100.0
        mean_abs_move = float(abs_moves_bps.mean())
        # False negative: we abstained, but price made a large trend move (> 60 bps)
        fn_count = int((abs_moves_bps > large_move_bps_threshold).sum())
        fn_rate = (fn_count / abstained_cnt) * 100.0
    else:
        mean_abs_move, fn_rate = 0.0, 0.0

    # Capital protection ratio: ratio of small chops filtered (< 30 bps) to false negatives
    small_chops = int((abs_moves_bps <= 30.0).sum()) if abstained_cnt > 0 else 0
    cap_ratio = float(small_chops / max(1, fn_count)) if abstained_cnt > 0 else 1.0

    # Verdict
    if 65.0 <= abstain_rate <= 95.0 and cap_ratio >= 1.5:
        verdict = "GENERALIZED"
    elif len(valid) < 100:
        verdict = "INSUFFICIENT_SAMPLE"
    else:
        verdict = "UNSTABLE"

    return AbstentionGeneralizationReport(
        symbol=symbol,
        total_bars=n,
        active_count=active_cnt,
        abstention_count=abstained_cnt,
        active_rate_pct=round(active_rate, 2),
        abstention_rate_pct=round(abstain_rate, 2),
        active_win_rate_pct=round(act_wr, 2),
        active_mean_return_bps=round(act_mean_bps, 1),
        abstained_mean_abs_return_bps=round(mean_abs_move, 1),
        false_negative_rate_pct=round(fn_rate, 2),
        capital_protection_ratio=round(cap_ratio, 2),
        verdict=verdict,
    )
