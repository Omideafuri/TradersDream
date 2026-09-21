"""Cross-Asset Signal Testing and Generalization Framework.

Evaluates Jev directional predictions across BTCUSDT, ETHUSDT, and SOLUSDT:
- Tests whether signal properties persist across different market capitalizations and volatility profiles.
- Enforces identical decision rules without asset-specific parameter tuning.
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Tuple
from pathlib import Path
import numpy as np
import pandas as pd

from backtest.dataset import DatasetManager, HistoricalDecision
from backtest.engine import BacktestEngine, BacktestConfig
from validation.dataset_expansion import MultiAssetDataManager
from diagnosis.decomposition import extract_raw_signal_records


@dataclass
class CrossAssetResult:
    symbol: str
    candle_count: int
    active_signals_count: int
    directional_accuracy_15m_pct: float
    directional_accuracy_1h_pct: float
    mean_forward_return_15m_pct: float
    mean_forward_return_1h_pct: float
    strategy_net_return_pct: float
    strategy_win_rate_pct: float
    strategy_profit_factor: float
    is_cross_asset_valid: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "candle_count": self.candle_count,
            "active_signals_count": self.active_signals_count,
            "directional_accuracy_15m_pct": round(self.directional_accuracy_15m_pct, 2),
            "directional_accuracy_1h_pct": round(self.directional_accuracy_1h_pct, 2),
            "mean_forward_return_15m_pct": round(self.mean_forward_return_15m_pct, 4),
            "mean_forward_return_1h_pct": round(self.mean_forward_return_1h_pct, 4),
            "strategy_net_return_pct": round(self.strategy_net_return_pct, 4),
            "strategy_win_rate_pct": round(self.strategy_win_rate_pct, 2),
            "strategy_profit_factor": round(self.strategy_profit_factor, 4),
            "is_cross_asset_valid": self.is_cross_asset_valid,
        }


def run_cross_asset_evaluation(
    data_mgr: MultiAssetDataManager,
    config: BacktestConfig,
    assets: List[str] = ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
    seed: int = 42,
) -> List[CrossAssetResult]:
    """Evaluates raw signal and strategy metrics across assets without per-asset tuning."""
    engine = BacktestEngine(config)
    results: List[CrossAssetResult] = []

    for sym in assets:
        candles, enriched, decisions = data_mgr.get_or_generate_dataset(
            symbol=sym, timeframe="5m", target_candles=1500, seed=seed
        )

        records = extract_raw_signal_records(candles, decisions)
        active = [r for r in records if r.action in ("LONG", "SHORT")]

        fwd15 = [r.directional_returns.get("15m") for r in active if r.directional_returns.get("15m") is not None]
        fwd1h = [r.directional_returns.get("1h") for r in active if r.directional_returns.get("1h") is not None]

        acc15 = float(np.mean([f > 0 for f in fwd15])) * 100.0 if fwd15 else 0.0
        acc1h = float(np.mean([f > 0 for f in fwd1h])) * 100.0 if fwd1h else 0.0
        mean_ret15 = float(np.mean(fwd15)) * 100.0 if fwd15 else 0.0
        mean_ret1h = float(np.mean(fwd1h)) * 100.0 if fwd1h else 0.0

        backtest_res = engine.run(candles, decisions)

        results.append(
            CrossAssetResult(
                symbol=sym,
                candle_count=len(candles),
                active_signals_count=len(active),
                directional_accuracy_15m_pct=acc15,
                directional_accuracy_1h_pct=acc1h,
                mean_forward_return_15m_pct=mean_ret15,
                mean_forward_return_1h_pct=mean_ret1h,
                strategy_net_return_pct=backtest_res.metrics.total_return_pct,
                strategy_win_rate_pct=backtest_res.metrics.win_rate_pct,
                strategy_profit_factor=backtest_res.metrics.profit_factor,
                is_cross_asset_valid=acc15 > 50.0 and mean_ret15 > 0.0,
            )
        )

    return results
