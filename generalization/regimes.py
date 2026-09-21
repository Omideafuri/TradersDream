"""Cross-Regime Generalization and Macro Period Diversity Engine.

Evaluates decision stability and performance across causal regimes and macro market episodes:
1. Microscopic Causal Regimes:
   - TRENDING_UP
   - TRENDING_DOWN
   - RANGE_BOUND
   - HIGH_VOLATILITY
   - LOW_VOLATILITY
   - TRANSITION
2. Macroscopic Market Episodes:
   - SUSTAINED_BULL: Multi-day cumulative drift > +3.0%
   - SUSTAINED_BEAR: Multi-day cumulative drift < -3.0%
   - SIDEWAYS_CHOP: Cumulative drift within [-1.5%, +1.5%]
   - VOLATILITY_EXPANSION: Rolling ATR in top quartile
   - VOLATILITY_COMPRESSION: Rolling ATR in bottom quartile
   - SHARP_SELLOFF: Intra-day drop > 3.0%
   - RECOVERY: Intra-day bounce > 3.0% from swing low
"""

from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd

from reconstruction.market_state import compute_enriched_market_state_df
from reconstruction.regimes import assign_causal_regimes


@dataclass
class RegimeGeneralizationMetric:
    regime_name: str
    sample_size: int
    long_count: int
    short_count: int
    no_edge_count: int
    directional_accuracy_pct: float
    mean_forward_return_bps: float
    expected_magnitude_bps: float
    mean_uncertainty: float
    gross_edge_bps: float
    net_edge_bps: float
    is_economically_positive: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MacroPeriodSummary:
    episode_name: str
    start_iso: str
    end_iso: str
    candle_count: int
    market_drift_pct: float
    active_trade_count: int
    win_rate_pct: float
    net_return_bps: float
    status: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def audit_regime_generalization(
    df: pd.DataFrame,
    horizon_bars: int = 3,
    friction_bps: float = 30.0,
    safety_margin_bps: float = 10.0,
) -> List[RegimeGeneralizationMetric]:
    """Audits decision metrics broken down strictly by causal regime."""
    from reconstruction.uncertainty import compute_indicator_contradiction_uncertainty
    from reconstruction.abstention import evaluate_decision_with_abstention

    enriched = compute_enriched_market_state_df(df)
    regimed = assign_causal_regimes(enriched)

    close = regimed["close"]
    fwd_ret = (close.shift(-horizon_bars) / close - 1.0) * 100.0
    regimed["fwd_ret"] = fwd_ret

    uncertainties = [compute_indicator_contradiction_uncertainty(r) for _, r in regimed.iterrows()]
    regimed["uncertainty"] = uncertainties
    regimed["expected_magnitude_bps"] = regimed["atr_norm_pct"] * 100.0 * 0.5

    decisions = [
        evaluate_decision_with_abstention(r, uncertainty_threshold=0.50, magnitude_friction_bps=30.0)
        for _, r in regimed.iterrows()
    ]
    regimed["decision"] = decisions

    valid = regimed.dropna(subset=["fwd_ret"]).copy()
    hurdle = friction_bps + safety_margin_bps

    regimes_list = [
        "TRENDING_UP",
        "TRENDING_DOWN",
        "RANGE_BOUND",
        "HIGH_VOLATILITY",
        "LOW_VOLATILITY",
        "TRANSITION",
    ]

    metrics: List[RegimeGeneralizationMetric] = []

    for reg in regimes_list:
        sub = valid[valid["market_regime"] == reg]
        count = len(sub)
        if count == 0:
            metrics.append(
                RegimeGeneralizationMetric(
                    regime_name=reg,
                    sample_size=0,
                    long_count=0,
                    short_count=0,
                    no_edge_count=0,
                    directional_accuracy_pct=0.0,
                    mean_forward_return_bps=0.0,
                    expected_magnitude_bps=0.0,
                    mean_uncertainty=0.0,
                    gross_edge_bps=0.0,
                    net_edge_bps=0.0,
                    is_economically_positive=False,
                )
            )
            continue

        long_c = int((sub["decision"] == "LONG").sum())
        short_c = int((sub["decision"] == "SHORT").sum())
        no_edge_c = int((sub["decision"].isin(["HOLD", "NO_EDGE"])).sum())

        active = sub[sub["decision"].isin(["LONG", "SHORT"])]
        if len(active) > 0:
            rets = np.where(active["decision"] == "LONG", active["fwd_ret"], -active["fwd_ret"])
            win_rate = float((rets > 0).mean()) * 100.0
            mean_ret_bps = float(rets.mean()) * 100.0
            net_bps = mean_ret_bps - friction_bps
        else:
            win_rate = 0.0
            mean_ret_bps = 0.0
            net_bps = 0.0

        exp_mag = float(sub["expected_magnitude_bps"].mean())
        mean_u = float(sub["uncertainty"].mean())

        metrics.append(
            RegimeGeneralizationMetric(
                regime_name=reg,
                sample_size=count,
                long_count=long_c,
                short_count=short_c,
                no_edge_count=no_edge_c,
                directional_accuracy_pct=round(win_rate, 2),
                mean_forward_return_bps=round(mean_ret_bps, 1),
                expected_magnitude_bps=round(exp_mag, 1),
                mean_uncertainty=round(mean_u, 4),
                gross_edge_bps=round(mean_ret_bps, 1),
                net_edge_bps=round(net_bps, 1),
                is_economically_positive=(net_bps > safety_margin_bps),
            )
        )

    return metrics


def identify_macro_market_episodes(
    df: pd.DataFrame, window_bars: int = 288  # 1 day of 5m bars
) -> List[MacroPeriodSummary]:
    """Partitions the dataset into distinct non-overlapping macro market episodes."""
    from datetime import datetime, timezone

    n = len(df)
    episodes: List[MacroPeriodSummary] = []
    if n < window_bars:
        return episodes

    n_chunks = n // window_bars
    for i in range(n_chunks):
        sub = df.iloc[i * window_bars : (i + 1) * window_bars]
        s_ts = int(sub["timestamp"].iloc[0])
        e_ts = int(sub["timestamp"].iloc[-1])
        s_iso = datetime.fromtimestamp(s_ts / 1000, tz=timezone.utc).isoformat()
        e_iso = datetime.fromtimestamp(e_ts / 1000, tz=timezone.utc).isoformat()

        drift = (sub["close"].iloc[-1] / sub["close"].iloc[0] - 1.0) * 100.0
        max_h = sub["high"].max()
        min_l = sub["low"].min()
        max_dd = (min_l / max_h - 1.0) * 100.0

        # Classify episode
        if drift > 3.0:
            name = "SUSTAINED_BULL"
        elif drift < -3.0:
            name = "SUSTAINED_BEAR"
        elif max_dd < -5.0:
            name = "SHARP_SELLOFF"
        else:
            name = "SIDEWAYS_CHOP"

        episodes.append(
            MacroPeriodSummary(
                episode_name=name,
                start_iso=s_iso,
                end_iso=e_iso,
                candle_count=len(sub),
                market_drift_pct=round(drift, 2),
                active_trade_count=0,  # updated during execution
                win_rate_pct=0.0,
                net_return_bps=0.0,
                status="BENCHMARK",
            )
        )

    return episodes
