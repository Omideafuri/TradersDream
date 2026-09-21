"""Primary vs Secondary Temporal Methodology Engine.

Implements the formal distinction required by Phase 7 Section 6:

1. Primary Methodology:
   prediction horizon = execution horizon
   - 5m -> 5m (generated on 5m bars, evaluated 1 bar [5m] ahead)
   - 15m -> 15m (generated on 15m bars, evaluated 1 bar [15m] ahead)
   - 30m -> 30m (generated on 30m bars, evaluated 1 bar [30m] ahead)
   - 1h -> 1h (generated on 1h bars, evaluated 1 bar [1h] ahead)
   - 4h -> 4h (generated on 4h bars, evaluated 1 bar [4h] ahead)

2. Secondary Methodology:
   predictions generated on 5m data but evaluated at longer forward hold horizons:
   - 5m decision -> 5m forward return (1 bar)
   - 5m decision -> 15m forward return (3 bars)
   - 5m decision -> 30m forward return (6 bars)
   - 5m decision -> 1h forward return (12 bars)
   - 5m decision -> 4h forward return (48 bars)

Both methodologies maintain strictly causal market states and frozen Jev parameters.
"""

from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import pandas as pd

from temporal.data_aggregator import TemporalDataAggregator, TIMEFRAME_BAR_RATIOS
from temporal.targets import calculate_forward_targets
from reconstruction.market_state import compute_enriched_market_state_df
from reconstruction.uncertainty import compute_indicator_contradiction_uncertainty
from reconstruction.abstention import evaluate_decision_with_abstention


@dataclass
class EvaluatedBarSeries:
    methodology: str  # "PRIMARY" or "SECONDARY"
    symbol: str
    timeframe: str
    prediction_horizon: str
    shift_bars: int
    df_evaluated: pd.DataFrame
    total_bars: int
    active_bars: int
    abstained_bars: int


def generate_frozen_decisions(df_enriched: pd.DataFrame) -> pd.DataFrame:
    """Applies frozen Phase 5/6 decision architecture to an enriched DataFrame."""
    out = df_enriched.copy()
    uncertainties = [compute_indicator_contradiction_uncertainty(r) for _, r in out.iterrows()]
    out["uncertainty"] = uncertainties
    out["expected_magnitude_bps"] = out["atr_norm_pct"] * 100.0 * 0.5

    decisions = [
        evaluate_decision_with_abstention(r, uncertainty_threshold=0.50, magnitude_friction_bps=30.0)
        for _, r in out.iterrows()
    ]
    out["decision"] = decisions

    # Decision direction numeric: +1 (LONG), -1 (SHORT), 0 (HOLD/NO_EDGE)
    dir_map = {"LONG": 1, "SHORT": -1, "HOLD": 0, "NO_EDGE": 0}
    out["decision_dir"] = [dir_map.get(d, 0) for d in decisions]
    out["is_active"] = out["decision"].isin(["LONG", "SHORT"])

    # Confidence mapped deterministically from uncertainty: [0.5, 1.0]
    out["confidence"] = 1.0 - np.array(uncertainties) * 0.5
    return out


def execute_primary_methodology(
    base_5m_df: pd.DataFrame,
    symbol: str = "BTCUSDT",
    timeframes: List[str] = ["5m", "15m", "30m", "1h", "4h"],
) -> Dict[str, EvaluatedBarSeries]:
    """Executes Primary Methodology: prediction horizon == execution horizon."""
    results: Dict[str, EvaluatedBarSeries] = {}

    for tf in timeframes:
        # 1. Aggregate to target timeframe
        agg_df, _ = TemporalDataAggregator.aggregate_candles(base_5m_df, target_timeframe=tf, symbol=symbol)

        # 2. Compute enriched causal market state on aggregated timeframe
        enriched = compute_enriched_market_state_df(agg_df)

        # 3. Apply frozen Jev decision logic
        with_decisions = generate_frozen_decisions(enriched)

        # 4. Calculate 1-bar forward targets for target timeframe
        evaluated = calculate_forward_targets(with_decisions, shift_bars=1, horizon_name=tf)

        total_bars = len(evaluated)
        active_bars = int(evaluated["is_active"].sum())
        abstained_bars = total_bars - active_bars

        results[tf] = EvaluatedBarSeries(
            methodology="PRIMARY",
            symbol=symbol,
            timeframe=tf,
            prediction_horizon=tf,
            shift_bars=1,
            df_evaluated=evaluated,
            total_bars=total_bars,
            active_bars=active_bars,
            abstained_bars=abstained_bars,
        )

    return results


def execute_secondary_methodology(
    base_5m_df: pd.DataFrame,
    symbol: str = "BTCUSDT",
    horizons: List[str] = ["5m", "15m", "30m", "1h", "4h"],
) -> Dict[str, EvaluatedBarSeries]:
    """Executes Secondary Methodology: 5m execution frequency, evaluated at longer forward hold horizons."""
    results: Dict[str, EvaluatedBarSeries] = {}

    # 1. Compute enriched causal market state on base 5m
    enriched = compute_enriched_market_state_df(base_5m_df)

    # 2. Apply frozen Jev decision logic
    with_decisions = generate_frozen_decisions(enriched)

    # 3. Calculate forward targets for each horizon
    for hz in horizons:
        shift_bars = TIMEFRAME_BAR_RATIOS[hz]
        evaluated = calculate_forward_targets(with_decisions, shift_bars=shift_bars, horizon_name=hz)

        total_bars = len(evaluated)
        active_bars = int(evaluated["is_active"].sum())
        abstained_bars = total_bars - active_bars

        results[hz] = EvaluatedBarSeries(
            methodology="SECONDARY",
            symbol=symbol,
            timeframe="5m",
            prediction_horizon=hz,
            shift_bars=shift_bars,
            df_evaluated=evaluated,
            total_bars=total_bars,
            active_bars=active_bars,
            abstained_bars=abstained_bars,
        )

    return results
