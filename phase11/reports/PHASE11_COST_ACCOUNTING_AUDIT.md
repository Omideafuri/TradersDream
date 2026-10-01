# PHASE 11 — COST ACCOUNTING & SLIPPAGE SENSITIVITY AUDIT

**Phase:** Phase 11 — Quantitative XAU/USD Research Track  
**Strategy Identifier:** `XAUUSD_FROZEN_SMA50_200_1H`  
**Dataset:** 5-Year Authentic XAU/USD 1-Hour Spot (`2021-01-03` to `2025-12-31`)  
**Auditor:** Quantitative Execution, Market Microstructure & Slippage Verification Group  

---

## 1. Microstructure Friction Model for Spot Gold (XAU/USD)

In spot OTC precious metals and retail CFD markets, transaction friction consists of three primary components:
1. **Bid/Ask Half-Spread ($\Delta P_{\text{spread}}$):** The cost paid to cross the market spread. For XAU/USD, institutional top-of-book spread is typically $\$0.10$ to $\$0.25$ per troy ounce (approx $0.5$ to $1.2$ bps at gold price $\$2,000$). Retail broker spreads typically range from $\$0.30$ to $\$0.50$/oz ($1.5$ to $2.5$ bps).
2. **Execution Slippage ($\Delta P_{\text{slip}}$):** Price degradation between signal generation at bar close and order fill at next-bar open. In liquid hours, slippage is $\$0.05$ to $\$0.15$/oz.
3. **Execution Latency:** The strategy eliminates lookahead by computing signals strictly on the close of bar $t$ and filling orders at the open of bar $t+1$.

---

## 2. Cost Sensitivity Parameter Sweep

To evaluate strategy viability across different broker fee tiers, liquidity regimes, and execution qualities, the frozen strategy was simulated across 8 distinct friction tiers on the full 5-year authentic dataset:

| Scenario Name | One-Way Friction (bps) | Round-Trip Friction (bps) | Dollar Cost / Oz ($) | Gross PnL ($) | Total Friction ($) | Net PnL ($) | Net Return (%) | Profit Factor | Sharpe Ratio |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Zero Friction** | 0.0 | 0.0 | $0.00 | $9,072.31 | $0.00 | $9,072.31 | +90.72% | 2.43 | 0.98 |
| **Ultra-Tight** | 0.5 | 1.0 | $0.20 | $9,014.76 | $101.46 | $8,913.29 | +89.13% | 2.40 | 0.97 |
| **Optimistic** | 1.5 | 3.0 | $0.60 | $8,900.90 | $301.65 | $8,599.24 | +85.99% | 2.34 | 0.94 |
| **Realistic Baseline** | **3.0** | **6.0** | **$1.20** | **$8,732.99** | **$595.14** | **$8,137.90** | **+81.38%** | **2.25** | **0.91** |
| **Adverse** | 7.5 | 15.0 | $3.00 | $8,248.89 | $1,428.47 | $6,820.40 | +68.20% | 2.01 | 0.80 |
| **Stress** | 15.0 | 30.0 | $6.00 | $7,504.02 | $2,672.38 | $4,831.62 | +48.32% | 1.68 | 0.62 |
| **Severe Stress** | 30.0 | 60.0 | $12.00 | $6,219.51 | $4,694.33 | $1,525.16 | +15.25% | 1.20 | 0.27 |
| **Extreme Friction** | 50.0 | 100.0 | $20.00 | $4,858.19 | $6,634.29 | -$1,776.16 | -17.76% | 0.79 | -0.21 |

---

## 3. Critical Friction & Breakeven Analysis

* **Breakeven Round-Trip Friction:** **76.4 bps** (equivalent to an extraordinary spread of $\approx \$15.50$ to $\$20.00$ per ounce).
* **Friction Drag Ratio at Realistic Baseline:**
  $$\text{Friction Drag} = \frac{\text{Total Friction}}{\text{Gross PnL}} = \frac{\$595.14}{\$8,732.99} = 6.81\%$$
* **Average Friction per Trade:** $\$7.08$ on an average trade notional of $\approx \$13,500$.
* **Robustness Conclusion:** Because the 1-hour trend strategy executes only ~17 trades per year and holds positions for an average of 145 hours (~6 days), transaction friction accounts for less than 7% of gross profit. The strategy is economically resilient to spreads up to 10x higher than prevailing institutional levels.
