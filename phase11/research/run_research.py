"""
Phase 11: Multi-Strategy Grid Evaluation across Timeframes and Chronological Splits.
Evaluates Candidate Strategies on Development (2021-2023) and Validation (2024).
Holdout (2025) is strictly locked until a final strategy is frozen.
"""

import json
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from phase11.research.strategy_engine import (
    CostModel,
    COST_SCENARIOS,
    PerformanceSummary,
    compute_indicators,
    simulate_strategy,
)

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
PROCESSED_DIR = ROOT_DIR / "phase11" / "data" / "processed"
REPORTS_DIR = ROOT_DIR / "phase11" / "reports"


def load_dataset(timeframe: str) -> pd.DataFrame:
    """Load resampled XAUUSD dataset and precompute technical indicators."""
    csv_file = PROCESSED_DIR / f"XAUUSD_{timeframe.upper()}_2021_2025.csv"
    if not csv_file.exists():
        raise FileNotFoundError(f"Missing processed file: {csv_file}")
    df = pd.read_csv(csv_file)
    df["dt_utc"] = pd.to_datetime(df["dt_utc"])
    df = compute_indicators(df)
    return df


def split_data(df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    """Split dataset chronologically into Dev (2021-2023), Val (2024), and Holdout (2025)."""
    # 2021 to 2023 = Development (60%)
    dev_mask = df["dt_utc"] < pd.to_datetime("2024-01-01 00:00:00", utc=True)
    # 2024 = Validation (20%)
    val_mask = (df["dt_utc"] >= pd.to_datetime("2024-01-01 00:00:00", utc=True)) & (
        df["dt_utc"] < pd.to_datetime("2025-01-01 00:00:00", utc=True)
    )
    # 2025 = Final Holdout (20%)
    holdout_mask = df["dt_utc"] >= pd.to_datetime("2025-01-01 00:00:00", utc=True)

    return {
        "dev": df[dev_mask].copy().reset_index(drop=True),
        "val": df[val_mask].copy().reset_index(drop=True),
        "holdout": df[holdout_mask].copy().reset_index(drop=True),
    }


# Signal Generators
def gen_baseline_buy_and_hold(df: pd.DataFrame) -> np.ndarray:
    """Baseline A: Buy & Hold (Long continuously)."""
    return np.ones(len(df), dtype=int)


def gen_baseline_sma_trend(df: pd.DataFrame, fast_period: int = 50, slow_period: int = 200) -> np.ndarray:
    """Baseline D: Simple Moving Average Trend (Fast SMA vs Slow SMA)."""
    sig = np.zeros(len(df), dtype=int)
    fast = df[f"sma_{fast_period}"] if f"sma_{fast_period}" in df else df["close"].rolling(fast_period).mean()
    slow = df[f"sma_{slow_period}"] if f"sma_{slow_period}" in df else df["close"].rolling(slow_period).mean()
    
    long_mask = fast > slow
    short_mask = fast < slow
    sig[long_mask] = 1
    sig[short_mask] = -1
    return sig


def gen_baseline_rsi_mean_reversion(df: pd.DataFrame, lower: float = 30.0, upper: float = 70.0) -> np.ndarray:
    """Baseline E: Simple RSI Overbought/Oversold Reversion."""
    sig = np.zeros(len(df), dtype=int)
    rsi = df["rsi_14"]
    sig[rsi < lower] = 1
    sig[rsi > upper] = -1
    return sig


def gen_family_a_triple_ema(df: pd.DataFrame) -> np.ndarray:
    """
    Strategy Family A: Multi-Timeframe Alignment Triple EMA Trend.
    Long: EMA20 > EMA50 > EMA200 AND RSI > 50 AND Close > EMA20
    Short: EMA20 < EMA50 < EMA200 AND RSI < 50 AND Close < EMA20
    """
    sig = np.zeros(len(df), dtype=int)
    ema20 = df["ema_20"]
    ema50 = df["ema_50"]
    ema200 = df["ema_200"]
    rsi = df["rsi_14"]
    c = df["close"]

    long_cond = (ema20 > ema50) & (ema50 > ema200) & (rsi > 50.0) & (c > ema20)
    short_cond = (ema20 < ema50) & (ema50 < ema200) & (rsi < 50.0) & (c < ema20)

    sig[long_cond] = 1
    sig[short_cond] = -1
    return sig


def gen_family_b_donchian_breakout(df: pd.DataFrame) -> np.ndarray:
    """
    Strategy Family B: Donchian Channel Volatility Breakout.
    Long: Close > Previous 20-bar High AND ATR > ATR_SMA20
    Short: Close < Previous 20-bar Low AND ATR > ATR_SMA20
    """
    sig = np.zeros(len(df), dtype=int)
    c = df["close"]
    prev_high = df["donchian_high_20"].shift(1)
    prev_low = df["donchian_low_20"].shift(1)
    atr = df["atr_14"]
    atr_ma = df["atr_sma_20"]

    long_cond = (c > prev_high) & (atr > atr_ma)
    short_cond = (c < prev_low) & (atr > atr_ma)

    sig[long_cond] = 1
    sig[short_cond] = -1
    return sig


def gen_family_c_bollinger_mr(df: pd.DataFrame) -> np.ndarray:
    """
    Strategy Family C: Bollinger Bands Mean Reversion with RSI Filter.
    Long: Close < Lower Band AND RSI < 35 (oversold)
    Short: Close > Upper Band AND RSI > 65 (overbought)
    Exit / Flat: When price crosses back to Middle Band
    """
    n = len(df)
    sig = np.zeros(n, dtype=int)
    c = df["close"].to_numpy()
    lower = df["bb_lower"].to_numpy()
    upper = df["bb_upper"].to_numpy()
    mid = df["bb_mid"].to_numpy()
    rsi = df["rsi_14"].to_numpy()

    state = 0
    for i in range(20, n):
        if state == 0:
            if c[i] < lower[i] and rsi[i] < 35.0:
                state = 1
            elif c[i] > upper[i] and rsi[i] > 65.0:
                state = -1
        elif state == 1:
            if c[i] >= mid[i]:
                state = 0
            elif c[i] > upper[i]:
                state = -1
        elif state == -1:
            if c[i] <= mid[i]:
                state = 0
            elif c[i] < lower[i]:
                state = 1
        sig[i] = state
    return sig


def gen_trend_sma_50_200_long_only(df: pd.DataFrame) -> np.ndarray:
    """Strategy: SMA 50 / 200 Golden Cross Long Only."""
    sig = np.zeros(len(df), dtype=int)
    fast = df["sma_50"]
    slow = df["sma_200"]
    sig[fast > slow] = 1
    return sig


def gen_trend_ema_20_50_long_only(df: pd.DataFrame) -> np.ndarray:
    """Strategy: EMA 20 / 50 Trend Alignment Long Only."""
    sig = np.zeros(len(df), dtype=int)
    ema20 = df["ema_20"]
    ema50 = df["ema_50"]
    ema200 = df["ema_200"]
    sig[(ema20 > ema50) & (df["close"] > ema200)] = 1
    return sig


def gen_donchian_breakout_long_only(df: pd.DataFrame) -> np.ndarray:
    """Strategy: Donchian 20-bar Breakout Long Only with EMA 200 Trend Filter."""
    n = len(df)
    sig = np.zeros(n, dtype=int)
    c = df["close"].to_numpy()
    prev_high = df["donchian_high_20"].shift(1).to_numpy()
    prev_low = df["donchian_low_20"].shift(1).to_numpy()
    ema200 = df["ema_200"].to_numpy()

    state = 0
    for i in range(20, n):
        if state == 0:
            if c[i] > prev_high[i] and c[i] > ema200[i]:
                state = 1
        elif state == 1:
            if c[i] < prev_low[i] or c[i] < ema200[i]:
                state = 0
        sig[i] = state
    return sig


def gen_family_d_regime_adaptive(df: pd.DataFrame) -> np.ndarray:
    """
    Strategy Family D: Regime-Adaptive Hybrid.
    Regime Filter: ADX(14)
    - If ADX > 25 (Strong Trend): Deploy Triple EMA Trend signals
    - If ADX < 20 (Ranging / Mean Reverting): Deploy Bollinger Mean Reversion signals
    - If 20 <= ADX <= 25 (Uncertain / Choppy): Stay Flat (Cash)
    """
    n = len(df)
    sig_trend = gen_family_a_triple_ema(df)
    sig_mr = gen_family_c_bollinger_mr(df)
    adx = df["adx_14"].to_numpy()

    sig = np.zeros(n, dtype=int)
    for i in range(n):
        if not np.isnan(adx[i]):
            if adx[i] > 25.0:
                sig[i] = sig_trend[i]
            elif adx[i] < 20.0:
                sig[i] = sig_mr[i]
            else:
                sig[i] = 0
    return sig


def run_strategy_search():
    """Run search grid across timeframes, strategies, and development/validation splits."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    timeframes = ["15m", "1h", "4h"]
    cost_model = COST_SCENARIOS["realistic"]  # 2.0 bps spread + 1.0 bps slippage = 3 bps one-way

    strategies = [
        ("BASE_BUY_HOLD", "Baseline", gen_baseline_buy_and_hold, False, 2.0),
        ("BASE_SMA_50_200", "Baseline", gen_baseline_sma_trend, False, 2.0),
        ("BASE_RSI_MR", "Baseline", gen_baseline_rsi_mean_reversion, False, 2.0),
        ("STRAT_A_TRIPLE_EMA", "Trend_Following", gen_family_a_triple_ema, True, 2.5),
        ("STRAT_B_DONCHIAN", "Breakout", gen_family_b_donchian_breakout, True, 2.0),
        ("STRAT_C_BOLLINGER_MR", "Mean_Reversion", gen_family_c_bollinger_mr, False, 1.5),
        ("STRAT_D_REGIME_ADAPTIVE", "Regime_Adaptive", gen_family_d_regime_adaptive, True, 2.5),
        ("STRAT_SMA_LONG_ONLY", "Trend_Following", gen_trend_sma_50_200_long_only, False, 2.0),
        ("STRAT_EMA_LONG_ONLY", "Trend_Following", gen_trend_ema_20_50_long_only, False, 2.0),
        ("STRAT_DONCHIAN_LONG_ONLY", "Breakout", gen_donchian_breakout_long_only, False, 2.0),
    ]

    all_summaries: List[PerformanceSummary] = []

    print("======================================================================")
    print("PHASE 11: MULTI-STRATEGY DISCOVERY & VALIDATION GRID")
    print(f"Cost Model: {cost_model.name} (Round-Trip Friction: {cost_model.total_round_trip_friction_bps:.1f} bps)")
    print("======================================================================\n")

    for tf in timeframes:
        print(f"\n--- Loading Timeframe: {tf} ---")
        df_full = load_dataset(tf)
        splits = split_data(df_full)

        print(f"  Dev bars: {len(splits['dev']):,} | Val bars: {len(splits['val']):,} | Holdout bars: {len(splits['holdout']):,}")

        for strat_id, family, gen_func, use_atr, atr_mult in strategies:
            for split_name in ["dev", "val"]:
                df_split = splits[split_name]
                sigs = gen_func(df_split)

                summary, trades, _ = simulate_strategy(
                    df=df_split,
                    signals=sigs,
                    cost_model=cost_model,
                    initial_cash=10000.0,
                    strategy_id=f"{strat_id}_{tf}",
                    strategy_family=family,
                    timeframe=tf,
                    dataset_split=split_name,
                    use_trailing_atr_stop=use_atr,
                    atr_mult=atr_mult,
                )
                all_summaries.append(summary)

                print(
                    f"[{split_name.upper():<3}] {tf:<3} | {strat_id:<23} | "
                    f"Trades: {summary.total_trades:>4} | Win%: {summary.win_rate_pct:>5.1f}% | "
                    f"Net PnL: ${summary.net_pnl_usd:>8.2f} ({summary.net_return_pct:>6.2f}%) | "
                    f"PF: {summary.profit_factor_net:>4.2f} | Sharpe: {summary.sharpe_ratio:>5.2f} | "
                    f"MaxDD: {summary.max_drawdown_pct:>5.1f}%"
                )

    # Save complete search log
    search_log_path = REPORTS_DIR / "PHASE11_STRATEGY_SEARCH_LOG.csv"
    records = [asdict(s) for s in all_summaries]
    df_log = pd.DataFrame(records)
    df_log.to_csv(search_log_path, index=False)
    print(f"\nSaved complete strategy search log: {len(df_log)} runs -> {search_log_path}")

    # Identify best candidate based on Dev + Val robustness
    # Criteria: Positive net PnL in both Dev and Val, Sharpe > 0.5, MaxDD < 25%
    val_df = df_log[df_log["dataset_split"] == "val"].set_index(["strategy_id", "timeframe"])
    dev_df = df_log[df_log["dataset_split"] == "dev"].set_index(["strategy_id", "timeframe"])

    print("\n--- Model Selection Analysis (Dev vs Val Out-of-Sample Performance) ---")
    joined = dev_df[["net_return_pct", "sharpe_ratio", "max_drawdown_pct", "profit_factor_net"]].join(
        val_df[["net_return_pct", "sharpe_ratio", "max_drawdown_pct", "profit_factor_net"]],
        lsuffix="_dev",
        rsuffix="_val",
    )
    print(joined.to_string())

    return df_log


if __name__ == "__main__":
    run_strategy_search()
