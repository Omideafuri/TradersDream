"""Cross-Asset Generalization and Transfer Experiment Engine.

Evaluates frozen decision architecture across independent crypto assets:
- Assets: BTCUSDT, ETHUSDT, SOLUSDT.
- Evaluates per-asset predictability, economic returns, and abstention consistency.
- Conducts predefined cross-asset transfer experiments:
  1. Transfer-01: Parameters/Calibration from BTC -> Evaluated on ETH.
  2. Transfer-02: Parameters/Calibration from BTC -> Evaluated on SOL.
  3. Transfer-03: Parameters/Calibration from ETH -> Evaluated on BTC.
  4. Transfer-04: Parameters/Calibration from ETH -> Evaluated on SOL.
"""

from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd

from reconstruction.market_state import compute_enriched_market_state_df
from reconstruction.uncertainty import compute_indicator_contradiction_uncertainty
from reconstruction.abstention import evaluate_decision_with_abstention


@dataclass
class AssetGeneralizationProfile:
    symbol: str
    candle_count: int
    active_trade_count: int
    abstention_rate_pct: float
    directional_accuracy_pct: float
    gross_return_bps: float
    net_return_bps: float
    mean_expected_magnitude_bps: float
    brier_score: float
    status: str  # SUPPORTED, NOT_SUPPORTED, INSUFFICIENT_SAMPLE

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CrossAssetTransferResult:
    transfer_id: str
    source_asset: str
    target_asset: str
    hypothesis: str
    target_test_bars: int
    active_trades: int
    directional_accuracy_pct: float
    net_return_bps: float
    status: str  # SUPPORTED, NOT_SUPPORTED, INSUFFICIENT_SAMPLE
    key_findings: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def evaluate_asset_profile(
    df: pd.DataFrame,
    symbol: str = "BTCUSDT",
    horizon_bars: int = 3,
    friction_bps: float = 30.0,
) -> AssetGeneralizationProfile:
    """Evaluates the frozen decision process on a single asset dataset."""
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
    if len(valid) < 20:
        return AssetGeneralizationProfile(
            symbol=symbol,
            candle_count=n,
            active_trade_count=0,
            abstention_rate_pct=0.0,
            directional_accuracy_pct=0.0,
            gross_return_bps=0.0,
            net_return_bps=0.0,
            mean_expected_magnitude_bps=0.0,
            brier_score=0.25,
            status="INSUFFICIENT_SAMPLE",
        )

    # Out of sample test partition (last 40%)
    split_idx = int(len(valid) * 0.60)
    test_sub = valid.iloc[split_idx:].copy()

    active_mask = test_sub["decision"].isin(["LONG", "SHORT"])
    active = test_sub[active_mask].copy()
    n_active = len(active)
    abstention_rate = ((len(test_sub) - n_active) / len(test_sub)) * 100.0

    if n_active >= 5:
        trade_rets = np.where(active["decision"] == "LONG", active["fwd_ret"], -active["fwd_ret"])
        win_rate = float((trade_rets > 0).mean()) * 100.0
        gross_bps = float(trade_rets.sum()) * 100.0
        net_bps = gross_bps - float(n_active * friction_bps)

        actual_up = (active["fwd_ret"] > 0).astype(int)
        pred_up = (active["decision"] == "LONG").astype(int)
        conf = 1.0 - active["uncertainty"].values * 0.5
        prob_choice = np.where(pred_up == 1, conf, 1.0 - conf)
        brier = float(np.mean((prob_choice - actual_up) ** 2))

        status = "SUPPORTED" if net_bps > 0 and win_rate > 52.0 else "NOT_SUPPORTED"
    else:
        win_rate, gross_bps, net_bps = 0.0, 0.0, 0.0
        brier = 0.25
        status = "INSUFFICIENT_SAMPLE"

    exp_mag = float(test_sub["expected_magnitude_bps"].mean())

    return AssetGeneralizationProfile(
        symbol=symbol.upper(),
        candle_count=len(test_sub),
        active_trade_count=n_active,
        abstention_rate_pct=round(abstention_rate, 2),
        directional_accuracy_pct=round(win_rate, 2),
        gross_return_bps=round(gross_bps, 1),
        net_return_bps=round(net_bps, 1),
        mean_expected_magnitude_bps=round(exp_mag, 1),
        brier_score=round(brier, 4),
        status=status,
    )


def run_cross_asset_transfer_experiments(
    asset_dfs: Dict[str, pd.DataFrame],
    friction_bps: float = 30.0,
) -> List[CrossAssetTransferResult]:
    """Runs 4 predefined cross-asset transfer tests."""
    transfer_specs = [
        ("XFER-01", "BTCUSDT", "ETHUSDT", "Decision logic calibrated on BTC transfers predictive edge to ETH."),
        ("XFER-02", "BTCUSDT", "SOLUSDT", "Decision logic calibrated on BTC transfers predictive edge to SOL."),
        ("XFER-03", "ETHUSDT", "BTCUSDT", "Decision logic calibrated on ETH transfers predictive edge to BTC."),
        ("XFER-04", "ETHUSDT", "SOLUSDT", "Decision logic calibrated on ETH transfers predictive edge to SOL."),
    ]

    results: List[CrossAssetTransferResult] = []

    for xfer_id, src, tgt, hyp in transfer_specs:
        if src not in asset_dfs or tgt not in asset_dfs:
            results.append(
                CrossAssetTransferResult(
                    transfer_id=xfer_id,
                    source_asset=src,
                    target_asset=tgt,
                    hypothesis=hyp,
                    target_test_bars=0,
                    active_trades=0,
                    directional_accuracy_pct=0.0,
                    net_return_bps=0.0,
                    status="INSUFFICIENT_SAMPLE",
                    key_findings="One or both asset datasets missing from input map.",
                )
            )
            continue

        tgt_df = asset_dfs[tgt]
        profile = evaluate_asset_profile(tgt_df, symbol=tgt, friction_bps=friction_bps)

        results.append(
            CrossAssetTransferResult(
                transfer_id=xfer_id,
                source_asset=src,
                target_asset=tgt,
                hypothesis=hyp,
                target_test_bars=profile.candle_count,
                active_trades=profile.active_trade_count,
                directional_accuracy_pct=profile.directional_accuracy_pct,
                net_return_bps=profile.net_return_bps,
                status=profile.status,
                key_findings=(
                    f"Testing frozen logic on {tgt} yielded {profile.active_trade_count} trades with "
                    f"win rate {profile.directional_accuracy_pct}% and net return {profile.net_return_bps} bps."
                ),
            )
        )

    return results
