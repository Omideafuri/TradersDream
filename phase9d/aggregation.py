"""Microstructure Aggregation Module for Phase 9D.

Aggregates order-book and trade-flow events into continuous 5-minute candle
features causally aligned to candle boundaries.
"""

from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd

from phase9d.alignment import TemporalAlignment
from phase9d.microstructure import MicrostructureEngine


class MicrostructureAggregator:
    """Aggregates discrete microstructure events/snapshots into aligned tabular series."""

    @classmethod
    def aggregate_to_candles(
        cls,
        candles_df: pd.DataFrame,
        orderbook_df: Optional[pd.DataFrame] = None,
        trades_df: Optional[pd.DataFrame] = None,
        window_name: str = "5m",
    ) -> pd.DataFrame:
        """Constructs point-in-time microstructure features aligned to candles_df.
        
        Args:
            candles_df: 5-minute candle DataFrame with 'timestamp', 'open', 'high', 'low', 'close', 'volume'.
            orderbook_df: Optional DataFrame of L2 snapshots.
            trades_df: Optional DataFrame of tick trades.
            window_name: Pre-registered lookback window ("30s", "1m", "3m", "5m").
            
        Returns:
            DataFrame of aggregated microstructure features with index matching candles_df.
        """
        has_real_ob = orderbook_df is not None and not orderbook_df.empty
        has_real_trades = trades_df is not None and not trades_df.empty

        if not has_real_ob and not has_real_trades:
            # SCIENTIFIC CLASSIFICATION: OHLCV-DERIVED PROXIES — NOT AUTHENTIC EVENT-LEVEL MICROSTRUCTURE.
            # In the absence of historical L2 depth and tick trades, this path generates synthetic
            # microstructure proxies derived from 5-minute OHLCV candles (spread proxy, volume-based TFI).
            c = candles_df["close"].values
            h = candles_df["high"].values
            l = candles_df["low"].values
            o = candles_df["open"].values
            v = candles_df["volume"].values

            range_pct = (h - l) / (c + 1e-9)
            spread_bps = np.clip(range_pct * 10000.0 * 0.15, 1.5, 25.0)
            rel_spread = spread_bps / 10000.0

            body_dir = (c - (h + l) / 2.0) / ((h - l) / 2.0 + 1e-9)
            imb_l5 = np.clip(body_dir * 0.6, -1.0, 1.0)
            imb_l1 = np.clip(body_dir * 0.8, -1.0, 1.0)
            imb_l10 = np.clip(body_dir * 0.4, -1.0, 1.0)
            depth_ratio_l5 = (1.0 + imb_l5) / (1.0 - imb_l5 + 1e-9)
            total_depth_l10 = v * 0.1

            ret_bar = (c - o) / (o + 1e-9)
            buy_fraction = 0.5 + 0.5 * np.tanh(ret_bar * 100.0)
            buy_vol = v * buy_fraction
            sell_vol = v * (1.0 - buy_fraction)
            tfi = (buy_vol - sell_vol) / (v + 1e-9)
            bs_ratio = buy_vol / (sell_vol + 1e-9)
            tc = np.maximum(1, (v * 10.0).astype(int))
            intensity = tc / 300.0
            avg_size = v / tc
            signed_vol = buy_vol - sell_vol

            agg_df = pd.DataFrame({
                "spread_bps": spread_bps,
                "relative_spread": rel_spread,
                "ob_imbalance_l1": imb_l1,
                "ob_imbalance_l5": imb_l5,
                "ob_imbalance_l10": imb_l10,
                "depth_ratio_l5": depth_ratio_l5,
                "total_depth_l10": total_depth_l10,
                "buy_volume": buy_vol,
                "sell_volume": sell_vol,
                "total_trade_volume": v,
                "aggressor_imbalance": tfi,
                "buy_sell_ratio": bs_ratio,
                "trade_count": tc,
                "trade_intensity": intensity,
                "average_trade_size": avg_size,
                "signed_volume": signed_vol,
            }, index=candles_df.index)

            agg_df = MicrostructureEngine.compute_rolling_microstructure_series_features(agg_df)
            return agg_df

        # If live snapshot/stream provided, causally slice
        n_bars = len(candles_df)
        candle_ts = candles_df["timestamp"].values
        records = []

        for i in range(n_bars):
            ts = int(candle_ts[i])
            row_metrics = {}

            if has_real_ob:
                snap = TemporalAlignment.get_latest_causal_orderbook(orderbook_df, ts)
                ob_metrics = MicrostructureEngine.compute_orderbook_snapshot_metrics(snap)
            else:
                ob_metrics = {}

            if has_real_trades:
                trades_slice = TemporalAlignment.slice_causal_trades(trades_df, ts, window_name=window_name)
                window_sec = TemporalAlignment.WINDOWS_MS.get(window_name, 300_000) / 1000.0
                tf_metrics = MicrostructureEngine.compute_trade_flow_window_metrics(trades_slice, window_seconds=window_sec)
            else:
                tf_metrics = {}

            row_metrics.update(ob_metrics)
            row_metrics.update(tf_metrics)
            records.append(row_metrics)

        agg_df = pd.DataFrame(records, index=candles_df.index)
        agg_df = MicrostructureEngine.compute_rolling_microstructure_series_features(agg_df)
        return agg_df
