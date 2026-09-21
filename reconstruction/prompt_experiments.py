"""Controlled Prompt & Context Engineering Experiments.

Defines and evaluates 5 controlled prompt variants:
- Variant A (Baseline): Generic trading action prompt without horizon or structure.
- Variant B (Horizon-Explicit): Explicit 15m prediction horizon.
- Variant C (Regime-Aware): Explicit market regime conditioning (TRENDING, RANGE, VOLATILITY).
- Variant D (Decomposed): Decoupled P(up), expected return magnitude, and uncertainty score.
- Variant E (Unified Enriched): Full market structure (swings, BOS, compression), regime, and explicit horizon.

Supports deterministic offline evaluation with strictly reproducible pseudo-response generation.
"""

from dataclasses import dataclass
from typing import Dict, Any, List
import pandas as pd
import numpy as np


@dataclass
class PromptExperimentResult:
    variant_id: str
    variant_name: str
    prompt_template: str
    total_predictions: int
    long_pct: float
    short_pct: float
    hold_pct: float
    no_edge_pct: float
    directional_accuracy_pct: float
    mean_realized_return_bps: float
    win_rate_pct: float
    status: str  # SUPPORTED, NOT_SUPPORTED, INCONCLUSIVE

    def to_dict(self) -> Dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "variant_name": self.variant_name,
            "prompt_template": self.prompt_template,
            "total_predictions": self.total_predictions,
            "long_pct": round(self.long_pct, 2),
            "short_pct": round(self.short_pct, 2),
            "hold_pct": round(self.hold_pct, 2),
            "no_edge_pct": round(self.no_edge_pct, 2),
            "directional_accuracy_pct": round(self.directional_accuracy_pct, 2),
            "mean_realized_return_bps": round(self.mean_realized_return_bps, 1),
            "win_rate_pct": round(self.win_rate_pct, 2),
            "status": self.status,
        }


PROMPT_VARIANTS = {
    "Variant_A": {
        "name": "Baseline (Unconstrained)",
        "template": (
            "Determine the cryptocurrency trading action for {symbol} based strictly on the provided technical indicator state.\n"
            "Inputs: Price={price}, EMA20={ema20}, EMA50={ema50}, RSI14={rsi14}, ATR14={atr14}, VolumeRatio={volume_ratio}.\n"
            "Choices: LONG, SHORT, HOLD."
        ),
    },
    "Variant_B": {
        "name": "Horizon-Explicit (15m)",
        "template": (
            "Determine the directional movement of {symbol} over the explicit forward horizon of 15 minutes (3 bars).\n"
            "Inputs: Price={price}, EMA20={ema20}, EMA50={ema50}, RSI14={rsi14}, ATR14={atr14}, VolumeRatio={volume_ratio}.\n"
            "Goal: Predict whether price in 15 minutes will be higher (+15m) or lower (-15m).\n"
            "Choices: LONG, SHORT, HOLD."
        ),
    },
    "Variant_C": {
        "name": "Regime-Conditioned",
        "template": (
            "Given current Market Regime: {market_regime}.\n"
            "Determine trading action for {symbol} over a 15-minute horizon.\n"
            "If Regime is RANGE_BOUND, prefer HOLD or mean-reversion.\n"
            "If Regime is TRENDING, align with trend direction.\n"
            "Choices: LONG, SHORT, HOLD."
        ),
    },
    "Variant_D": {
        "name": "Decomposed (Uncertainty & Magnitude)",
        "template": (
            "Analyze market state for {symbol}. Do not force a trade.\n"
            "Output three explicit parameters:\n"
            "1. P(Up) probability in [0.0, 1.0]\n"
            "2. Expected move magnitude in basis points\n"
            "3. Uncertainty score U in [0.0, 1.0]\n"
            "If U > 0.50 or Expected Move < 30 bps, output NO_EDGE."
        ),
    },
    "Variant_E": {
        "name": "Unified Enriched (Structure + Regime + Horizon)",
        "template": (
            "Market Analysis for {symbol} over 15m Forward Horizon:\n"
            "- Regime: {market_regime}\n"
            "- Structure: {structure_type}, BOS={break_of_structure}, Swing High={dist_to_swing_high_pct}%, Swing Low={dist_to_swing_low_pct}%\n"
            "- Volatility Compression: {compression_state} (ATR%={atr_norm_pct}%)\n"
            "Task: Issue LONG/SHORT only if Break of Structure confirms trend and expected move exceeds 40 bps; otherwise issue NO_EDGE or HOLD."
        ),
    },
}


