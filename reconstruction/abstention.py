"""Explicit Abstention Architecture.

Disentangles flat consolidation (HOLD) from absence of edge / high epistemic uncertainty (NO_EDGE):
- LONG: Directional bias bullish + expected magnitude exceeds friction barrier + low uncertainty.
- SHORT: Directional bias bearish + expected magnitude exceeds friction barrier + low uncertainty.
- HOLD: Market is consolidating / flat / rangebound, but signals are clear and consistent.
- NO_EDGE: High uncertainty, conflicting indicators, or expected magnitude below friction barrier.
"""

from dataclasses import dataclass
from typing import Dict, Any, List
import pandas as pd
import numpy as np


@dataclass
class AbstentionProfile:
    total_bars: int
    long_count: int
    short_count: int
    hold_count: int
    no_edge_count: int
    active_trade_rate_pct: float
    abstention_rate_pct: float
    active_trade_win_rate_pct: float
    active_trade_mean_return_bps: float
    abstained_trade_mean_return_bps: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_bars": self.total_bars,
            "long_count": self.long_count,
            "short_count": self.short_count,
            "hold_count": self.hold_count,
            "no_edge_count": self.no_edge_count,
            "active_trade_rate_pct": round(self.active_trade_rate_pct, 2),
            "abstention_rate_pct": round(self.abstention_rate_pct, 2),
            "active_trade_win_rate_pct": round(self.active_trade_win_rate_pct, 2),
            "active_trade_mean_return_bps": round(self.active_trade_mean_return_bps, 1),
            "abstained_trade_mean_return_bps": round(self.abstained_trade_mean_return_bps, 1),
        }


def evaluate_decision_with_abstention(
    row: pd.Series,
    uncertainty_threshold: float = 0.50,
    magnitude_friction_bps: float = 30.0,
) -> str:
    """Evaluates whether to trade (LONG/SHORT), hold in consolidation (HOLD), or abstain (NO_EDGE)."""
    uncertainty = float(row.get("uncertainty", 0.5))
    expected_bps = float(row.get("expected_magnitude_bps", 20.0))
    dist_ema20 = float(row.get("dist_ema20_pct", 0.0))
    rsi = float(row.get("rsi14", 50.0))
    structure = str(row.get("structure_type", "MIXED"))

    # 1. High uncertainty -> NO_EDGE
    if uncertainty > uncertainty_threshold:
        return "NO_EDGE"

    # 2. Insufficient expected magnitude -> NO_EDGE
    if expected_bps < magnitude_friction_bps:
        return "NO_EDGE"

    # 3. Consolidation without strong trend -> HOLD
    if abs(dist_ema20) < 0.15 and 45.0 <= rsi <= 55.0 and structure == "MIXED":
        return "HOLD"

    # 4. Bullish conditions
    if dist_ema20 > 0 and rsi >= 50:
        return "LONG"

    # 5. Bearish conditions
    if dist_ema20 < 0 and rsi <= 50:
        return "SHORT"

    return "HOLD"


def audit_abstention_impact(
    df: pd.DataFrame,
    horizon_bars: int = 3,
    uncertainty_threshold: float = 0.50,
    friction_bps: float = 30.0,
) -> AbstentionProfile:
    """Evaluates the performance impact of explicit abstention on out-of-sample forward returns."""
    from reconstruction.market_state import compute_enriched_market_state_df
    from reconstruction.uncertainty import compute_indicator_contradiction_uncertainty

    enriched = compute_enriched_market_state_df(df)
    n = len(enriched)
    if n == 0:
        return AbstentionProfile(0, 0, 0, 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0)

    # Compute forward returns
    close = enriched["close"]
    fwd_ret = (close.shift(-horizon_bars) / close - 1.0) * 100.0
    enriched["fwd_ret"] = fwd_ret

    # Compute uncertainty & expected bps
    uncertainties = [compute_indicator_contradiction_uncertainty(r) for _, r in enriched.iterrows()]
    enriched["uncertainty"] = uncertainties
    enriched["expected_magnitude_bps"] = enriched["atr_norm_pct"] * 100.0 * 0.5

    decisions = []
    for _, r in enriched.iterrows():
        decisions.append(
            evaluate_decision_with_abstention(
                r,
                uncertainty_threshold=uncertainty_threshold,
                magnitude_friction_bps=friction_bps,
            )
        )
    enriched["decision"] = decisions

    long_c = int((enriched["decision"] == "LONG").sum())
    short_c = int((enriched["decision"] == "SHORT").sum())
    hold_c = int((enriched["decision"] == "HOLD").sum())
    no_edge_c = int((enriched["decision"] == "NO_EDGE").sum())
    active_c = long_c + short_c
    abstain_c = hold_c + no_edge_c

    active_rate = (active_c / n) * 100.0
    abstain_rate = (abstain_c / n) * 100.0

    # Evaluate win rate and returns for active trades
    active_df = enriched[enriched["decision"].isin(["LONG", "SHORT"])].dropna(subset=["fwd_ret"])
    abstained_df = enriched[enriched["decision"].isin(["HOLD", "NO_EDGE"])].dropna(subset=["fwd_ret"])

    if len(active_df) > 0:
        # Long trade returns = fwd_ret, Short trade returns = -fwd_ret
        trade_returns = np.where(active_df["decision"] == "LONG", active_df["fwd_ret"], -active_df["fwd_ret"])
        win_rate = float((trade_returns > 0).mean()) * 100.0
        mean_active_bps = float(trade_returns.mean()) * 100.0
    else:
        win_rate, mean_active_bps = 0.0, 0.0

    mean_abstained_bps = float(abstained_df["fwd_ret"].abs().mean()) * 100.0 if len(abstained_df) > 0 else 0.0

    return AbstentionProfile(
        total_bars=n,
        long_count=long_c,
        short_count=short_c,
        hold_count=hold_c,
        no_edge_count=no_edge_c,
        active_trade_rate_pct=active_rate,
        abstention_rate_pct=abstain_rate,
        active_trade_win_rate_pct=win_rate,
        active_trade_mean_return_bps=mean_active_bps,
        abstained_trade_mean_return_bps=mean_abstained_bps,
    )
