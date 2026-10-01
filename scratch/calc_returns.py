import numpy as np
import pandas as pd

df = pd.read_csv("phase12/reports/PHASE12_TRADE_LEDGER.csv")
df["exit_dt"] = pd.to_datetime(df["exit_dt"])
df["year"] = df["exit_dt"].dt.year

print("--- ANNUAL RETURNS ---")
for yr in range(2021, 2026):
    sub = df[df["year"] == yr]
    pnl = sub["net_pnl"].sum()
    pct = pnl / (sub["ending_equity"].iloc[0] - sub["net_pnl"].iloc[0]) * 100.0 if len(sub) > 0 else 0.0
    print(f"{yr}: Trades={len(sub)}, Net PnL=${pnl:.2f}")

cum_ret = (18134.88 / 10000.0 - 1.0) * 100.0
cagr = ((18134.88 / 10000.0) ** (1.0 / 5.0) - 1.0) * 100.0
print(f"Cumulative Return: {cum_ret:.2f}%")
print(f"CAGR: {cagr:.2f}%")

rets = df["return_pct"].to_numpy()
downside = rets[rets < 0]
downside_std = np.sqrt(np.mean(downside**2))
trades_per_year = len(rets) / 5.0
sharpe = (np.mean(rets) / np.std(rets, ddof=1)) * np.sqrt(trades_per_year)
sortino = (np.mean(rets) / downside_std) * np.sqrt(trades_per_year)
print(f"Annualized Sharpe (Trade-level): {sharpe:.3f}")
print(f"Annualized Sortino (Trade-level): {sortino:.3f}")
