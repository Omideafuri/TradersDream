# PHASE 12 — STATISTICAL PROPERTIES & TRADE CONCENTRATION AUDIT

**Project:** Autonomous Quantitative Research & Market Microstructure Verification  
**Phase:** Phase 12 — XAU/USD Real-Market Execution Validation  
**Instrument:** `XAU/USD` (Physical Spot Gold / US Dollar)  
**Strategy Identifier:** `XAUUSD_FROZEN_SMA50_200_1H`  
**Auditor:** Quantitative Risk, Statistical Distribution & Tail Risk Group  

---

## 1. Trade Distribution & Higher Statistical Moments

The empirical net return distribution across all 84 executed trades under Tier B (Broker-Realistic Execution) was analyzed:

| Statistical Parameter | Value | Institutional Interpretation |
| :--- | :---: | :--- |
| **Total Number of Trades ($N$)** | **84** | ~17 trades/year over 5 years |
| **Winning Trades** | **36 (42.9%)** | Typical trend-following win rate ($< 50\%$) |
| **Losing Trades** | **48 (57.1%)** | Majority of trades take small losses |
| **Mean Net PnL per Trade** | **+$78.13** | Positive overall mathematical expectancy |
| **Median Net PnL per Trade** | **-$29.31** | **Negative median** (hallmark of right-skewed trend systems) |
| **Standard Deviation ($\sigma$)** | **$433.82** | High variance across individual trade outcomes |
| **Distribution Skewness** | **+3.64** | **Extremely positive right skew** (massive long right tail) |
| **Distribution Excess Kurtosis** | **+16.12** | **Heavy leptokurtic tails** (fat-tailed outlier distribution) |
| **Largest Realized Winner** | **+$2,741.12** | Trade 81 (Aug 24, 2025 to Oct 23, 2025: $3,371 $\to$ $4,087) |
| **Largest Realized Loser** | **-$690.69** | Trade 74 (May 6, 2025 to May 12, 2025: -$4.5% drawdown) |
| **Average Winner** | **+$362.19** | Average profit when trade succeeds |
| **Average Loser** | **-$134.92** | Average loss when trade fails |
| **Win/Loss Payoff Ratio** | **2.68** | Each winning dollar is nearly 3x larger than each lost dollar |

---

## 2. Trade Concentration & Outlier Dependency

Trend-following strategies inherently rely on large outliers. The table below measures the concentration of total net profit across the top trades:

| Concentration Category | Share of Total Net Profit (%) | Realized Dollar Amount ($) |
| :--- | :---: | :---: |
| **Top 1 Trade** | **41.8%** | $2,741.12 |
| **Top 3 Trades** | **71.3%** | $4,681.42 |
| **Top 5 Trades** | **91.4%** | $5,999.45 |
| **Top 10% of Trades (8 Trades)** | **117.7%** | $7,723.40 |
| **Remaining 76 Trades (90%)** | **-17.7%** | -$1,160.54 |

### Stress Exclusions (Sensitivity to Top Macro Trends):
1. **Excluding Top 1 Winner:** Strategy still generates **+$3,821.74 net profit (+38.22% net return)**.
2. **Excluding Top 3 Winners:** Strategy still generates **+$1,881.18 net profit (+18.81% net return)**.
3. **Excluding Top 5 Winners:** Strategy still generates **+$563.38 net profit (+5.63% net return)**.
4. **Excluding Top 10% (8 Trades):** Net return drops to **-11.61% (-$1,160.54 net loss)**.

---

## 3. Forensic Interpretation of Tail Dependency

This trade concentration profile is not a bug; it is the fundamental nature of systematic trend following:
- In ranging, choppy markets, the strategy suffers continuous frictional decay and small false-breakout losses (median trade: -$29.31).
- In macro trending regimes, it captures multi-hundred-dollar runs that overcome all accumulated small losses combined.
- **Risk Implication:** Missing just 3 to 5 of the biggest trend moves over a 5-year period wipes out over 90% of the strategy's total profit. Flawless execution and continuous discipline are mandatory.
