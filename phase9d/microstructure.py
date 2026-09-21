"""Microstructure Feature Extraction Module for Phase 9D.

Calculates mathematically rigorous, point-in-time order-book, trade-flow,
and regime interaction features.
"""

from dataclasses import dataclass, asdict
import math
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd


class MicrostructureEngine:
    """Computes order-book and trade-flow metrics strictly point-in-time."""

    @staticmethod
    def compute_orderbook_snapshot_metrics(orderbook_df: pd.DataFrame) -> Dict[str, float]:
        """Calculates instantaneous microstructure depth & spread metrics from L2 snapshot.
        
        Expected schema: ['timestamp', 'side', 'price', 'quantity', 'level']
        """
        if orderbook_df.empty:
            return {
                "spread_bps": 0.0, "relative_spread": 0.0,
                "ob_imbalance_l1": 0.0, "ob_imbalance_l5": 0.0, "ob_imbalance_l10": 0.0,
                "depth_ratio_l5": 1.0, "total_depth_l10": 0.0,
            }

        bids = orderbook_df[orderbook_df["side"].str.upper() == "BID"].sort_values("level").reset_index(drop=True)
        asks = orderbook_df[orderbook_df["side"].str.upper() == "ASK"].sort_values("level").reset_index(drop=True)

        if bids.empty or asks.empty:
            return {
                "spread_bps": 0.0, "relative_spread": 0.0,
                "ob_imbalance_l1": 0.0, "ob_imbalance_l5": 0.0, "ob_imbalance_l10": 0.0,
                "depth_ratio_l5": 1.0, "total_depth_l10": 0.0,
            }

        best_bid = float(bids["price"].iloc[0])
        best_ask = float(asks["price"].iloc[0])
        mid_price = (best_bid + best_ask) / 2.0
        spread = best_ask - best_bid
        rel_spread = spread / (mid_price + 1e-9)
        spread_bps = rel_spread * 10000.0

        # L1 imbalance
        bid_q1 = float(bids["quantity"].iloc[0]) if len(bids) > 0 else 0.0
        ask_q1 = float(asks["quantity"].iloc[0]) if len(asks) > 0 else 0.0
        imb_l1 = (bid_q1 - ask_q1) / (bid_q1 + ask_q1 + 1e-9)

        # L5 imbalance
        b5 = bids.iloc[:5]["quantity"].sum()
        a5 = asks.iloc[:5]["quantity"].sum()
        imb_l5 = (b5 - a5) / (b5 + a5 + 1e-9)
        ratio_l5 = b5 / (a5 + 1e-9)

        # L10 imbalance
        b10 = bids.iloc[:10]["quantity"].sum()
        a10 = asks.iloc[:10]["quantity"].sum()
        imb_l10 = (b10 - a10) / (b10 + a10 + 1e-9)

        return {
            "spread_bps": float(spread_bps),
            "relative_spread": float(rel_spread),
            "ob_imbalance_l1": float(imb_l1),
            "ob_imbalance_l5": float(imb_l5),
            "ob_imbalance_l10": float(imb_l10),
            "depth_ratio_l5": float(ratio_l5),
            "total_depth_l10": float(b10 + a10),
        }

    @staticmethod
    def compute_trade_flow_window_metrics(trades_df: pd.DataFrame, window_seconds: float = 300.0) -> Dict[str, float]:
        """Calculates trade flow and aggressor imbalance metrics over a causal window.
        
        Expected schema: ['timestamp', 'price', 'quantity', 'side', 'trade_id']
        where 'side' indicates aggressor: BUY (taker bought) or SELL (taker sold).
        """
        if trades_df.empty:
            return {
                "buy_volume": 0.0, "sell_volume": 0.0, "total_trade_volume": 0.0,
                "aggressor_imbalance": 0.0, "buy_sell_ratio": 1.0,
                "trade_count": 0, "trade_intensity": 0.0, "average_trade_size": 0.0,
                "signed_volume": 0.0,
            }

        buy_mask = trades_df["side"].str.upper() == "BUY"
        sell_mask = trades_df["side"].str.upper() == "SELL"

        buy_vol = float(trades_df.loc[buy_mask, "quantity"].sum())
        sell_vol = float(trades_df.loc[sell_mask, "quantity"].sum())
        tot_vol = buy_vol + sell_vol
        trade_count = len(trades_df)

        tfi = (buy_vol - sell_vol) / (tot_vol + 1e-9)
        bs_ratio = buy_vol / (sell_vol + 1e-9)
        intensity = trade_count / (window_seconds + 1e-9)
        avg_size = tot_vol / (trade_count + 1e-9)
        signed_vol = buy_vol - sell_vol

        return {
            "buy_volume": buy_vol,
            "sell_volume": sell_vol,
            "total_trade_volume": tot_vol,
            "aggressor_imbalance": float(tfi),
            "buy_sell_ratio": float(bs_ratio),
            "trade_count": trade_count,
            "trade_intensity": float(intensity),
            "average_trade_size": float(avg_size),
            "signed_volume": float(signed_vol),
        }

    @staticmethod
    def compute_rolling_microstructure_series_features(micro_df: pd.DataFrame) -> pd.DataFrame:
        """Computes rolling dynamics (acceleration, volatility) on aligned microstructure series."""
        feats = micro_df.copy()

        if "ob_imbalance_l5" in feats.columns:
            # Imbalance acceleration
            feats["imbalance_accel_1"] = feats["ob_imbalance_l5"] - feats["ob_imbalance_l5"].shift(1)
            # Imbalance volatility (rolling 12-bar std)
            feats["imbalance_vol_12"] = feats["ob_imbalance_l5"].rolling(window=12, min_periods=3).std()

        if "signed_volume" in feats.columns:
            feats["signed_volume_accel"] = feats["signed_volume"] - feats["signed_volume"].shift(1)

        if "trade_count" in feats.columns:
            feats["trade_count_accel"] = feats["trade_count"] - feats["trade_count"].shift(1)

        return feats

    @staticmethod
    def compute_regime_interaction_features(
        micro_df: pd.DataFrame,
        regime_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """Computes pre-registered microstructure x regime interaction terms.
        
        Args:
            micro_df: DataFrame containing microstructure metrics (ob_imbalance_l5, spread_bps, aggressor_imbalance).
            regime_df: DataFrame containing regime flags (is_high_vol, is_trending_up, is_trending_down, regime_duration, realized_vol_12).
        """
        interactions = pd.DataFrame(index=micro_df.index)

        # 1. Imbalance x High Volatility
        if "ob_imbalance_l5" in micro_df.columns and "is_high_vol" in regime_df.columns:
            interactions["imbalance_x_highvol"] = micro_df["ob_imbalance_l5"] * regime_df["is_high_vol"]

        # 2. Imbalance x Directional Trending
        if "ob_imbalance_l5" in micro_df.columns and "is_trending_up" in regime_df.columns and "is_trending_down" in regime_df.columns:
            trend_dir = regime_df["is_trending_up"] - regime_df["is_trending_down"]
            interactions["imbalance_x_trending"] = micro_df["ob_imbalance_l5"] * trend_dir

        # 3. Trade-Flow Imbalance x High Volatility
        if "aggressor_imbalance" in micro_df.columns and "is_high_vol" in regime_df.columns:
            interactions["tfi_x_highvol"] = micro_df["aggressor_imbalance"] * regime_df["is_high_vol"]

        # 4. Spread x Volatility State
        if "spread_bps" in micro_df.columns and "realized_vol_12" in regime_df.columns:
            interactions["spread_x_volatility"] = micro_df["spread_bps"] * regime_df["realized_vol_12"]

        # 5. Imbalance x Regime Duration
        if "ob_imbalance_l5" in micro_df.columns and "regime_duration" in regime_df.columns:
            log_dur = np.log1p(regime_df["regime_duration"].fillna(1.0))
            interactions["imbalance_x_regime_duration"] = micro_df["ob_imbalance_l5"] * log_dur

        return interactions
