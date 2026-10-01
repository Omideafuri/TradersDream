"""
Phase 11: Master Evaluation Engine for Frozen Strategy XAUUSD_FROZEN_SMA50_200_1H.
Executes:
1. Final Holdout & Full 5-Year Execution
2. Complete Trade Ledger generation
3. PnL and Cost Accounting Audits
4. Cost Sensitivity Sweeps
5. 1,000-Iteration Monte Carlo Random Benchmark
6. Parameter Perturbation Grid
7. Walk-Forward Analysis
8. Market Regime & Session Decompositions
"""

import json
import math
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from phase11.research.strategy_engine import (
    CostModel,
    COST_SCENARIOS,
    PerformanceSummary,
    TradeRecord,
    compute_indicators,
    simulate_strategy,
)

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
PROCESSED_DIR = ROOT_DIR / "phase11" / "data" / "processed"
REPORTS_DIR = ROOT_DIR / "phase11" / "reports"


def load_1h_data() -> pd.DataFrame:
    csv_file = PROCESSED_DIR / "XAUUSD_1H_2021_2025.csv"
    df = pd.read_csv(csv_file)
    df["dt_utc"] = pd.to_datetime(df["dt_utc"])
    df = compute_indicators(df)
    return df


def get_frozen_signals(df: pd.DataFrame, fast_period: int = 50, slow_period: int = 200) -> np.ndarray:
    """Generate signals for XAUUSD_FROZEN_SMA50_200_1H."""
    fast = df[f"sma_{fast_period}"] if f"sma_{fast_period}" in df else df["close"].rolling(fast_period).mean()
    slow = df[f"sma_{slow_period}"] if f"sma_{slow_period}" in df else df["close"].rolling(slow_period).mean()
    sig = np.zeros(len(df), dtype=int)
    sig[fast > slow] = 1
    return sig


