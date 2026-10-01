"""
XAU/USD ML Research Track — Feature Engineering Pipeline
Strictly causal, zero look-ahead bias feature extraction for 1-hour OHLCV bars.
"""

from typing import List, Tuple
import numpy as np
import pandas as pd

FEATURE_NAMES: List[str] = [
    # A. Price / Return Features (6)
    "ret_1h",
    "ret_2h",
    "ret_4h",
    "ret_8h",
    "ret_12h",
    "ret_24h",
    # B. Trend & Moving Average Features (7)
    "dist_sma50",
    "dist_sma200",
    "sma50_diff_sma200",
    "sma50_ratio_sma200",
    "sma50_slope",
    "sma200_slope",
    "sma_trend_regime",
    # C. Volatility Features (5)
    "atr14_norm",
    "volatility_24h",
    "range_1h",
    "range_4h",
    "range_24h",
    # D. Momentum & Breakout Features (2)
    "rsi14",
    "breakout_dist_24h",
    # E. Market Structure / Volume Features (2)
    "vol_ratio_24h",
    "vol_change_1h",
    # F. Cyclical Time Context (2)
    "hour_sin",
    "hour_cos",
]

WARMUP_BARS: int = 210  # 200 bars for SMA200 + 10 bars for SMA200 slope


def compute_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Computes all 24 causal features for the given 1-hour OHLCV DataFrame.

    Invariants:
    1. Every feature is computed using information available strictly at or before Close(t).
    2. Zero forward-looking shifts (no shift(-k)).
    3. Warmup periods produce NaNs for the first 210 bars, which must be dropped or handled causally.
    """
    df_feat = df.copy()

    # Ensure required columns exist
    req_cols = ["open", "high", "low", "close", "volume", "dt_utc"]
    for col in req_cols:
        if col not in df_feat.columns:
            raise ValueError(f"Missing required column: {col}")

    c = df_feat["close"]
    h = df_feat["high"]
    l = df_feat["low"]
    v = df_feat["volume"]
    dt = pd.to_datetime(df_feat["dt_utc"], utc=True)

    # --- A. Price / Return Features ---
    df_feat["ret_1h"] = c.pct_change(1)
    df_feat["ret_2h"] = c.pct_change(2)
    df_feat["ret_4h"] = c.pct_change(4)
    df_feat["ret_8h"] = c.pct_change(8)
    df_feat["ret_12h"] = c.pct_change(12)
    df_feat["ret_24h"] = c.pct_change(24)

    # --- B. Trend & Moving Average Features ---
    sma50 = c.rolling(50).mean()
    sma200 = c.rolling(200).mean()

    df_feat["dist_sma50"] = (c - sma50) / sma50
    df_feat["dist_sma200"] = (c - sma200) / sma200
    df_feat["sma50_diff_sma200"] = (sma50 - sma200) / c
    df_feat["sma50_ratio_sma200"] = (sma50 / sma200) - 1.0
    df_feat["sma50_slope"] = (sma50 - sma50.shift(5)) / (5.0 * c)
    df_feat["sma200_slope"] = (sma200 - sma200.shift(10)) / (10.0 * c)
    df_feat["sma_trend_regime"] = (sma50 > sma200).astype(float)

    # --- C. Volatility Features ---
    prev_close = c.shift(1)
    tr1 = h - l
    tr2 = (h - prev_close).abs()
    tr3 = (l - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr14 = tr.rolling(14).mean()

    df_feat["atr14_norm"] = atr14 / c
    df_feat["volatility_24h"] = df_feat["ret_1h"].rolling(24).std()
    df_feat["range_1h"] = (h - l) / c
    df_feat["range_4h"] = (h.rolling(4).max() - l.rolling(4).min()) / c
    df_feat["range_24h"] = (h.rolling(24).max() - l.rolling(24).min()) / c

    # --- D. Momentum & Breakout Features ---
    delta = c.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / (avg_loss + 1e-12)
    rsi14 = 100.0 - (100.0 / (1.0 + rs))
    df_feat["rsi14"] = rsi14 / 100.0

    low_24h = l.rolling(24).min()
    high_24h = h.rolling(24).max()
    df_feat["breakout_dist_24h"] = (c - low_24h) / (high_24h - low_24h + 1e-12)

    # --- E. Market Structure / Volume Features ---
    vol_mean_24 = v.rolling(24).mean()
    df_feat["vol_ratio_24h"] = np.where(vol_mean_24 > 0, v / (vol_mean_24 + 1e-12), 0.0)
    v_prev = v.shift(1)
    df_feat["vol_change_1h"] = np.where(v_prev > 0, (v - v_prev) / (v_prev + 1e-12), 0.0)

    # --- F. Cyclical Time Context ---
    hour_utc = dt.dt.hour
    df_feat["hour_sin"] = np.sin(2.0 * np.pi * hour_utc / 24.0)
    df_feat["hour_cos"] = np.cos(2.0 * np.pi * hour_utc / 24.0)

    return df_feat


def get_feature_matrix(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Returns (cleaned_features_df, raw_df_sliced) where rows with NaN in features
    (warmup period) are pruned.
    """
    df_feat = compute_features(df)
    valid_mask = ~df_feat[FEATURE_NAMES].isna().any(axis=1)
    return df_feat.loc[valid_mask, FEATURE_NAMES].copy(), df_feat.loc[valid_mask].copy()
