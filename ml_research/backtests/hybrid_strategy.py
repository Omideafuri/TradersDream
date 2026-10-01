"""
XAU/USD ML Research Track — Hybrid SMA50/200 + ML Filtering Strategy Backtest
Simulates and compares:
1. Frozen SMA50/200 Strategy (Phase 11/12 Baseline)
2. Standalone ML Strategy (HistGradientBoosting / RandomForest)
3. Hybrid Strategy: Frozen SMA50/200 filtered by ML Confidence >= tau*
"""

import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

BASE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BASE_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.preprocessing import StandardScaler

from ml_research.features.feature_pipeline import (
    FEATURE_NAMES,
    WARMUP_BARS,
    compute_features,
)
from ml_research.labels.label_generator import calculate_swap_days

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

DATA_PATH = REPO_ROOT / "phase11" / "data" / "processed" / "XAUUSD_1H_2021_2025.csv"
ARTIFACTS_DIR = BASE_DIR / "artifacts"

# Cost model parameters (Strict alignment with Phase 12 / Phase 13)
HALF_SPREAD_RATE: float = 0.0002      # 2.0 bps entry, 2.0 bps exit (4.0 bps RT)
SLIPPAGE_RATE: float = 0.0002         # 2.0 bps entry, 2.0 bps exit (4.0 bps RT)
COMMISSION_PER_OZ: float = 0.02      # $0.02 / oz flat fee per fill ($0.04 RT)
ANNUAL_SWAP_RATE: float = 0.035       # 3.5% annualized financing interest