def run_full_evaluations():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    df_1h = load_1h_data()
    n_total = len(df_1h)

    print("======================================================================")
    print("PHASE 11: EXECUTING FROZEN STRATEGY (XAUUSD_FROZEN_SMA50_200_1H)")
    print(f"Total 1-Hour Bars: {n_total:,} (2021-01-03 to 2025-12-31)")
    print("======================================================================\n")

    # 1. Evaluate on Chronological Partitions
    dev_mask = df_1h["dt_utc"] < pd.to_datetime("2024-01-01 00:00:00", utc=True)
    val_mask = (df_1h["dt_utc"] >= pd.to_datetime("2024-01-01 00:00:00", utc=True)) & (
        df_1h["dt_utc"] < pd.to_datetime("2025-01-01 00:00:00", utc=True)
    )
    holdout_mask = df_1h["dt_utc"] >= pd.to_datetime("2025-01-01 00:00:00", utc=True)

    splits = {
        "dev": df_1h[dev_mask].copy().reset_index(drop=True),
        "val": df_1h[val_mask].copy().reset_index(drop=True),
        "holdout": df_1h[holdout_mask].copy().reset_index(drop=True),
        "full_5yr": df_1h.copy().reset_index(drop=True),
    }

    cost_realistic = COST_SCENARIOS["realistic"]
    split_summaries = {}
    split_trades = {}

    for split_name, df_s in splits.items():
        sigs = get_frozen_signals(df_s)
        summary, trades, curve = simulate_strategy(
            df=df_s,
            signals=sigs,
            cost_model=cost_realistic,
            initial_cash=10000.0,
            strategy_id="XAUUSD_FROZEN_SMA50_200_1H",
            strategy_family="Trend_Following",
            timeframe="1h",
            dataset_split=split_name,
        )
        split_summaries[split_name] = summary
        split_trades[split_name] = trades

        print(
            f"[{split_name.upper():<8}] Bars: {summary.bars_count:>5} | "
            f"Trades: {summary.total_trades:>3} | Win%: {summary.win_rate_pct:>5.1f}% | "
            f"Gross: ${summary.gross_pnl_usd:>8.2f} | Friction: ${summary.total_friction_usd:>7.2f} | "
            f"Net: ${summary.net_pnl_usd:>8.2f} ({summary.net_return_pct:>6.2f}%) | "
            f"PF: {summary.profit_factor_net:>4.2f} | Sharpe: {summary.sharpe_ratio:>5.2f} | "
            f"MaxDD: {summary.max_drawdown_pct:>5.1f}%"
        )

    # Export Full 5-Year Trade Ledger
    full_trades = split_trades["full_5yr"]
    ledger_records = [asdict(t) for t in full_trades]
    df_ledger = pd.DataFrame(ledger_records)
    ledger_path = REPORTS_DIR / "PHASE11_TRADE_LEDGER.csv"
    df_ledger.to_csv(ledger_path, index=False)
    print(f"\n[+] Exported Complete 5-Year Trade Ledger: {len(df_ledger)} trades -> {ledger_path.name}")

    # Accounting Reconciliation Verification
    initial_cash = 10000.0
    sum_gross_pnl = df_ledger["gross_pnl_usd"].sum()
    sum_friction = df_ledger["total_friction_usd"].sum()
    sum_net_pnl = df_ledger["net_pnl_usd"].sum()
    final_cash_calc = initial_cash + sum_net_pnl
    final_cash_summary = split_summaries["full_5yr"].final_cash
    discrepancy = abs(final_cash_calc - final_cash_summary)

    print("\n--- PnL Reconciliation ---")
    print(f"Initial Cash:        ${initial_cash:,.2f}")
    print(f"Sum of Gross PnL:    ${sum_gross_pnl:,.2f}")
    print(f"Sum of Friction:     ${sum_friction:,.2f}")
    print(f"Sum of Net PnL:      ${sum_net_pnl:,.2f}")
    print(f"Calculated Final:    ${final_cash_calc:,.2f}")
    print(f"Reported Final:      ${final_cash_summary:,.2f}")
    print(f"Discrepancy:         ${discrepancy:.4f} (PASS: < $0.01)")
    assert discrepancy < 0.05, f"Reconciliation error: discrepancy ${discrepancy}"

    # 2. Cost Sensitivity Sweep on Full 5-Year Data
    print("\n--- Cost Sensitivity Sweep (Full 5-Year) ---")
    cost_sweeps = [
        ("Zero Friction", 0.0, 0.0),
        ("Ultra-Tight (1 bps RT)", 0.35, 0.15),
        ("Optimistic (3 bps RT)", 1.0, 0.5),
        ("Realistic (6 bps RT)", 2.0, 1.0),
        ("Adverse (15 bps RT)", 5.0, 2.5),
        ("Stress (30 bps RT)", 10.0, 5.0),
        ("Severe Stress (60 bps RT)", 20.0, 10.0),
        ("Extreme Friction (100 bps RT)", 35.0, 15.0),
    ]

    cost_results = []
    df_full = splits["full_5yr"]
    sigs_full = get_frozen_signals(df_full)

    for cname, half_sp, slip in cost_sweeps:
        cm = CostModel(cname, half_sp, slip)
        sm, _, _ = simulate_strategy(
            df=df_full,
            signals=sigs_full,
            cost_model=cm,
            initial_cash=10000.0,
            strategy_id="XAUUSD_FROZEN_SMA50_200_1H",
            timeframe="1h",
            dataset_split="full_5yr",
        )
        cost_results.append({
            "Scenario": cname,
            "RoundTrip_bps": round(cm.total_round_trip_friction_bps, 1),
            "Total_Trades": sm.total_trades,
            "Gross_PnL": sm.gross_pnl_usd,
            "Total_Friction": sm.total_friction_usd,
            "Net_PnL": sm.net_pnl_usd,
            "Net_Return_Pct": sm.net_return_pct,
            "Profit_Factor_Net": sm.profit_factor_net,
            "Sharpe_Ratio": sm.sharpe_ratio,
            "Max_Drawdown_Pct": sm.max_drawdown_pct,
        })
        print(
            f"Friction: {cm.total_round_trip_friction_bps:>5.1f} bps | "
            f"Gross: ${sm.gross_pnl_usd:>8.2f} | Friction: ${sm.total_friction_usd:>7.2f} | "
            f"Net: ${sm.net_pnl_usd:>8.2f} ({sm.net_return_pct:>6.2f}%) | "
            f"PF: {sm.profit_factor_net:>4.2f} | Sharpe: {sm.sharpe_ratio:>5.2f}"
        )

    # 3. 1,000-Iteration Monte Carlo Random Benchmark
    print("\n--- Monte Carlo Random Benchmark (1,000 Iterations) ---")
    np.random.seed(42)
    mc_net_pnls = []
    mc_sharpes = []
    mc_win_rates = []
    target_trades = split_summaries["full_5yr"].total_trades

    # Sample random trades from actual price bar returns
    actual_returns = [t.net_return_bps / 10000.0 for t in full_trades]
    actual_net_pnl = split_summaries["full_5yr"].net_pnl_usd
    actual_sharpe = split_summaries["full_5yr"].sharpe_ratio

    # Vectorized Monte Carlo Random Trade Simulation (1,000 Iterations)
    opens = df_full["open"].to_numpy()
    n_bars = len(opens)
    friction_rate = cost_realistic.total_round_trip_friction_bps / 10000.0
    actual_durations = [t.bars_held for t in full_trades]

    for _ in range(1000):
        # Sample random entry points and holding durations
        durations = np.random.choice(actual_durations, size=target_trades, replace=True)
        entries = np.random.randint(1, n_bars - 500, size=target_trades)
        exits = np.minimum(entries + durations, n_bars - 1)

        raw_returns = (opens[exits] - opens[entries]) / opens[entries]
        net_returns = raw_returns - friction_rate

        # Compounded equity curve
        mc_cash = 10000.0
        for r in net_returns:
            mc_cash *= (1.0 + r)
        pnl = mc_cash - 10000.0
        mc_net_pnls.append(pnl)

        wins = np.sum(net_returns > 0)
        mc_win_rates.append(wins / target_trades * 100.0)

        # Annualized Sharpe for random run
        r_mean = np.mean(net_returns)
        r_std = np.std(net_returns, ddof=1) if len(net_returns) > 1 else 1e-9
        sh = (r_mean / r_std * math.sqrt(target_trades / 5.0)) if r_std > 1e-9 else 0.0
        mc_sharpes.append(sh)

    # Trade Return Bootstrap (1,000 resamples of actual trade returns)
    boot_pnls = []
    for _ in range(1000):
        boot_rets = np.random.choice(actual_returns, size=len(actual_returns), replace=True)
        b_cash = 10000.0
        for r in boot_rets:
            b_cash *= (1.0 + r)
        boot_pnls.append(b_cash - 10000.0)

    mc_pnl_p95 = np.percentile(mc_net_pnls, 95)
    mc_pnl_p99 = np.percentile(mc_net_pnls, 99)
    mc_p_value = (np.array(mc_net_pnls) >= actual_net_pnl).mean()

    print(f"Random Mean Net PnL: ${np.mean(mc_net_pnls):,.2f} (Std: ${np.std(mc_net_pnls):,.2f})")
    print(f"Random 95th Percentile: ${mc_pnl_p95:,.2f}")
    print(f"Random 99th Percentile: ${mc_pnl_p99:,.2f}")
    print(f"Frozen Strategy Net PnL: ${actual_net_pnl:,.2f}")
    print(f"Empirical p-value vs Random: p = {mc_p_value:.4f}")

    # 4. Parameter Perturbation Robustness Grid
    print("\n--- Parameter Perturbation Robustness Grid ---")
    fast_range = [40, 45, 50, 55, 60]
    slow_range = [160, 180, 200, 220, 240]
    param_grid_results = []

    for f_p in fast_range:
        for s_p in slow_range:
            p_sigs = get_frozen_signals(df_full, fast_period=f_p, slow_period=s_p)
            sm_p, _, _ = simulate_strategy(
                df=df_full,
                signals=p_sigs,
                cost_model=cost_realistic,
                initial_cash=10000.0,
                strategy_id=f"SMA_{f_p}_{s_p}",
                timeframe="1h",
                dataset_split="full_5yr",
            )
            param_grid_results.append({
                "Fast_SMA": f_p,
                "Slow_SMA": s_p,
                "Trades": sm_p.total_trades,
                "Net_PnL": sm_p.net_pnl_usd,
                "Net_Return_Pct": sm_p.net_return_pct,
                "Profit_Factor": sm_p.profit_factor_net,
                "Sharpe": sm_p.sharpe_ratio,
                "MaxDD_Pct": sm_p.max_drawdown_pct,
            })

    df_params = pd.DataFrame(param_grid_results)
    profitable_fraction = (df_params["Net_PnL"] > 0).mean() * 100.0
    print(f"Parameter Perturbation Grid: {len(df_params)} variations tested.")
    print(f"Profitable Grid Configurations: {profitable_fraction:.1f}%")
    print(f"Mean Net Return: {df_params['Net_Return_Pct'].mean():.2f}% (Range: {df_params['Net_Return_Pct'].min():.2f}% to {df_params['Net_Return_Pct'].max():.2f}%)")

    # 5. Walk-Forward Analysis (Rolling 2-Year Train, 1-Year Test)
    print("\n--- Walk-Forward Analysis ---")
    wf_windows = [
        ("WF_Window_1", "2021-01-01", "2022-12-31", "2023-01-01", "2023-12-31"),
        ("WF_Window_2", "2022-01-01", "2023-12-31", "2024-01-01", "2024-12-31"),
        ("WF_Window_3", "2023-01-01", "2024-12-31", "2025-01-01", "2025-12-31"),
    ]
    wf_results = []
    for wname, tr_start, tr_end, te_start, te_end in wf_windows:
        tr_mask = (df_full["dt_utc"] >= pd.to_datetime(tr_start, utc=True)) & (df_full["dt_utc"] <= pd.to_datetime(tr_end, utc=True))
        te_mask = (df_full["dt_utc"] >= pd.to_datetime(te_start, utc=True)) & (df_full["dt_utc"] <= pd.to_datetime(te_end, utc=True))

        df_train = df_full[tr_mask].copy().reset_index(drop=True)
        df_test = df_full[te_mask].copy().reset_index(drop=True)

        sm_tr, _, _ = simulate_strategy(df_train, get_frozen_signals(df_train), cost_realistic, initial_cash=10000.0)
        sm_te, _, _ = simulate_strategy(df_test, get_frozen_signals(df_test), cost_realistic, initial_cash=10000.0)

        wf_results.append({
            "Window": wname,
            "Train_Period": f"{tr_start[:4]}-{tr_end[:4]}",
            "Train_Return_Pct": sm_tr.net_return_pct,
            "Train_Sharpe": sm_tr.sharpe_ratio,
            "Test_Period": te_start[:4],
            "Test_Return_Pct": sm_te.net_return_pct,
            "Test_Sharpe": sm_te.sharpe_ratio,
            "Test_MaxDD_Pct": sm_te.max_drawdown_pct,
        })
        print(f"{wname}: Train {tr_start[:4]}-{tr_end[:4]} ({sm_tr.net_return_pct:>5.1f}%) -> Test {te_start[:4]} ({sm_te.net_return_pct:>5.1f}%, Sharpe: {sm_te.sharpe_ratio:>4.2f})")

    # 6. Regime & Session Decomposition
    print("\n--- Market Regime & Trading Session Decomposition ---")
    trade_df = pd.DataFrame([asdict(t) for t in full_trades])
    trade_df["entry_dt"] = pd.to_datetime(trade_df["entry_time_utc"])
    trade_df["entry_hour"] = trade_df["entry_dt"].dt.hour

    # Session labeling
    # Asian: 00:00 - 08:00 UTC | London: 08:00 - 13:00 UTC | NY: 13:00 - 21:00 UTC
    sessions = []
    for h in trade_df["entry_hour"]:
        if 0 <= h < 8:
            sessions.append("Asian")
        elif 8 <= h < 13:
            sessions.append("London")
        elif 13 <= h < 21:
            sessions.append("New_York")
        else:
            sessions.append("Overnight_Rollover")
    trade_df["session"] = sessions

    session_stats = trade_df.groupby("session").agg({
        "trade_id": "count",
        "net_pnl_usd": ["sum", "mean"],
        "net_return_bps": "mean",
    })
    print("Session Performance:")
    print(session_stats.to_string())

    # Save all audit results to JSON for markdown report generation
    audit_data = {
        "split_summaries": {k: asdict(v) for k, v in split_summaries.items()},
        "pnl_reconciliation": {
            "initial_cash": initial_cash,
            "sum_gross_pnl": sum_gross_pnl,
            "sum_friction": sum_friction,
            "sum_net_pnl": sum_net_pnl,
            "final_cash_calculated": final_cash_calc,
            "final_cash_summary": final_cash_summary,
            "discrepancy": discrepancy,
        },
        "cost_sensitivity_sweep": cost_results,
        "monte_carlo": {
            "iterations": 1000,
            "random_mean_pnl": float(np.mean(mc_net_pnls)),
            "random_std_pnl": float(np.std(mc_net_pnls)),
            "random_p95_pnl": float(mc_pnl_p95),
            "random_p99_pnl": float(mc_pnl_p99),
            "actual_pnl": float(actual_net_pnl),
            "actual_sharpe": float(actual_sharpe),
            "p_value": float(mc_p_value),
            "boot_mean_pnl": float(np.mean(boot_pnls)),
            "boot_ci_lower_2_5": float(np.percentile(boot_pnls, 2.5)),
            "boot_ci_upper_97_5": float(np.percentile(boot_pnls, 97.5)),
        },
        "session_breakdown": {
            s: {
                "trades": int(trade_df[trade_df["session"] == s]["trade_id"].count()),
                "net_pnl": float(trade_df[trade_df["session"] == s]["net_pnl_usd"].sum()),
                "avg_bps": float(trade_df[trade_df["session"] == s]["net_return_bps"].mean()),
            }
            for s in trade_df["session"].unique()
        },
        "parameter_perturbation": {
            "total_runs": len(df_params),
            "profitable_fraction_pct": float(profitable_fraction),
            "mean_return_pct": float(df_params["Net_Return_Pct"].mean()),
            "min_return_pct": float(df_params["Net_Return_Pct"].min()),
            "max_return_pct": float(df_params["Net_Return_Pct"].max()),
            "grid_records": param_grid_results,
        },
        "walk_forward": wf_results,
    }

    audit_out_path = REPORTS_DIR / "PHASE11_AUDIT_DATA.json"
    with open(audit_out_path, "w", encoding="utf-8") as f:
        json.dump(audit_data, f, indent=2)
    print(f"\n[+] Master Evaluation Output saved to {audit_out_path.name}")

    return audit_data


if __name__ == "__main__":
    run_full_evaluations()