def simulate_prompt_decision(variant_id: str, row: pd.Series) -> str:
    """Deterministic simulation of prompt responses based on variant criteria."""
    price = float(row["close"])
    ema20 = float(row.get("ema20", price))
    ema50 = float(row.get("ema50", price))
    rsi = float(row.get("rsi14", 50.0))
    atr_norm = float(row.get("atr_norm_pct", 0.5))
    regime = str(row.get("market_regime", "TRANSITION"))
    structure = str(row.get("structure_type", "MIXED"))
    bos = str(row.get("break_of_structure", "NONE"))
    uncertainty = float(row.get("uncertainty", 0.5))

    if variant_id == "Variant_A":
        # Baseline behavior: naive threshold on EMA and RSI
        if price > ema20 and rsi > 52:
            return "LONG"
        elif price < ema20 and rsi < 48:
            return "SHORT"
        return "HOLD"

    elif variant_id == "Variant_B":
        # Horizon explicit: requires 3-bar momentum alignment
        rsi_slope = float(row.get("rsi_slope_3", 0.0))
        if price > ema20 and rsi_slope > 1.0:
            return "LONG"
        elif price < ema20 and rsi_slope < -1.0:
            return "SHORT"
        return "HOLD"

    elif variant_id == "Variant_C":
        # Regime aware: trade only in trending regimes, hold in ranges
        if regime == "RANGE_BOUND" or regime == "LOW_VOLATILITY":
            return "HOLD"
        if regime == "TRENDING_UP" and price > ema20:
            return "LONG"
        if regime == "TRENDING_DOWN" and price < ema20:
            return "SHORT"
        return "HOLD"

    elif variant_id == "Variant_D":
        # Decomposed: explicit NO_EDGE on uncertainty
        expected_bps = atr_norm * 100.0 * 0.5
        if uncertainty > 0.50 or expected_bps < 30.0:
            return "NO_EDGE"
        if price > ema20 and rsi >= 50:
            return "LONG"
        if price < ema20 and rsi <= 50:
            return "SHORT"
        return "HOLD"

    elif variant_id == "Variant_E":
        # Unified enriched: BOS + Structure + Regime + Friction
        expected_bps = atr_norm * 100.0 * 0.5
        if uncertainty > 0.45 or expected_bps < 35.0:
            return "NO_EDGE"
        if regime == "RANGE_BOUND":
            return "HOLD"

        if (regime == "TRENDING_UP" or structure == "HH_HL" or bos == "BULLISH_BOS") and price > ema20:
            return "LONG"
        if (regime == "TRENDING_DOWN" or structure == "LH_LL" or bos == "BEARISH_BOS") and price < ema20:
            return "SHORT"
        return "HOLD"

    return "HOLD"


def run_prompt_experiments(df: pd.DataFrame, horizon_bars: int = 3) -> List[PromptExperimentResult]:
    """Runs all 5 prompt experiments on the dataset and evaluates out-of-sample decision quality."""
    from reconstruction.market_state import compute_enriched_market_state_df
    from reconstruction.regimes import assign_causal_regimes
    from reconstruction.uncertainty import compute_indicator_contradiction_uncertainty

    enriched = compute_enriched_market_state_df(df)
    enriched = assign_causal_regimes(enriched)

    uncertainties = [compute_indicator_contradiction_uncertainty(r) for _, r in enriched.iterrows()]
    enriched["uncertainty"] = uncertainties

    close = enriched["close"]
    fwd_ret = (close.shift(-horizon_bars) / close - 1.0) * 100.0
    enriched["fwd_ret"] = fwd_ret

    valid = enriched.dropna(subset=["fwd_ret"]).copy()
    n = len(valid)
    if n == 0:
        return []

    results: List[PromptExperimentResult] = []

    for vid, meta in PROMPT_VARIANTS.items():
        decisions = [simulate_prompt_decision(vid, row) for _, row in valid.iterrows()]
        valid["decision"] = decisions

        long_c = int((valid["decision"] == "LONG").sum())
        short_c = int((valid["decision"] == "SHORT").sum())
        hold_c = int((valid["decision"] == "HOLD").sum())
        no_edge_c = int((valid["decision"] == "NO_EDGE").sum())

        long_pct = (long_c / n) * 100.0
        short_pct = (short_c / n) * 100.0
        hold_pct = (hold_c / n) * 100.0
        no_edge_pct = (no_edge_c / n) * 100.0

        active_mask = valid["decision"].isin(["LONG", "SHORT"])
        active_sub = valid[active_mask]

        if len(active_sub) > 0:
            trade_ret = np.where(active_sub["decision"] == "LONG", active_sub["fwd_ret"], -active_sub["fwd_ret"])
            win_rate = float((trade_ret > 0).mean()) * 100.0
            acc = win_rate
            mean_bps = float(trade_ret.mean()) * 100.0
        else:
            win_rate, acc, mean_bps = 0.0, 0.0, 0.0

        # Status determination
        if len(active_sub) >= 20 and win_rate > 53.0 and mean_bps > 10.0:
            status = "SUPPORTED"
        elif len(active_sub) < 15:
            status = "INSUFFICIENT_SAMPLE"
        else:
            status = "NOT_SUPPORTED"

        results.append(
            PromptExperimentResult(
                variant_id=vid,
                variant_name=meta["name"],
                prompt_template=meta["template"],
                total_predictions=n,
                long_pct=long_pct,
                short_pct=short_pct,
                hold_pct=hold_pct,
                no_edge_pct=no_edge_pct,
                directional_accuracy_pct=acc,
                mean_realized_return_bps=mean_bps,
                win_rate_pct=win_rate,
                status=status,
            )
        )

    return results
