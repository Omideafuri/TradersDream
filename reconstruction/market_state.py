"""Causal Market State and Market Structure Representation.

Constructs enriched, normalized, causal market state features strictly without look-ahead bias:
- Trend: Distance to EMA20/50/200 (%), EMA slopes.
- Momentum: RSI14, RSI slope, normalized MACD histogram.
- Volatility: Normalized ATR% (ATR/Close), Bollinger Band Width%, Bollinger %B.
- Volume: Volume ratio vs 20-period volume SMA, Volume trend direction.
- Market Structure: Backwards-looking swing highs/lows, Higher High/Low / Lower High/Low,
  Break of Structure (BOS), and Range Expansion/Compression ratios.
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional
import numpy as np
import pandas as pd


@dataclass
class MarketStructureState:
    swing_high: float
    swing_low: float
    dist_to_swing_high_pct: float
    dist_to_swing_low_pct: float
    structure_type: str  # HH_HL (Uptrend), LH_LL (Downtrend), MIXED
    break_of_structure: str  # BULLISH_BOS, BEARISH_BOS, NONE
    range_expansion_ratio: float
    compression_state: str  # EXPANDED, COMPRESSED, NORMAL

    def to_dict(self) -> Dict[str, Any]:
        return {
            "swing_high": round(self.swing_high, 2),
            "swing_low": round(self.swing_low, 2),
            "dist_to_swing_high_pct": round(self.dist_to_swing_high_pct, 3),
            "dist_to_swing_low_pct": round(self.dist_to_swing_low_pct, 3),
            "structure_type": self.structure_type,
            "break_of_structure": self.break_of_structure,
            "range_expansion_ratio": round(self.range_expansion_ratio, 3),
            "compression_state": self.compression_state,
        }


@dataclass
class EnrichedMarketState:
    timestamp: str
    close: float
    # Trend Features
    dist_ema20_pct: float
    dist_ema50_pct: float
    dist_ema200_pct: float
    ema20_slope_pct: float
    ema50_slope_pct: float
    # Momentum Features
    rsi14: float
    rsi_slope_3: float
    macd_hist_norm: float
    # Volatility Features
    atr_norm_pct: float
    bb_width_pct: float
    bb_pct_b: float
    # Volume Features
    volume_ratio: float
    # Market Structure Features
    structure: MarketStructureState

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "close": round(self.close, 2),
            "dist_ema20_pct": round(self.dist_ema20_pct, 3),
            "dist_ema50_pct": round(self.dist_ema50_pct, 3),
            "dist_ema200_pct": round(self.dist_ema200_pct, 3),
            "ema20_slope_pct": round(self.ema20_slope_pct, 3),
            "ema50_slope_pct": round(self.ema50_slope_pct, 3),
            "rsi14": round(self.rsi14, 2),
            "rsi_slope_3": round(self.rsi_slope_3, 2),
            "macd_hist_norm": round(self.macd_hist_norm, 4),
            "atr_norm_pct": round(self.atr_norm_pct, 3),
            "bb_width_pct": round(self.bb_width_pct, 3),
            "bb_pct_b": round(self.bb_pct_b, 3),
            "volume_ratio": round(self.volume_ratio, 2),
            "structure": self.structure.to_dict(),
        }


def compute_enriched_market_state_df(df: pd.DataFrame) -> pd.DataFrame:
    """Computes causal enriched technical indicators and market structure on an OHLCV DataFrame.

    All computations are strictly causal: bar t only depends on values at or before bar t.
    """
    out = df.copy()

    # 1. Base Moving Averages
    if "ema20" not in out.columns:
        out["ema20"] = out["close"].ewm(span=20, adjust=False).mean()
    if "ema50" not in out.columns:
        out["ema50"] = out["close"].ewm(span=50, adjust=False).mean()
    if "ema200" not in out.columns:
        out["ema200"] = out["close"].ewm(span=200, adjust=False).mean()

    # Distances in % from EMAs
    out["dist_ema20_pct"] = (out["close"] - out["ema20"]) / out["ema20"] * 100.0
    out["dist_ema50_pct"] = (out["close"] - out["ema50"]) / out["ema50"] * 100.0
    out["dist_ema200_pct"] = (out["close"] - out["ema200"]) / out["ema200"] * 100.0

    # EMA Slopes (3-bar change in EMA normalized by EMA)
    out["ema20_slope_pct"] = (out["ema20"] - out["ema20"].shift(3)) / out["ema20"].shift(3) * 100.0
    out["ema50_slope_pct"] = (out["ema50"] - out["ema50"].shift(3)) / out["ema50"].shift(3) * 100.0

    # 2. RSI & RSI Slope
    if "rsi14" not in out.columns:
        delta = out["close"].diff()
        gain = (delta.where(delta > 0, 0.0)).ewm(alpha=1 / 14, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0.0)).ewm(alpha=1 / 14, adjust=False).mean()
        rs = gain / loss.replace(0, np.nan)
        out["rsi14"] = 100.0 - (100.0 / (1.0 + rs))
        out["rsi14"] = out["rsi14"].fillna(50.0)

    out["rsi_slope_3"] = out["rsi14"] - out["rsi14"].shift(3)

    # 3. MACD & Normalized Histogram
    ema12 = out["close"].ewm(span=12, adjust=False).mean()
    ema26 = out["close"].ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    macd_hist = macd_line - signal_line
    out["macd_hist_norm"] = (macd_hist / out["close"]) * 100.0  # normalized in % of price

    # 4. Volatility: ATR% and Bollinger Bands
    if "atr14" not in out.columns:
        high = out["high"]
        low = out["low"]
        close_prev = out["close"].shift(1)
        tr1 = high - low
        tr2 = (high - close_prev).abs()
        tr3 = (low - close_prev).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        out["atr14"] = tr.ewm(alpha=1 / 14, adjust=False).mean()

    out["atr_norm_pct"] = (out["atr14"] / out["close"]) * 100.0

    bb_sma = out["close"].rolling(window=20).mean()
    bb_std = out["close"].rolling(window=20).std(ddof=0)
    bb_upper = bb_sma + 2.0 * bb_std
    bb_lower = bb_sma - 2.0 * bb_std
    out["bb_width_pct"] = ((bb_upper - bb_lower) / bb_sma.replace(0, np.nan)) * 100.0
    bb_diff = bb_upper - bb_lower
    out["bb_pct_b"] = (out["close"] - bb_lower) / bb_diff.replace(0, np.nan)
    out["bb_pct_b"] = out["bb_pct_b"].clip(-0.5, 1.5)

    # 5. Volume Ratio
    if "volume_ratio" not in out.columns:
        vol_sma20 = out["volume"].rolling(window=20).mean()
        out["volume_ratio"] = out["volume"] / vol_sma20.replace(0, np.nan)
        out["volume_ratio"] = out["volume_ratio"].fillna(1.0)

    # 6. Causal Market Structure (Rolling Backwards-Looking Pivot Levels)
    # Pivot lookback: strictly causal window of 10 prior completed bars
    # Bar t can only reference swing levels established strictly before bar t
    lookback = 10
    prior_highs = out["high"].shift(1).rolling(window=lookback).max()
    prior_lows = out["low"].shift(1).rolling(window=lookback).min()

    # Previous-previous window for structure trend (HH/HL vs LH/LL)
    prior_prior_highs = out["high"].shift(1 + lookback).rolling(window=lookback).max()
    prior_prior_lows = out["low"].shift(1 + lookback).rolling(window=lookback).min()

    out["swing_high"] = prior_highs
    out["swing_low"] = prior_lows

    # Distances to swing levels in %
    out["dist_to_swing_high_pct"] = (out["close"] - out["swing_high"]) / out["swing_high"] * 100.0
    out["dist_to_swing_low_pct"] = (out["close"] - out["swing_low"]) / out["swing_low"] * 100.0

    # Break of Structure (BOS)
    # Bullish BOS: Current close breaks above the prior 10-bar swing high
    # Bearish BOS: Current close breaks below the prior 10-bar swing low
    bos_col = []
    struct_col = []
    for c, sh, sl, p_sh, p_sl in zip(
        out["close"], prior_highs, prior_lows, prior_prior_highs, prior_prior_lows
    ):
        if pd.isna(sh) or pd.isna(sl):
            bos_col.append("NONE")
            struct_col.append("MIXED")
            continue

        if c > sh:
            bos_col.append("BULLISH_BOS")
        elif c < sl:
            bos_col.append("BEARISH_BOS")
        else:
            bos_col.append("NONE")

        if pd.notna(p_sh) and pd.notna(p_sl):
            if sh > p_sh and sl > p_sl:
                struct_col.append("HH_HL")
            elif sh < p_sh and sl < p_sl:
                struct_col.append("LH_LL")
            else:
                struct_col.append("MIXED")
        else:
            struct_col.append("MIXED")

    out["break_of_structure"] = bos_col
    out["structure_type"] = struct_col

    # Range expansion / compression ratio (bar range vs 10-bar mean range)
    bar_range = out["high"] - out["low"]
    mean_bar_range = bar_range.shift(1).rolling(window=10).mean()
    out["range_expansion_ratio"] = bar_range / mean_bar_range.replace(0, np.nan)
    out["range_expansion_ratio"] = out["range_expansion_ratio"].fillna(1.0)

    compression_col = []
    for r in out["range_expansion_ratio"]:
        if r > 1.5:
            compression_col.append("EXPANDED")
        elif r < 0.7:
            compression_col.append("COMPRESSED")
        else:
            compression_col.append("NORMAL")
    out["compression_state"] = compression_col

    return out


def extract_enriched_market_state(df: pd.DataFrame, idx: int) -> EnrichedMarketState:
    """Extracts a strongly-typed EnrichedMarketState object from an enriched DataFrame at index idx."""
    row = df.iloc[idx]
    ts = str(row.get("timestamp", ""))

    structure = MarketStructureState(
        swing_high=float(row.get("swing_high", row["close"])),
        swing_low=float(row.get("swing_low", row["close"])),
        dist_to_swing_high_pct=float(row.get("dist_to_swing_high_pct", 0.0)),
        dist_to_swing_low_pct=float(row.get("dist_to_swing_low_pct", 0.0)),
        structure_type=str(row.get("structure_type", "MIXED")),
        break_of_structure=str(row.get("break_of_structure", "NONE")),
        range_expansion_ratio=float(row.get("range_expansion_ratio", 1.0)),
        compression_state=str(row.get("compression_state", "NORMAL")),
    )

    return EnrichedMarketState(
        timestamp=ts,
        close=float(row["close"]),
        dist_ema20_pct=float(row.get("dist_ema20_pct", 0.0)),
        dist_ema50_pct=float(row.get("dist_ema50_pct", 0.0)),
        dist_ema200_pct=float(row.get("dist_ema200_pct", 0.0)),
        ema20_slope_pct=float(row.get("ema20_slope_pct", 0.0)),
        ema50_slope_pct=float(row.get("ema50_slope_pct", 0.0)),
        rsi14=float(row.get("rsi14", 50.0)),
        rsi_slope_3=float(row.get("rsi_slope_3", 0.0)),
        macd_hist_norm=float(row.get("macd_hist_norm", 0.0)),
        atr_norm_pct=float(row.get("atr_norm_pct", 0.0)),
        bb_width_pct=float(row.get("bb_width_pct", 0.0)),
        bb_pct_b=float(row.get("bb_pct_b", 0.5)),
        volume_ratio=float(row.get("volume_ratio", 1.0)),
        structure=structure,
    )
