# PHASE 11 — MARKET REGIME & TRADING SESSION DECOMPOSITION

**Phase:** Phase 11 — Quantitative XAU/USD Research Track  
**Strategy Identifier:** `XAUUSD_FROZEN_SMA50_200_1H`  
**Dataset:** 5-Year Authentic XAU/USD 1-Hour Spot (`2021-01-03` to `2025-12-31`)  
**Auditor:** Quantitative Market Microstructure & Macro Regime Research Group  

---

## 1. Trading Session Decomposition

Spot Gold trades 24 hours a day during weekdays, but liquidity, volatility, and order flow vary significantly across the major financial centers:

* **Asian Session:** `00:00` to `08:00 UTC` (Tokyo, Singapore, Hong Kong, Sydney)
* **London Session:** `08:00` to `13:00 UTC` (London LBMA market fix, European open)
* **New York Session:** `13:00` to `21:00 UTC` (US economic releases, COMEX pit hours, NY cash close)
* **Overnight / Rollover:** `21:00` to `24:00 UTC` (Daily bank swap maintenance)

### Empirical Breakdown by Entry Session (84 Trades):

| Session Name | Trade Count | Win Rate (%) | Total Net PnL ($) | Avg Net PnL / Trade ($) | Avg Return (bps) | Share of Total Profit (%) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **London** | **22** | **50.0%** | **+$3,297.72** | **+$149.90** | **+131.5 bps** | **40.5%** |
| **Overnight / Rollover** | **5** | **60.0%** | **+$3,059.68** | **+$611.94** | **+414.6 bps** | **37.6%** |
| **Asian** | **28** | **42.9%** | **+$2,263.02** | **+$80.82** | **+66.4 bps** | **27.8%** |
| **New York** | **29** | **34.5%** | **-$482.52** | **-$16.64** | **-13.3 bps** | **-5.9%** |

### Microstructure Insights:
1. **London & Asian Initiation Advantage:** Trends initiated during London and late Asian hours represent institutional macro positioning and LBMA physical liquidity clearing. These moves persist across multi-day horizons.
2. **New York Intraday Noise:** New York session signals frequently coincide with high-volatility US macroeconomic data releases (CPI, Non-Farm Payrolls, FOMC announcements), which often trigger whipsaws and intraday false breakouts before returning to the broader trend.

---

## 2. Macro Volatility & Trend Regime Breakdown

| Macro Market Regime | Total Hours in Regime | Strategy Position | Total Realized PnL ($) | Win Rate (%) | Strategic Behavior |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Bullish Trend Regime** (Price $>$ SMA 200) | 14,820 hrs (51.5%) | 84 Trades (Long) | **+$8,137.90** | 42.9% | Participates fully in upward macro thrusts. |
| **Bearish Trend Regime** (Price $\le$ SMA 200) | 13,976 hrs (48.5%) | 0 Trades (Cash) | **$0.00** | N/A | **100% Capital Preservation** in risk-free cash. |
| **High Volatility** ($\text{ATR} > \text{Median}$) | 14,398 hrs | 46 Trades | +$5,412.30 | 45.7% | Large target expansions, high dollar gains. |
| **Low Volatility** ($\text{ATR} \le \text{Median}$) | 14,398 hrs | 38 Trades | +$2,725.60 | 39.5% | Stable, steady compounding. |

---

## 3. Regime Filter Effectiveness

The strategy's primary source of risk reduction is its asymmetric exposure:
* During secular bull runs (2024–2025), it captures multi-hundred-dollar trend expansions.
* During brutal macro tightening cycles (such as 2022, when gold dropped from $2,070 to $1,614), the strategy spent months completely flat in cash, avoiding severe portfolio destruction.
