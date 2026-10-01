"""
Phase 12: Independent Clean-Room Audit of Phase 11 Strategy and Datasets.
This script DOES NOT import any module or class from phase11.
It independently re-implements:
- Raw data loading and verification (SHA-256, row counts, deduplication)
- 1-minute to 1-hour aggregation
- SMA50 and SMA200 indicator calculation
- Frozen strategy state machine
- Trade execution, transaction costs, compounding, drawdown, and risk metrics
- Trade-by-trade comparison against Phase 11 trade ledger
"""

import hashlib
import json
import math
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
RAW_DIR = ROOT_DIR / "phase11" / "data" / "raw"
PHASE11_REPORTS_DIR = ROOT_DIR / "phase11" / "reports"
PHASE12_REPORTS_DIR = ROOT_DIR / "phase12" / "reports"


def audit_phase11_data_and_execution() -> Dict:
    results = {}

    # 1 & 2: Raw Row Count & Deduplication
    print("--- 1. Auditing Raw Data Files & Row Counts ---")
    raw_files = [
        "DAT_MT_XAUUSD_M1_2021.csv",
        "DAT_MT_XAUUSD_M1_2022.csv",
        "DAT_MT_XAUUSD_M1_2023.csv",
        "DAT_MT_XAUUSD_M1_2024.csv",
        "DAT_MT_XAUUSD_M1_2025.csv",
    ]

    dfs = []
    raw_row_counts = {}
    raw_hashes = {}

    for fname in raw_files:
        fpath = RAW_DIR / fname
        assert fpath.exists(), f"Missing raw file: {fpath}"

        # SHA-256 Checksum
        h = hashlib.sha256()
        with open(fpath, "rb") as f:
            while chunk := f.read(1048576):
                h.update(chunk)
        raw_hashes[fname] = h.hexdigest()

        # Parse CSV
        df = pd.read_csv(
            fpath,
            header=None,
            names=["date_str", "time_str", "open", "high", "low", "close", "volume"],
        )
        raw_row_counts[fname] = len(df)
        print(f"  {fname}: {len(df):,} rows | SHA-256: {raw_hashes[fname][:16]}...")

        # Parse timestamps: HistData is Eastern Standard Time (EST, UTC-5) with no DST
        dt_est = pd.to_datetime(df["date_str"] + " " + df["time_str"], format="%Y.%m.%d %H:%M")
        dt_utc = dt_est + pd.Timedelta(hours=5)
        df["dt_utc"] = dt_utc
        df["timestamp_ms"] = dt_utc.astype("datetime64[ms]").astype("int64")
        dfs.append(df)

    combined_1m = pd.concat(dfs, ignore_index=True)
    total_raw_rows = len(combined_1m)
    print(f"\nTotal Raw Rows: {total_raw_rows:,}")

    # Deduplicate
    dup_mask = combined_1m.duplicated(subset=["timestamp_ms"], keep="first")
    num_duplicates = int(dup_mask.sum())
    clean_1m = combined_1m[~dup_mask].sort_values("timestamp_ms").reset_index(drop=True)
    dedup_rows = len(clean_1m)
    print(f"Duplicate Rows Removed: {num_duplicates:,}")
    print(f"Deduplicated Rows: {dedup_rows:,}")

    # 3 & 4: Timestamp Ordering & Timezone
    ts_diffs = clean_1m["timestamp_ms"].diff().dropna()
    is_strictly_monotonic = bool((ts_diffs > 0).all())
    print(f"Strict Timestamp Monotonicity: {is_strictly_monotonic}")

    # 5 & 6: Weekend & Session Gaps
    weekend_gaps = int((ts_diffs >= (36 * 3600 * 1000)).sum())
    intraday_gaps = int(((ts_diffs > 60000) & (ts_diffs < (36 * 3600 * 1000))).sum())
    print(f"Weekend Closures (>= 36h): {weekend_gaps} (Expected: 260)")
    print(f"Intraday / Rollover Gaps (< 36h): {intraday_gaps}")

    # 7: 1-Hour Candle Construction
    print("\n--- 2. Constructing 1-Hour OHLCV Bars ---")
    interval_ms = 3600 * 1000
    clean_1m["bucket"] = (clean_1m["timestamp_ms"] // interval_ms) * interval_ms
    df_1h = (
        clean_1m.groupby("bucket")
        .agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        })
        .reset_index()
        .rename(columns={"bucket": "timestamp_ms"})
    )
    df_1h["dt_utc"] = pd.to_datetime(df_1h["timestamp_ms"], unit="ms", utc=True)
    total_1h_bars = len(df_1h)
    print(f"Total 1-Hour Bars: {total_1h_bars:,}")

    # 8 & 9: SMA50 and SMA200 Calculation
    print("\n--- 3. Computing Independent Technical Indicators ---")
    df_1h["sma_50"] = df_1h["close"].rolling(50).mean()
    df_1h["sma_200"] = df_1h["close"].rolling(200).mean()

    # 10 to 16: Signal Generation and Next-Bar Execution Simulator
    print("\n--- 4. Executing Independent Replication of Frozen Strategy ---")
    # Invariant model:
    # At close of bar t (using info up to and including bar t):
    #   if flat and sma50(t) > sma200(t): buy at open of bar t+1
    #   if long and sma50(t) <= sma200(t): exit at open of bar t+1
    # Transaction cost: 2.0 bps half spread + 1.0 bps slippage = 3.0 bps one-way (6.0 bps RT)

    n = len(df_1h)
    opens = df_1h["open"].to_numpy()
    closes = df_1h["close"].to_numpy()
    sma50 = df_1h["sma_50"].to_numpy()
    sma200 = df_1h["sma_200"].to_numpy()
    times = df_1h["dt_utc"].astype(str).to_numpy()

    # Signals evaluated at bar close
    signals = np.zeros(n, dtype=int)
    for t in range(200, n):
        if not np.isnan(sma50[t]) and not np.isnan(sma200[t]):
            if sma50[t] > sma200[t]:
                signals[t] = 1

    friction_rate = (2.0 + 1.0) / 10000.0  # 3.0 bps one-way

    # Simulate across full 5 years
    current_pos = 0
    cash = 10000.0
    entry_idx = 0
    entry_raw = 0.0
    entry_exec = 0.0
    entry_units = 0.0
    entry_notional = 0.0

    trades = []
    trade_id = 0
    equity_series = np.zeros(n)
    peak_cash = 10000.0
    max_dd_pct = 0.0

    for i in range(n):
        if current_pos == 1:
            unrealized = entry_units * (opens[i] - entry_raw)
            eq = cash + unrealized
        else:
            eq = cash
        equity_series[i] = eq
        if eq > peak_cash:
            peak_cash = eq
        dd = (peak_cash - eq) / peak_cash
        if dd > max_dd_pct:
            max_dd_pct = dd

        # Check exit if long
        if current_pos == 1 and i > entry_idx:
            # Signal at close of bar i-1 was <= 0
            if signals[i - 1] == 0:
                # Exit at open of bar i
                exit_raw = opens[i]
                exit_exec = exit_raw * (1.0 - friction_rate)
                gross_pnl = entry_units * (exit_raw - entry_raw)
                net_pnl = entry_units * (exit_exec - entry_exec)
                friction_usd = gross_pnl - net_pnl
                cash += net_pnl
                trade_id += 1

                trades.append({
                    "trade_id": trade_id,
                    "direction": "LONG",
                    "entry_bar": entry_idx,
                    "entry_time": times[entry_idx],
                    "entry_raw": round(entry_raw, 3),
                    "entry_exec": round(entry_exec, 3),
                    "exit_bar": i,
                    "exit_time": times[i],
                    "exit_raw": round(exit_raw, 3),
                    "exit_exec": round(exit_exec, 3),
                    "bars_held": i - entry_idx,
                    "units": round(entry_units, 4),
                    "notional_usd": round(entry_notional, 2),
                    "gross_pnl_usd": round(gross_pnl, 2),
                    "friction_usd": round(friction_usd, 2),
                    "net_pnl_usd": round(net_pnl, 2),
                    "cash_after": round(cash, 2),
                })
                current_pos = 0

        # Check entry if flat
        if current_pos == 0 and i > 0 and i < n - 1:
            if signals[i - 1] == 1:
                # Enter at open of bar i
                current_pos = 1
                entry_idx = i
                entry_raw = opens[i]
                entry_exec = entry_raw * (1.0 + friction_rate)
                entry_notional = cash
                entry_units = entry_notional / entry_raw

    # Close any open trade at end
    if current_pos == 1:
        i = n - 1
        exit_raw = closes[i]
        exit_exec = exit_raw * (1.0 - friction_rate)
        gross_pnl = entry_units * (exit_raw - entry_raw)
        net_pnl = entry_units * (exit_exec - entry_exec)
        friction_usd = gross_pnl - net_pnl
        cash += net_pnl
        trade_id += 1
        trades.append({
            "trade_id": trade_id,
            "direction": "LONG",
            "entry_bar": entry_idx,
            "entry_time": times[entry_idx],
            "entry_raw": round(entry_raw, 3),
            "entry_exec": round(entry_exec, 3),
            "exit_bar": i,
            "exit_time": times[i],
            "exit_raw": round(exit_raw, 3),
            "exit_exec": round(exit_exec, 3),
            "bars_held": i - entry_idx,
            "units": round(entry_units, 4),
            "notional_usd": round(entry_notional, 2),
            "gross_pnl_usd": round(gross_pnl, 2),
            "friction_usd": round(friction_usd, 2),
            "net_pnl_usd": round(net_pnl, 2),
            "cash_after": round(cash, 2),
        })

    df_rep_trades = pd.DataFrame(trades)
    print(f"Total Replicated Trades: {len(df_rep_trades)}")
    print(f"Final Replicated Cash: ${cash:,.2f}")
    print(f"Net Realized PnL: ${cash - 10000.0:,.2f} ({(cash - 10000.0) / 10000.0 * 100.0:.2f}%)")
    print(f"Max Drawdown: {max_dd_pct * 100.0:.2f}%")

    # Re-evaluate 2025 Holdout Independently
    holdout_start_dt = pd.to_datetime("2025-01-01 00:00:00", utc=True)
    df_1h_holdout = df_1h[df_1h["dt_utc"] >= holdout_start_dt].reset_index(drop=True)
    h_opens = df_1h_holdout["open"].to_numpy()
    h_closes = df_1h_holdout["close"].to_numpy()
    h_sma50 = df_1h_holdout["sma_50"].to_numpy()
    h_sma200 = df_1h_holdout["sma_200"].to_numpy()
    h_times = df_1h_holdout["dt_utc"].astype(str).to_numpy()
    h_n = len(df_1h_holdout)

    h_signals = np.zeros(h_n, dtype=int)
    for t in range(h_n):
        if not np.isnan(h_sma50[t]) and not np.isnan(h_sma200[t]):
            if h_sma50[t] > h_sma200[t]:
                h_signals[t] = 1

    h_cash = 10000.0
    h_pos = 0
    h_entry_idx = 0
    h_entry_raw = 0.0
    h_entry_exec = 0.0
    h_entry_units = 0.0
    h_trades = []
    h_trade_id = 0
    h_peak = 10000.0
    h_max_dd = 0.0

    for i in range(h_n):
        if h_pos == 1:
            eq = h_cash + h_entry_units * (h_opens[i] - h_entry_raw)
        else:
            eq = h_cash
        if eq > h_peak:
            h_peak = eq
        h_dd = (h_peak - eq) / h_peak
        if h_dd > h_max_dd:
            h_max_dd = h_dd

        if h_pos == 1 and i > h_entry_idx:
            if h_signals[i - 1] == 0:
                exit_raw = h_opens[i]
                exit_exec = exit_raw * (1.0 - friction_rate)
                gross_pnl = h_entry_units * (exit_raw - h_entry_raw)
                net_pnl = h_entry_units * (exit_exec - h_entry_exec)
                h_cash += net_pnl
                h_trade_id += 1
                h_trades.append({
                    "trade_id": h_trade_id,
                    "net_pnl": net_pnl,
                    "gross_pnl": gross_pnl,
                    "ret": net_pnl / (h_entry_units * h_entry_raw),
                })
                h_pos = 0

        if h_pos == 0 and i > 0 and i < h_n - 1:
            if h_signals[i - 1] == 1:
                h_pos = 1
                h_entry_idx = i
                h_entry_raw = h_opens[i]
                h_entry_exec = h_entry_raw * (1.0 + friction_rate)
                h_entry_units = h_cash / h_entry_raw

    # Close open holdout trade at end if any
    if h_pos == 1:
        exit_raw = h_closes[-1]
        exit_exec = exit_raw * (1.0 - friction_rate)
        gross_pnl = h_entry_units * (exit_raw - h_entry_raw)
        net_pnl = h_entry_units * (exit_exec - h_entry_exec)
        h_cash += net_pnl
        h_trade_id += 1
        h_trades.append({
            "trade_id": h_trade_id,
            "net_pnl": net_pnl,
            "gross_pnl": gross_pnl,
            "ret": net_pnl / (h_entry_units * h_entry_raw),
        })

    h_wins = sum(1 for t in h_trades if t["net_pnl"] > 0)
    h_win_pnl = sum(t["net_pnl"] for t in h_trades if t["net_pnl"] > 0)
    h_loss_pnl = abs(sum(t["net_pnl"] for t in h_trades if t["net_pnl"] < 0))
    h_pf = (h_win_pnl / h_loss_pnl) if h_loss_pnl > 0 else 99.0
    h_rets = [t["ret"] for t in h_trades]
    h_sharpe = (np.mean(h_rets) / np.std(h_rets, ddof=1) * math.sqrt(len(h_trades))) if np.std(h_rets) > 0 else 0.0

    print("\n--- 5. Independent 2025 Holdout Re-computation ---")
    print(f"  Holdout Trades:      {len(h_trades)} (Reported: 15)")
    print(f"  Holdout Net PnL:     ${h_cash - 10000.0:,.2f} (Reported: $3,288.52)")
    print(f"  Holdout Net Return:  {(h_cash - 10000.0) / 10000.0 * 100.0:.2f}% (Reported: 32.89%)")
    print(f"  Holdout PF:          {h_pf:.2f} (Reported: 3.84)")
    print(f"  Holdout Sharpe:      {h_sharpe:.2f} (Reported: 1.30)")
    print(f"  Holdout Max DD:      {h_max_dd * 100.0:.2f}% (Reported: 15.50%)")

    # Load Phase 11 Trade Ledger for direct row-by-row comparison
    ledger_p11_path = PHASE11_REPORTS_DIR / "PHASE11_TRADE_LEDGER.csv"
    assert ledger_p11_path.exists(), f"Missing ledger: {ledger_p11_path}"
    df_p11_ledger = pd.read_csv(ledger_p11_path)

    # Compare trade-by-trade
    comp_records = []
    max_pnl_diff = 0.0

    for idx in range(min(len(df_rep_trades), len(df_p11_ledger))):
        rep = df_rep_trades.iloc[idx]
        p11 = df_p11_ledger.iloc[idx]

        pnl_diff = abs(rep["net_pnl_usd"] - p11["net_pnl_usd"])
        cash_diff = abs(rep["cash_after"] - p11["cash_after"])
        if pnl_diff > max_pnl_diff:
            max_pnl_diff = pnl_diff

        comp_records.append({
            "trade_id": rep["trade_id"],
            "p11_entry_time": p11["entry_time_utc"],
            "rep_entry_time": rep["entry_time"],
            "p11_exit_time": p11["exit_time_utc"],
            "rep_exit_time": rep["exit_time"],
            "p11_entry_exec": p11["entry_price_executed"],
            "rep_entry_exec": rep["entry_exec"],
            "p11_exit_exec": p11["exit_price_executed"],
            "rep_exit_exec": rep["exit_exec"],
            "p11_net_pnl": p11["net_pnl_usd"],
            "rep_net_pnl": rep["net_pnl_usd"],
            "pnl_diff": round(pnl_diff, 4),
            "p11_cash_after": p11["cash_after"],
            "rep_cash_after": rep["cash_after"],
            "cash_diff": round(cash_diff, 4),
            "status": "EXACT_MATCH" if cash_diff < 0.05 else "DIFF",
        })

    df_comp = pd.DataFrame(comp_records)
    rep_csv_path = PHASE12_REPORTS_DIR / "PHASE12_INDEPENDENT_REPLICATION.csv"
    df_comp.to_csv(rep_csv_path, index=False)
    print(f"\n[+] Exported Trade Comparison: {len(df_comp)} trades -> {rep_csv_path.name}")
    print(f"Max Single-Trade PnL Difference: ${max_pnl_diff:.4f}")
    print(f"Total Exact Matching Trades (< $0.05 diff): {(df_comp['status'] == 'EXACT_MATCH').sum()} / {len(df_comp)}")

    results = {
        "total_raw_rows": total_raw_rows,
        "dedup_rows": dedup_rows,
        "is_strictly_monotonic": is_strictly_monotonic,
        "weekend_gaps": weekend_gaps,
        "intraday_gaps": intraday_gaps,
        "total_1h_bars": total_1h_bars,
        "total_trades": len(df_rep_trades),
        "final_cash": cash,
        "max_drawdown_pct": max_dd_pct * 100.0,
        "holdout_trades": len(h_trades),
        "holdout_net_pnl": h_cash - 10000.0,
        "holdout_net_return": (h_cash - 10000.0) / 100.0,
        "holdout_pf": h_pf,
        "holdout_sharpe": h_sharpe,
        "holdout_max_dd": h_max_dd * 100.0,
        "max_pnl_diff": max_pnl_diff,
        "exact_match_ratio": float((df_comp["status"] == "EXACT_MATCH").mean()),
    }
    return results


if __name__ == "__main__":
    audit_phase11_data_and_execution()
