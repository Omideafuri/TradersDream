"""Causal Market Regime x Signal Cross-Tabulation Matrix.

Examines performance segmentation across:
1. Regime x Direction (Trending Up/Down/Sideways/High Vol/Low Vol x LONG/SHORT/HOLD)
2. Regime x Confidence (Low Conf <0.65 vs High Conf >=0.65)
Computes uncosted accuracy, forward returns, MFE, MAE, and small-sample reliability.
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Tuple, Optional
import numpy as np
import pandas as pd

from backtest.dataset import HistoricalDecision
from validation.regime import classify_causal_regimes
from diagnosis.decomposition import RawDecisionRecord, extract_raw_signal_records
from diagnosis.excursion import compute_excursions, ExcursionRecord


@dataclass
class RegimeSignalCell:
    regime: str
    subgroup: str  # Action (LONG/SHORT/HOLD) or Conf tier (LOW/HIGH)
    sample_count: int
    directional_accuracy_pct: float
    mean_forward_return_15m_pct: float
    mean_confidence: float
    mean_mfe_pct: float
    mean_mae_pct: float
    is_statistically_reliable: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "regime": self.regime,
            "subgroup": self.subgroup,
            "sample_count": self.sample_count,
            "directional_accuracy_pct": round(self.directional_accuracy_pct, 2),
            "mean_forward_return_15m_pct": round(self.mean_forward_return_15m_pct, 4),
            "mean_confidence": round(self.mean_confidence, 4),
            "mean_mfe_pct": round(self.mean_mfe_pct, 4),
            "mean_mae_pct": round(self.mean_mae_pct, 4),
            "is_statistically_reliable": self.is_statistically_reliable,
        }


def build_regime_signal_matrix(
    enriched_df: pd.DataFrame,
    decisions: List[HistoricalDecision],
) -> Dict[str, List[RegimeSignalCell]]:
    """Builds two matrices: regime_x_direction and regime_x_confidence."""
    classified = classify_causal_regimes(enriched_df)
    ts_to_trend = dict(zip(classified["timestamp"], classified["trend_regime"]))
    ts_to_vol = dict(zip(classified["timestamp"], classified["vol_regime"]))

    records = extract_raw_signal_records(enriched_df, decisions)
    excursions = compute_excursions(enriched_df, decisions)
    ts_to_exc = {e.timestamp: e for e in excursions}

    regimes_list = ["Trending Up", "Trending Down", "Sideways", "High Volatility", "Low Volatility"]

    # 1. Regime x Direction
    dir_cells: List[RegimeSignalCell] = []
    for reg in regimes_list:
        for act in ["LONG", "SHORT", "HOLD"]:
            sub_recs = []
            for r in records:
                r_reg = ts_to_trend.get(r.timestamp) if reg in ("Trending Up", "Trending Down", "Sideways") else ts_to_vol.get(r.timestamp)
                if r_reg == reg and r.action == act:
                    sub_recs.append(r)

            n = len(sub_recs)
            if n > 0:
                confs = [r.confidence for r in sub_recs]
                m_conf = float(np.mean(confs))

                fwd_rets = [r.directional_returns.get("15m") for r in sub_recs if r.directional_returns.get("15m") is not None]
                if fwd_rets:
                    arr_fwd = np.array(fwd_rets) * 100.0
                    m_fwd = float(np.mean(arr_fwd))
                    acc = float((arr_fwd > 0).sum() / len(arr_fwd)) * 100.0 if act in ("LONG", "SHORT") else 50.0
                else:
                    m_fwd = acc = 0.0

                # Excursions
                sub_excs = [ts_to_exc[r.timestamp] for r in sub_recs if r.timestamp in ts_to_exc]
                if sub_excs:
                    m_mfe = float(np.mean([e.mfe_pct for e in sub_excs]))
                    m_mae = float(np.mean([e.mae_pct for e in sub_excs]))
                else:
                    m_mfe = m_mae = 0.0
            else:
                m_conf = m_fwd = acc = m_mfe = m_mae = 0.0

            dir_cells.append(
                RegimeSignalCell(
                    regime=reg,
                    subgroup=act,
                    sample_count=n,
                    directional_accuracy_pct=acc,
                    mean_forward_return_15m_pct=m_fwd,
                    mean_confidence=m_conf,
                    mean_mfe_pct=m_mfe,
                    mean_mae_pct=m_mae,
                    is_statistically_reliable=n >= 30,
                )
            )

    # 2. Regime x Confidence (Low < 0.65 vs High >= 0.65) for active directional signals
    conf_cells: List[RegimeSignalCell] = []
    for reg in regimes_list:
        for conf_tier, is_high in [("Low Conf (<0.65)", False), ("High Conf (>=0.65)", True)]:
            sub_recs = []
            for r in records:
                if r.action not in ("LONG", "SHORT"):
                    continue
                r_reg = ts_to_trend.get(r.timestamp) if reg in ("Trending Up", "Trending Down", "Sideways") else ts_to_vol.get(r.timestamp)
                tier_match = (r.confidence >= 0.65) if is_high else (r.confidence < 0.65)
                if r_reg == reg and tier_match:
                    sub_recs.append(r)

            n = len(sub_recs)
            if n > 0:
                confs = [r.confidence for r in sub_recs]
                m_conf = float(np.mean(confs))

                fwd_rets = [r.directional_returns.get("15m") for r in sub_recs if r.directional_returns.get("15m") is not None]
                if fwd_rets:
                    arr_fwd = np.array(fwd_rets) * 100.0
                    m_fwd = float(np.mean(arr_fwd))
                    acc = float((arr_fwd > 0).sum() / len(arr_fwd)) * 100.0
                else:
                    m_fwd = acc = 0.0

                sub_excs = [ts_to_exc[r.timestamp] for r in sub_recs if r.timestamp in ts_to_exc]
                if sub_excs:
                    m_mfe = float(np.mean([e.mfe_pct for e in sub_excs]))
                    m_mae = float(np.mean([e.mae_pct for e in sub_excs]))
                else:
                    m_mfe = m_mae = 0.0
            else:
                m_conf = m_fwd = acc = m_mfe = m_mae = 0.0

            conf_cells.append(
                RegimeSignalCell(
                    regime=reg,
                    subgroup=conf_tier,
                    sample_count=n,
                    directional_accuracy_pct=acc,
                    mean_forward_return_15m_pct=m_fwd,
                    mean_confidence=m_conf,
                    mean_mfe_pct=m_mfe,
                    mean_mae_pct=m_mae,
                    is_statistically_reliable=n >= 30,
                )
            )

    return {
        "regime_x_direction": dir_cells,
        "regime_x_confidence": conf_cells,
    }