def simulate_trading_system(
    df: pd.DataFrame, signals: np.ndarray, strategy_name: str, initial_cash: float = 10000.0
) -> Tuple[Dict[str, Any], pd.DataFrame]:
    """
    Executes a discrete event simulation with authentic next-bar execution:
    - Signal generated at close of bar t.
    - Execution at Open of bar t+1.
    - Entry price: Ask + slippage = Open * (1 + half_spread + slippage)
    - Exit price: Bid - slippage = Open * (1 - half_spread - slippage)
    - Broker commission: $0.02 / oz per fill
    - Overnight financing: 3.5% daily cut at 22:00 UTC (Wed triple rollover)
    """
    n = len(df)
    opens = df["open"].to_numpy()
    closes = df["close"].to_numpy()
    dts = pd.to_datetime(df["dt_utc"], utc=True).to_numpy()

    cash = initial_cash
    current_pos = 0  # 0 = flat, 1 = long
    entry_idx = 0
    entry_raw = 0.0
    entry_ask = 0.0
    entry_notional = 0.0
    entry_units = 0.0

    trades: List[Dict[str, Any]] = []
    trade_id = 0

    equity_curve = np.zeros(n)
    equity_curve[0] = initial_cash

    for i in range(1, n):
        # 1. Check Exit
        if current_pos == 1:
            # Exit if signal at t-1 was 0
            if signals[i - 1] == 0:
                exit_raw = opens[i]
                exit_bid = exit_raw * (1.0 - HALF_SPREAD_RATE - SLIPPAGE_RATE)

                entry_dt = pd.Timestamp(dts[entry_idx])
                exit_dt = pd.Timestamp(dts[i])
                swap_days = calculate_swap_days(entry_dt, exit_dt)

                gross_pnl = entry_units * (exit_raw - entry_raw)
                spread_cost = entry_units * entry_raw * HALF_SPREAD_RATE + entry_units * exit_raw * HALF_SPREAD_RATE
                slippage_cost = entry_units * entry_raw * SLIPPAGE_RATE + entry_units * exit_raw * SLIPPAGE_RATE
                comm_cost = entry_units * COMMISSION_PER_OZ * 2.0
                swap_cost = entry_notional * (ANNUAL_SWAP_RATE / 365.0) * swap_days

                net_pnl = gross_pnl - spread_cost - slippage_cost - comm_cost - swap_cost
                cash += net_pnl
                trade_id += 1

                trades.append({
                    "trade_id": trade_id,
                    "entry_time": str(entry_dt),
                    "exit_time": str(exit_dt),
                    "bars_held": i - entry_idx,
                    "swap_days": swap_days,
                    "entry_raw": entry_raw,
                    "exit_raw": exit_raw,
                    "units_oz": entry_units,
                    "notional_usd": entry_notional,
                    "gross_pnl": gross_pnl,
                    "spread_cost": spread_cost,
                    "slippage_cost": slippage_cost,
                    "comm_cost": comm_cost,
                    "swap_cost": swap_cost,
                    "net_pnl": net_pnl,
                    "net_return_pct": (net_pnl / entry_notional) * 100.0,
                    "net_return_bps": (net_pnl / entry_notional) * 10000.0,
                    "cash_after": cash,
                })
                current_pos = 0

        # 2. Check Entry
        if current_pos == 0 and i < n - 1:
            if signals[i - 1] == 1:
                current_pos = 1
                entry_idx = i
                entry_raw = opens[i]
                entry_ask = entry_raw * (1.0 + HALF_SPREAD_RATE + SLIPPAGE_RATE)
                entry_notional = cash
                entry_units = entry_notional / entry_raw

        equity_curve[i] = cash + (entry_units * (closes[i] - entry_raw) if current_pos == 1 else 0.0)

    # Force close if still open at end
    if current_pos == 1:
        i = n - 1
        exit_raw = closes[i]
        entry_dt = pd.Timestamp(dts[entry_idx])
        exit_dt = pd.Timestamp(dts[i])
        swap_days = calculate_swap_days(entry_dt, exit_dt)

        gross_pnl = entry_units * (exit_raw - entry_raw)
        spread_cost = entry_units * entry_raw * HALF_SPREAD_RATE + entry_units * exit_raw * HALF_SPREAD_RATE
        slippage_cost = entry_units * entry_raw * SLIPPAGE_RATE + entry_units * exit_raw * SLIPPAGE_RATE
        comm_cost = entry_units * COMMISSION_PER_OZ * 2.0
        swap_cost = entry_notional * (ANNUAL_SWAP_RATE / 365.0) * swap_days

        net_pnl = gross_pnl - spread_cost - slippage_cost - comm_cost - swap_cost
        cash += net_pnl
        trade_id += 1

        trades.append({
            "trade_id": trade_id,
            "entry_time": str(entry_dt),
            "exit_time": str(exit_dt),
            "bars_held": i - entry_idx,
            "swap_days": swap_days,
            "entry_raw": entry_raw,
            "exit_raw": exit_raw,
            "units_oz": entry_units,
            "notional_usd": entry_notional,
            "gross_pnl": gross_pnl,
            "spread_cost": spread_cost,
            "slippage_cost": slippage_cost,
            "comm_cost": comm_cost,
            "swap_cost": swap_cost,
            "net_pnl": net_pnl,
            "net_return_pct": (net_pnl / entry_notional) * 100.0,
            "net_return_bps": (net_pnl / entry_notional) * 10000.0,
            "cash_after": cash,
        })
        equity_curve[i] = cash

    df_trades = pd.DataFrame(trades)

    # Summary metrics
    if len(df_trades) > 0:
        net_pnls = df_trades["net_pnl"].to_numpy()
        wins = net_pnls[net_pnls > 0]
        losses = net_pnls[net_pnls < 0]
        win_rate = len(wins) / len(net_pnls) * 100.0
        sum_w = wins.sum() if len(wins) > 0 else 0.0
        sum_l = np.abs(losses.sum()) if len(losses) > 0 else 0.0
        pf = sum_w / sum_l if sum_l > 0 else (999.0 if sum_w > 0 else 0.0)

        total_net_pnl = cash - initial_cash
        cum_ret_pct = (total_net_pnl / initial_cash) * 100.0

        # Drawdown calculation
        peaks = np.maximum.accumulate(equity_curve)
        dds = (peaks - equity_curve) / peaks
        max_dd_pct = np.max(dds) * 100.0

        # Annualized Sharpe (hourly equity returns)
        eq_returns = np.diff(equity_curve) / equity_curve[:-1]
        mean_r = np.mean(eq_returns)
        std_r = np.std(eq_returns)
        sharpe = (mean_r / std_r) * np.sqrt(5900.0) if std_r > 1e-12 else 0.0

        avg_bars = df_trades["bars_held"].mean()
        avg_swap = df_trades["swap_days"].mean()
        avg_ret_bps = df_trades["net_return_bps"].mean()
    else:
        win_rate = pf = cum_ret_pct = max_dd_pct = sharpe = avg_bars = avg_swap = avg_ret_bps = 0.0
        total_net_pnl = 0.0

    summary = {
        "strategy": strategy_name,
        "initial_cash": initial_cash,
        "final_cash": round(cash, 2),
        "total_net_pnl": round(total_net_pnl, 2),
        "cumulative_return_pct": round(cum_ret_pct, 2),
        "trade_count": len(df_trades),
        "win_rate_pct": round(win_rate, 2),
        "profit_factor": round(pf, 2),
        "annualized_sharpe": round(sharpe, 2),
        "max_drawdown_pct": round(max_dd_pct, 2),
        "avg_bars_held": round(avg_bars, 1),
        "avg_swap_days": round(avg_swap, 1),
        "avg_net_return_bps": round(avg_ret_bps, 2),
    }

    return summary, df_trades


