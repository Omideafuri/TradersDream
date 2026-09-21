"""Signal Decomposition and Directional Information Content Engine.

Separates raw predictions (Direction, Confidence, Timestamps) from execution mechanics.
Evaluates pure uncosted forward price returns at 5m, 15m, 30m, 1h, 4h horizons:
- LONG: positive forward return = correct
- SHORT: negative forward return = correct (directional return = -1 * raw return)
- HOLD: raw underlying market drift
"""

from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import pandas as pd

from backtest.dataset import HistoricalDecision
from validation.forward_returns import compute_bootstrap_ci

HORIZON_MAP = {
    "5m": 1,    # 1 bar of 5m
    "15m": 3,   # 3 bars
    "30m": 6,   # 6 bars
    "1h": 12,   # 12 bars
    "4h": 48,   # 48 bars
}


@dataclass
class RawDecisionRecord:
    timestamp: int
    symbol: str
    action: str
    confidence: float
    price: float
    prob_long: float
    prob_short: float
    prob_hold: float
    raw_returns: Dict[str, Optional[float]]
    directional_returns: Dict[str, Optional[float]]
    is_correct: Dict[str, Optional[bool]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "symbol": self.symbol,
            "action": self.action,
            "confidence": round(self.confidence, 4),
            "price": round(self.price, 2),
            "prob_long": round(self.prob_long, 4),
            "prob_short": round(self.prob_short, 4),
            "prob_hold": round(self.prob_hold, 4),
            "raw_returns": {k: (round(v * 100.0, 4) if v is not None else None) for k, v in self.raw_returns.items()},
            "directional_returns": {k: (round(v * 100.0, 4) if v is not None else None) for k, v in self.directional_returns.items()},
            "is_correct": self.is_correct,
        }


@dataclass
class HorizonSignalStats:
    horizon: str
    action: str
    sample_count: int
    mean_return_pct: float
    median_return_pct: float
    directional_accuracy_pct: float
    expected_return_pct: float
    std_return_pct: float
    ci_lower_pct: float
    ci_upper_pct: float
    is_statistically_reliable: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "horizon": self.horizon,
            "action": self.action,
            "sample_count": self.sample_count,
            "mean_return_pct": round(self.mean_return_pct, 4),
            "median_return_pct": round(self.median_return_pct, 4),
            "directional_accuracy_pct": round(self.directional_accuracy_pct, 2),
            "expected_return_pct": round(self.expected_return_pct, 4),
            "std_return_pct": round(self.std_return_pct, 4),
            "ci_lower_pct": round(self.ci_lower_pct, 4),
            "ci_upper_pct": round(self.ci_upper_pct, 4),
            "is_statistically_reliable": self.is_statistically_reliable,
        }


def extract_raw_signal_records(
    candles_df: pd.DataFrame,
    decisions: List[HistoricalDecision],
) -> List[RawDecisionRecord]:
    """Computes exact path-dependent uncosted forward returns for all decisions."""
    sorted_candles = candles_df.sort_values("timestamp").reset_index(drop=True)
    prices = sorted_candles["close"].to_numpy()
    timestamps = sorted_candles["timestamp"].to_numpy()
    ts_to_idx = {ts: idx for idx, ts in enumerate(timestamps)}

    records: List[RawDecisionRecord] = []

    for d in decisions:
        ts = d.timestamp
        if ts not in ts_to_idx:
            continue
        idx = ts_to_idx[ts]
        curr_p = prices[idx]

        raw_rets: Dict[str, Optional[float]] = {}
        dir_rets: Dict[str, Optional[float]] = {}
        correct_map: Dict[str, Optional[bool]] = {}

        for hz, offset in HORIZON_MAP.items():
            target_idx = idx + offset
            if target_idx < len(prices):
                fut_p = prices[target_idx]
                raw_r = (fut_p / curr_p) - 1.0
                raw_rets[hz] = raw_r

                if d.action == "LONG":
                    dir_rets[hz] = raw_r
                    correct_map[hz] = raw_r > 0
                elif d.action == "SHORT":
                    dir_rets[hz] = -raw_r
                    correct_map[hz] = raw_r < 0
                else:  # HOLD
                    dir_rets[hz] = raw_r
                    correct_map[hz] = None
            else:
                raw_rets[hz] = None
                dir_rets[hz] = None
                correct_map[hz] = None

        records.append(
            RawDecisionRecord(
                timestamp=ts,
                symbol=d.symbol,
                action=d.action,
                confidence=d.confidence,
                price=curr_p,
                prob_long=d.prob_long,
                prob_short=d.prob_short,
                prob_hold=d.prob_hold,
                raw_returns=raw_rets,
                directional_returns=dir_rets,
                is_correct=correct_map,
            )
        )

    return records


def compute_horizon_matrix(
    records: List[RawDecisionRecord],
    n_bootstrap: int = 500,
    seed: int = 42,
) -> Dict[str, Dict[str, HorizonSignalStats]]:
    """Calculates Signal x Horizon performance matrix.
    
    Structure: horizon -> action -> HorizonSignalStats
    """
    matrix: Dict[str, Dict[str, HorizonSignalStats]] = {}

    for hz in HORIZON_MAP.keys():
        matrix[hz] = {}
        for act in ["LONG", "SHORT", "HOLD"]:
            sub = [r for r in records if r.action == act and r.directional_returns.get(hz) is not None]
            count = len(sub)

            if count > 0:
                dir_vals = np.array([r.directional_returns[hz] * 100.0 for r in sub])  # in %
                mean_r = float(np.mean(dir_vals))
                median_r = float(np.median(dir_vals))
                std_r = float(np.std(dir_vals, ddof=1)) if count > 1 else 0.0

                if act in ("LONG", "SHORT"):
                    acc = float((dir_vals > 0).sum() / count) * 100.0
                else:
                    # For HOLD, directional accuracy is not defined in the binary sense
                    acc = float((dir_vals > 0).sum() / count) * 100.0

                ci_low, ci_high = compute_bootstrap_ci(dir_vals, n_resamples=n_bootstrap, seed=seed)
                reliable = count >= 30
            else:
                mean_r = median_r = std_r = acc = ci_low = ci_high = 0.0
                reliable = False

            matrix[hz][act] = HorizonSignalStats(
                horizon=hz,
                action=act,
                sample_count=count,
                mean_return_pct=mean_r,
                median_return_pct=median_r,
                directional_accuracy_pct=acc,
                expected_return_pct=mean_r,
                std_return_pct=std_r,
                ci_lower_pct=ci_low,
                ci_upper_pct=ci_high,
                is_statistically_reliable=reliable,
            )

    return matrix
