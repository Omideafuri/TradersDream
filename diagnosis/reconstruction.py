"""Candidate Strategy Architectures and Out-of-Sample Reconstruction Engine.

Evaluates 5 candidate decision architectures strictly across:
  Development (60%) -> Validation (20%) -> Frozen Sealed Holdout (20%)

Candidate Architectures:
1. Architecture A: Raw Signal -> Direct Trade (no confidence filter, threshold = 0.50)
2. Architecture B: High Confidence Gating (threshold = 0.70)
3. Architecture C: Regime Alignment Filter (LONG only in Trending Up, SHORT only in Trending Down)
4. Architecture D: Composite Filter (High Confidence >= 0.70 AND Regime Aligned)
5. Architecture E: Directional Margin Filter (|prob_long - prob_short| >= 0.40)
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Tuple
import numpy as np
import pandas as pd

from backtest.dataset import HistoricalDecision
from backtest.engine import BacktestEngine, BacktestConfig, BacktestResult
from validation.regime import classify_causal_regimes


@dataclass
class CandidateArchitectureResult:
    arch_id: str
    name: str
    description: str
    dev_trades: int
    dev_return_pct: float
    dev_profit_factor: float
    dev_win_rate_pct: float
    val_trades: int
    val_return_pct: float
    val_profit_factor: float
    val_win_rate_pct: float
    holdout_trades: int
    holdout_return_pct: float
    holdout_profit_factor: float
    holdout_win_rate_pct: float
    generalization_status: str  # SUPPORTED, NOT_SUPPORTED, INCONCLUSIVE, INSUFFICIENT_SAMPLE

    def to_dict(self) -> Dict[str, Any]:
        return {
            "arch_id": self.arch_id,
            "name": self.name,
            "description": self.description,
            "dev_trades": self.dev_trades,
            "dev_return_pct": round(self.dev_return_pct, 4),
            "dev_profit_factor": round(self.dev_profit_factor, 4),
            "dev_win_rate_pct": round(self.dev_win_rate_pct, 2),
            "val_trades": self.val_trades,
            "val_return_pct": round(self.val_return_pct, 4),
            "val_profit_factor": round(self.val_profit_factor, 4),
            "val_win_rate_pct": round(self.val_win_rate_pct, 2),
            "holdout_trades": self.holdout_trades,
            "holdout_return_pct": round(self.holdout_return_pct, 4),
            "holdout_profit_factor": round(self.holdout_profit_factor, 4),
            "holdout_win_rate_pct": round(self.holdout_win_rate_pct, 2),
            "generalization_status": self.generalization_status,
        }


def filter_decisions_for_arch(
    decisions: List[HistoricalDecision],
    classified_candles: pd.DataFrame,
    arch_id: str,
) -> List[HistoricalDecision]:
    """Filters or transforms decision stream based on candidate architecture rules."""
    ts_to_trend = dict(zip(classified_candles["timestamp"], classified_candles["trend_regime"]))
    filtered: List[HistoricalDecision] = []

    for d in decisions:
        act = d.action
        conf = d.confidence
        trend = ts_to_trend.get(d.timestamp, "Sideways")

        if arch_id == "arch_a":
            # Direct execution: keep all raw actions as-is
            new_act = act
        elif arch_id == "arch_b":
            # Confidence gating >= 0.70
            new_act = act if conf >= 0.70 else "HOLD"
        elif arch_id == "arch_c":
            # Regime alignment: only LONG in Trending Up, only SHORT in Trending Down
            if act == "LONG" and trend == "Trending Up":
                new_act = "LONG"
            elif act == "SHORT" and trend == "Trending Down":
                new_act = "SHORT"
            else:
                new_act = "HOLD"
        elif arch_id == "arch_d":
            # Composite: conf >= 0.70 AND aligned with trend
            if conf >= 0.70:
                if act == "LONG" and trend == "Trending Up":
                    new_act = "LONG"
                elif act == "SHORT" and trend == "Trending Down":
                    new_act = "SHORT"
                else:
                    new_act = "HOLD"
            else:
                new_act = "HOLD"
        elif arch_id == "arch_e":
            # Directional margin: |prob_long - prob_short| >= 0.40
            margin = abs(d.prob_long - d.prob_short)
            new_act = act if margin >= 0.40 else "HOLD"
        else:
            new_act = act

        filtered.append(
            HistoricalDecision(
                timestamp=d.timestamp,
                symbol=d.symbol,
                timeframe=d.timeframe,
                price=d.price,
                action=new_act,
                confidence=d.confidence,
                prob_hold=d.prob_hold,
                prob_long=d.prob_long,
                prob_short=d.prob_short,
            )
        )

    return filtered


def evaluate_candidate_architectures(
    dev_set: Tuple[pd.DataFrame, List[HistoricalDecision]],
    val_set: Tuple[pd.DataFrame, List[HistoricalDecision]],
    holdout_set: Tuple[pd.DataFrame, List[HistoricalDecision]],
    config: BacktestConfig,
) -> List[CandidateArchitectureResult]:
    """Runs rigorous three-way partition evaluation for Architectures A through E."""
    dev_c, dev_d = dev_set
    val_c, val_d = val_set
    hld_c, hld_d = holdout_set

    # Pre-classify regimes for each set
    dev_class = classify_causal_regimes(dev_c)
    val_class = classify_causal_regimes(val_c)
    hld_class = classify_causal_regimes(hld_c)

    engine = BacktestEngine(config)

    architectures = [
        ("arch_a", "Architecture A", "Raw Signal -> Direct Trade (All signals, conf >= 0.50)"),
        ("arch_b", "Architecture B", "High Confidence Gating (Conf >= 0.70)"),
        ("arch_c", "Architecture C", "Regime Filter (Trade only in trend direction)"),
        ("arch_d", "Architecture D", "Composite (Conf >= 0.70 AND Regime Aligned)"),
        ("arch_e", "Architecture E", "Directional Margin Filter (|P_long - P_short| >= 0.40)"),
    ]

    results: List[CandidateArchitectureResult] = []

    for a_id, a_name, a_desc in architectures:
        # Dev evaluation
        dev_dec = filter_decisions_for_arch(dev_d, dev_class, a_id)
        dev_res = engine.run(dev_c, dev_dec)

        # Val evaluation
        val_dec = filter_decisions_for_arch(val_d, val_class, a_id)
        val_res = engine.run(val_c, val_dec)

        # Sealed Holdout evaluation (evaluated once on frozen architecture)
        hld_dec = filter_decisions_for_arch(hld_d, hld_class, a_id)
        hld_res = engine.run(hld_c, hld_dec)

        # Classify generalization status
        hld_ret = hld_res.metrics.total_return_pct
        hld_n = hld_res.metrics.total_trades

        if hld_n < 10:
            status = "INSUFFICIENT_SAMPLE"
        elif hld_ret > 0 and val_res.metrics.total_return_pct > 0 and dev_res.metrics.total_return_pct > 0:
            status = "SUPPORTED"
        elif hld_ret <= 0:
            status = "NOT_SUPPORTED"
        else:
            status = "INCONCLUSIVE"

        results.append(
            CandidateArchitectureResult(
                arch_id=a_id,
                name=a_name,
                description=a_desc,
                dev_trades=dev_res.metrics.total_trades,
                dev_return_pct=dev_res.metrics.total_return_pct,
                dev_profit_factor=dev_res.metrics.profit_factor,
                dev_win_rate_pct=dev_res.metrics.win_rate_pct,
                val_trades=val_res.metrics.total_trades,
                val_return_pct=val_res.metrics.total_return_pct,
                val_profit_factor=val_res.metrics.profit_factor,
                val_win_rate_pct=val_res.metrics.win_rate_pct,
                holdout_trades=hld_res.metrics.total_trades,
                holdout_return_pct=hld_ret,
                holdout_profit_factor=hld_res.metrics.profit_factor,
                holdout_win_rate_pct=hld_res.metrics.win_rate_pct,
                generalization_status=status,
            )
        )

    return results
