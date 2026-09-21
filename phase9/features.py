"""Causal Feature Engineering Module for Phase 9C.

Provides strictly point-in-time, vectorized feature extractors for:
1. Price & Return Structure (multi-horizon log returns, acceleration, dispersion, skew, kurtosis)
2. Volatility Features (realized volatility, ATR, normalized ATR, expansion, percentiles, wick asymmetry)
3. Volume & Flow Proxies (volume z-score, relative volume, acceleration, price-volume correlation, up/down ratio)
4. Market Structure (swing levels, range position, breakout states, trend persistence, compression)
5. Regime Classification (causal regime detection, regime duration)
6. Cross-Asset Dynamics (lead-lag cross returns, spread momentum, rolling correlations)
7. Rolling Historical Normalization (zero forward leakage)
"""

from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd


class FeatureEngineer:
    """Computes point-in-time, causally valid features from OHLCV market series."""

    @staticmethod
    def compute_price_return_features(df: pd.DataFrame) -> pd.DataFrame:
        """Extracts causal price return features.
        
        Horizons:
            1 bar (5m), 3 bars (15m), 6 bars (30m), 12 bars (1h), 24 bars (2h), 48 bars (4h).
        """
        feats = pd.DataFrame(index=df.index)
        close = df["close"]

        # Multi-horizon log returns
        for lag in [1, 3, 6, 12, 24, 48]:
            feats[f"ret_log_{lag}"] = np.log(close / close.shift(lag))

        # Return acceleration (change in 1-bar return)
        feats["ret_accel_1"] = feats["ret_log_1"] - feats["ret_log_1"].shift(1)

        # Rolling dispersion of 1-bar returns (standard deviation)
        for w in [12, 24, 48]:
            feats[f"ret_dispersion_{w}"] = feats["ret_log_1"].rolling(window=w).std()

        # Rolling skewness and kurtosis (48-bar window)
        feats["ret_skew_48"] = feats["ret_log_1"].rolling(window=48).skew()
        feats["ret_kurt_48"] = feats["ret_log_1"].rolling(window=48).kurt()

        return feats

    @staticmethod
    def compute_volatility_features(df: pd.DataFrame) -> pd.DataFrame:
        """Extracts causal volatility and range features."""
        feats = pd.DataFrame(index=df.index)
        close = df["close"]
        high = df["high"]
        low = df["low"]
        open_p = df["open"]

        log_ret_1 = np.log(close / close.shift(1))

        # Realized Volatility (rolling std of 1-bar returns, scaled by sqrt(288) for daily equivalent)
        for w in [12, 24, 48]:
            feats[f"realized_vol_{w}"] = log_ret_1.rolling(window=w).std() * np.sqrt(288)

        # True Range (causal)
        prev_close = close.shift(1)
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        # ATR(14)
        atr_14 = true_range.rolling(window=14).mean()
        feats["atr_14"] = atr_14
        feats["natr_14"] = atr_14 / (close + 1e-9)

        # Volatility expansion/contraction ratio (short 12 / long 48)
        feats["vol_ratio_12_48"] = feats["realized_vol_12"] / (feats["realized_vol_48"] + 1e-9)

        # Volatility percentile over past 288 bars (24h)
        feats["vol_percentile_288"] = atr_14.rolling(window=288).rank(pct=True)

        # Candle body / total range ratio
        candle_range = (high - low).replace(0, 1e-9)
        feats["body_range_ratio"] = (close - open_p).abs() / candle_range

        # Upper vs Lower wick asymmetry:
        # positive => upper wick larger (selling pressure at top), negative => lower wick larger (buying support)
        upper_wick = high - np.maximum(close, open_p)
        lower_wick = np.minimum(close, open_p) - low
        feats["wick_asymmetry"] = (upper_wick - lower_wick) / candle_range

        return feats

    @staticmethod
    def compute_volume_features(df: pd.DataFrame) -> pd.DataFrame:
        """Extracts causal volume and flow proxy features from OHLCV."""
        feats = pd.DataFrame(index=df.index)
        vol = df["volume"]
        close = df["close"]
        open_p = df["open"]
        ret_1 = close.pct_change(1)

        # Volume rolling z-score (48 bars)
        vol_mean_48 = vol.rolling(window=48).mean()
        vol_std_48 = vol.rolling(window=48).std()
        feats["volume_zscore_48"] = (vol - vol_mean_48) / (vol_std_48 + 1e-9)

        # Relative volume (ratio to 48-bar mean)
        feats["rel_volume_48"] = vol / (vol_mean_48 + 1e-9)

        # Volume acceleration (difference of relative volume)
        feats["vol_accel"] = feats["rel_volume_48"] - feats["rel_volume_48"].shift(1)

        # Price-volume rolling correlation (24 bars)
        vol_change = vol.pct_change(1)
        feats["price_vol_corr_24"] = ret_1.rolling(window=24).corr(vol_change)

        # Up-volume vs Down-volume ratio (24 bars)
        up_vol = vol.where(close > open_p, 0.0)
        down_vol = vol.where(close < open_p, 0.0)
        feats["up_down_vol_ratio_24"] = up_vol.rolling(window=24).sum() / (down_vol.rolling(window=24).sum() + 1e-9)

        # Abnormal volume flag (z-score > 2.0)
        feats["abnormal_volume_flag"] = (feats["volume_zscore_48"] > 2.0).astype(float)

        return feats

    @staticmethod
    def compute_market_structure_features(df: pd.DataFrame) -> pd.DataFrame:
        """Extracts causal market structure, swing levels, and range metrics."""
        feats = pd.DataFrame(index=df.index)
        close = df["close"]
        high = df["high"]
        low = df["low"]

        # Causal rolling extrema over prior 24 bars (strictly prior bars [t-24 .. t-1])
        prior_high_24 = high.shift(1).rolling(window=24).max()
        prior_low_24 = low.shift(1).rolling(window=24).min()

        # Normalized position within recent 24-bar range [0.0, 1.0]
        range_24 = (prior_high_24 - prior_low_24).replace(0, 1e-9)
        feats["range_position_24"] = (close - prior_low_24) / range_24

        # Distance to recent 24-bar high/low in percentage
        feats["dist_to_high_24"] = (close - prior_high_24) / close
        feats["dist_to_low_24"] = (close - prior_low_24) / close

        # Breakout state (causally evaluated at close t against prior 24-bar high/low)
        breakout = pd.Series(0.0, index=df.index)
        breakout[close > prior_high_24] = 1.0
        breakout[close < prior_low_24] = -1.0
        feats["breakout_state_24"] = breakout

        # Trend persistence: fraction of positive return bars in past 12 and 24 bars
        ret_1 = close.pct_change(1)
        feats["trend_persistence_12"] = (ret_1 > 0).rolling(window=12).mean()
        feats["trend_persistence_24"] = (ret_1 > 0).rolling(window=24).mean()

        # Range compression / expansion: 24-bar range relative to 288-bar rolling range median
        rolling_range_24 = (high.rolling(window=24).max() - low.rolling(window=24).min()) / close
        median_range_288 = rolling_range_24.rolling(window=288).median()
        feats["range_compression_ratio"] = rolling_range_24 / (median_range_288 + 1e-9)

        return feats

    @staticmethod
    def compute_regime_features(df: pd.DataFrame) -> pd.DataFrame:
        """Computes causal regime classification and duration."""
        feats = pd.DataFrame(index=df.index)
        close = df["close"]

        # Causal trend indicators
        sma_12 = close.rolling(window=12).mean()
        sma_48 = close.rolling(window=48).mean()
        ret_24 = np.log(close / close.shift(24))

        # Realized vol and baseline median
        log_ret_1 = np.log(close / close.shift(1))
        rvol_24 = log_ret_1.rolling(window=24).std()
        rvol_p80 = rvol_24.rolling(window=288).quantile(0.80)
        rvol_p20 = rvol_24.rolling(window=288).quantile(0.20)

        # Regimes:
        # 1: TRENDING_UP
        # 2: TRENDING_DOWN
        # 3: HIGH_VOLATILITY
        # 4: LOW_VOLATILITY
        # 5: RANGE_BOUND
        # 0: TRANSITION
        regime = pd.Series(0.0, index=df.index)

        # Assign mutually exclusive causal states prioritizing volatility extremes
        high_vol_cond = (rvol_24 > rvol_p80)
        low_vol_cond = (rvol_24 < rvol_p20)
        trend_up_cond = (sma_12 > sma_48) & (ret_24 > 0.005) & ~high_vol_cond
        trend_down_cond = (sma_12 < sma_48) & (ret_24 < -0.005) & ~high_vol_cond
        range_cond = (ret_24.abs() <= 0.005) & ~high_vol_cond & ~low_vol_cond

        regime[high_vol_cond] = 3.0
        regime[low_vol_cond] = 4.0
        regime[trend_up_cond] = 1.0
        regime[trend_down_cond] = 2.0
        regime[range_cond] = 5.0

        feats["regime_code"] = regime

        # Regime duration (consecutive bars in identical regime)
        regime_change = (regime != regime.shift(1)).astype(int)
        regime_group = regime_change.cumsum()
        regime_duration = regime.groupby(regime_group).cumcount() + 1
        feats["regime_duration"] = regime_duration

        # Binary one-hot regime flags
        feats["is_trending_up"] = (regime == 1.0).astype(float)
        feats["is_trending_down"] = (regime == 2.0).astype(float)
        feats["is_high_vol"] = (regime == 3.0).astype(float)
        feats["is_low_vol"] = (regime == 4.0).astype(float)
        feats["is_range_bound"] = (regime == 5.0).astype(float)

        return feats

    @classmethod
    def compute_all_single_asset_features(cls, df: pd.DataFrame) -> pd.DataFrame:
        """Extracts complete single-asset feature matrix (strictly causal)."""
        f_price = cls.compute_price_return_features(df)
        f_vol = cls.compute_volatility_features(df)
        f_volume = cls.compute_volume_features(df)
        f_struct = cls.compute_market_structure_features(df)
        f_regime = cls.compute_regime_features(df)

        all_feats = pd.concat([f_price, f_vol, f_volume, f_struct, f_regime], axis=1)
        return all_feats

    @staticmethod
    def compute_cross_asset_features(
        primary_df: pd.DataFrame,
        other_dfs: Dict[str, pd.DataFrame],
        primary_asset: str = "BTC",
    ) -> pd.DataFrame:
        """Computes point-in-time cross-asset features aligned by timestamp.
        
        Args:
            primary_df: DataFrame of target asset with 'timestamp' and 'close'.
            other_dfs: Dict of {asset_name: df} for peer assets.
            primary_asset: Name of primary asset.
            
        Returns:
            DataFrame containing causal cross-asset returns, momentum divergence, and correlations.
        """
        feats = pd.DataFrame(index=primary_df.index)
        ts_primary = primary_df["timestamp"].values
        primary_ret_12 = np.log(primary_df["close"] / primary_df["close"].shift(12))

        for peer_name, peer_df in other_dfs.items():
            if peer_name.upper() == primary_asset.upper():
                continue
            
            # Align peer close to primary timestamps strictly without lookahead
            peer_aligned = pd.merge_asof(
                primary_df[["timestamp"]],
                peer_df[["timestamp", "close"]].rename(columns={"close": f"peer_close_{peer_name}"}),
                on="timestamp",
                direction="backward",
            )
            peer_close = peer_aligned[f"peer_close_{peer_name}"]

            # Cross returns at causal lags k in [1, 2, 3, 6, 12, 24] (5m, 10m, 15m, 30m, 1h, 2h)
            for lag in [1, 3, 6, 12, 24]:
                feats[f"cross_ret_{peer_name}_lag{lag}"] = np.log(peer_close / peer_close.shift(lag))

            # Spread momentum (Primary 1h return - Peer 1h return)
            peer_ret_12 = np.log(peer_close / peer_close.shift(12))
            feats[f"cross_spread_mom_{peer_name}_12"] = primary_ret_12 - peer_ret_12

            # Rolling 48-bar correlation between primary return and peer return
            prim_ret_1 = np.log(primary_df["close"] / primary_df["close"].shift(1))
            peer_ret_1 = np.log(peer_close / peer_close.shift(1))
            feats[f"cross_corr_{peer_name}_48"] = prim_ret_1.rolling(window=48).corr(peer_ret_1)

        return feats

    @staticmethod
    def rolling_historical_standardize(
        features_df: pd.DataFrame,
        window: int = 288,
        min_periods: int = 48,
    ) -> pd.DataFrame:
        """Standardizes features using ONLY historical observations in a backward rolling window.
        
        Zero future data or global statistics are used.
        """
        norm_df = pd.DataFrame(index=features_df.index)
        for col in features_df.columns:
            s = features_df[col]
            if pd.api.types.is_numeric_dtype(s):
                rolling_mean = s.rolling(window=window, min_periods=min_periods).mean()
                rolling_std = s.rolling(window=window, min_periods=min_periods).std()
                norm_df[f"{col}_z"] = (s - rolling_mean) / (rolling_std + 1e-9)
            else:
                norm_df[col] = s
        return norm_df