def run_hybrid_backtest():
    """
    Simulates Frozen SMA, Standalone ML, and Hybrid across:
    1. Validation 2024
    2. Holdout 2025
    3. Full 5-Year Dataset (2021-2025)
    """
    logging.info("Loading 1H dataset for Hybrid Backtest...")
    df = pd.read_csv(DATA_PATH)
    df["dt_utc"] = pd.to_datetime(df["dt_utc"], utc=True)
    df = df.sort_values("dt_utc").reset_index(drop=True)

    df_feat = compute_features(df)
    n = len(df)
    dt = df["dt_utc"]

    # 1. Base Frozen SMA50/200 Signals
    sma_sig = np.zeros(n, dtype=int)
    for t in range(WARMUP_BARS, n):
        if df_feat.loc[t, "sma_trend_regime"] == 1.0:
            sma_sig[t] = 1

    # 2. Train ML Model on Train (2021-2023) to generate out-of-sample probabilities
    from ml_research.labels.label_generator import compute_labels

    df_labels = compute_labels(df)
    train_mask = (dt < "2024-01-01 00:00:00+00:00") & (df.index >= WARMUP_BARS)
    train_idx = df[train_mask].index[:- 25]  # 24h + 1 purge

    X_train = df_feat.loc[train_idx, FEATURE_NAMES].to_numpy()
    y_train = df_labels.loc[train_idx, "target_24h"].to_numpy().astype(int)

    scaler = StandardScaler()
    X_train_sc = scaler.fit_transform(X_train)

    logging.info("Training HistGradientBoostingClassifier on 2021-2023...")
    clf = HistGradientBoostingClassifier(max_iter=100, max_depth=4, min_samples_leaf=50, random_state=42)
    clf.fit(X_train_sc, y_train)

    # Generate probabilities for entire dataset (strictly causal scaler and model)
    valid_idx = df.index[df.index >= WARMUP_BARS]
    X_all_sc = scaler.transform(df_feat.loc[valid_idx, FEATURE_NAMES].to_numpy())
    probs_valid = clf.predict_proba(X_all_sc)[:, 1]

    ml_probs = np.zeros(n, dtype=float)
    ml_probs[valid_idx] = probs_valid

    # Best frozen threshold from validation was tau* = 0.70
    frozen_tau = 0.70

    # Signals
    ml_sig = np.zeros(n, dtype=int)
    ml_sig[ml_probs >= frozen_tau] = 1

    hybrid_sig = np.zeros(n, dtype=int)
    hybrid_sig[(sma_sig == 1) & (ml_probs >= frozen_tau)] = 1

    # Define Partitions
    partitions = [
        {"name": "Validation (2024)", "mask": (dt >= "2024-01-01") & (dt < "2025-01-01")},
        {"name": "Holdout (2025)", "mask": dt >= "2025-01-01"},
        {"name": "Full 5-Year (2021-2025)", "mask": df.index >= WARMUP_BARS},
    ]

    all_summaries = []

    for part in partitions:
        p_name = part["name"]
        p_mask = part["mask"]
        df_part = df[p_mask].reset_index(drop=True)
        idx_part = df[p_mask].index

        sma_sub = sma_sig[idx_part]
        ml_sub = ml_sig[idx_part]
        hyb_sub = hybrid_sig[idx_part]

        logging.info(f"\n=======================================================")
        logging.info(f"SIMULATING PARTITION: {p_name} ({len(df_part):,} bars)")
        logging.info(f"=======================================================")

        s_sma, t_sma = simulate_trading_system(df_part, sma_sub, f"Frozen_SMA50_200 [{p_name}]")
        s_ml, t_ml = simulate_trading_system(df_part, ml_sub, f"Standalone_ML_tau={frozen_tau} [{p_name}]")
        s_hyb, t_hyb = simulate_trading_system(df_part, hyb_sub, f"Hybrid_SMA_ML [{p_name}]")

        for s in [s_sma, s_ml, s_hyb]:
            s["partition"] = p_name
            all_summaries.append(s)
            logging.info(
                f"  {s['strategy']:<35} | Trades: {s['trade_count']:>3} | Win%: {s['win_rate_pct']:>5.1f}% | "
                f"PF: {s['profit_factor']:>4.2f} | Net Return: {s['cumulative_return_pct']:>6.2f}% | "
                f"Sharpe: {s['annualized_sharpe']:>4.2f} | MaxDD: {s['max_drawdown_pct']:>5.1f}%"
            )

        if p_name == "Holdout (2025)":
            t_sma.to_csv(ARTIFACTS_DIR / "holdout_2025_trades_sma.csv", index=False)
            t_ml.to_csv(ARTIFACTS_DIR / "holdout_2025_trades_ml.csv", index=False)
            t_hyb.to_csv(ARTIFACTS_DIR / "holdout_2025_trades_hybrid.csv", index=False)

    df_sum = pd.DataFrame(all_summaries)
    df_sum.to_csv(ARTIFACTS_DIR / "hybrid_backtest_summary.csv", index=False)
    logging.info(f"\n[+] Successfully exported hybrid backtest summary to {ARTIFACTS_DIR / 'hybrid_backtest_summary.csv'}")

    return df_sum


if __name__ == "__main__":
    run_hybrid_backtest()
