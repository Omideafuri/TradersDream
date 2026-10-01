# PHASE 11 — STRATEGY SPECIFICATION & PARAMETER FREEZE

**Phase:** Phase 11 — Quantitative XAU/USD Research Track  
**Freeze Identifier:** `XAUUSD_FROZEN_SMA50_200_1H`  
**Date:** September 30, 2026  
**Status:** FROZEN — ZERO MODIFICATIONS PERMITTED AFTER THIS POINT  

---

## 1. Candidate Selection Rationale

Following a multi-timeframe and multi-family search across 60 strategy-timeframe-split permutations evaluated exclusively on the **Development Set (2021-2023)** and **Validation Set (2024)**, the research committee has selected:

**Strategy Identifier:** `XAUUSD_FROZEN_SMA50_200_1H`  
**Strategy Family:** Trend-Following (Long-Only Macro Momentum)  
**Selected Timeframe:** 1-Hour (`1h` / 3600 seconds)  

### Pre-Holdout Evidence (Dev + Val Only):
* **Development (2021-2023 / 3 Years):**
  - Trades: 51
  - Net Profit: +$1,982.52 (+19.83% net return on $10,000 cash)
  - Profit Factor (Net): 1.55
  - Annualized Sharpe Ratio: 0.64
  - Maximum Drawdown: 13.60%
* **Validation (2024 / 1 Year Out-of-Sample):**
  - Trades: 19
  - Net Profit: +$1,379.22 (+13.79% net return on $10,000 cash)
  - Profit Factor (Net): 2.14
  - Annualized Sharpe Ratio: 1.23
  - Maximum Drawdown: 8.34%
* **Combined Pre-Holdout Net Return:** +36.35% after full 6.0 bps round-trip friction.
* **Economic Logic:** XAU/USD exhibits multi-week directional cycles driven by real yields, central bank reserve purchases, and macroeconomic inflation expectations. Intraday mean-reversion is degraded by spread and slippage costs. Swing trend-following on the 1-hour bar provides sufficient trade duration (~160 hours / ~1 week per trade) such that 6 bps round-trip friction represents a minimal drag on gross profitability.

---

## 2. Mathematical Definition of Indicators

All calculations are strictly backward-looking with zero lookahead:

1. **Fast Simple Moving Average (50 bars):**
   $$\text{SMA}_{50}(t) = \frac{1}{50} \sum_{k=0}^{49} \text{Close}_{t-k}$$

2. **Slow Simple Moving Average (200 bars):**
   $$\text{SMA}_{200}(t) = \frac{1}{200} \sum_{k=0}^{199} \text{Close}_{t-k}$$

3. **Average True Range (14 bars):**
   $$\text{TR}_t = \max\left(\text{High}_t - \text{Low}_t, \, |\text{High}_t - \text{Close}_{t-1}|, \, |\text{Low}_t - \text{Close}_{t-1}|\right)$$
   $$\text{ATR}_{14}(t) = \frac{1}{14} \sum_{k=0}^{13} \text{TR}_{t-k}$$

---

## 3. Strict State Transition & Execution Rules

1. **State Space:**
   - $\text{State}_t \in \{0, 1\}$, where $0 = \text{FLAT (100\% Cash)}$, $1 = \text{LONG (100\% Notional)}$.
   - Short positions are strictly prohibited ($\text{Direction} \equiv \text{LONG}$).

2. **Entry Condition:**
   - At the close of 1-hour bar $t$:
     $$\text{If } \text{State}_t = 0 \text{ and } \text{SMA}_{50}(t) > \text{SMA}_{200}(t) \implies \text{Signal}_{t} = \text{BUY}$$
   - Execution occurs at the **Open of bar $t+1$**:
     $$\text{Execution Price}_{\text{entry}} = \text{Open}_{t+1} \times \left(1 + \frac{\text{half\_spread\_bps} + \text{slippage\_bps}}{10000}\right)$$

3. **Exit Condition:**
   - At the close of 1-hour bar $t$:
     $$\text{If } \text{State}_t = 1 \text{ and } \text{SMA}_{50}(t) \le \text{SMA}_{200}(t) \implies \text{Signal}_{t} = \text{CLOSE}$$
   - Execution occurs at the **Open of bar $t+1$**:
     $$\text{Execution Price}_{\text{exit}} = \text{Open}_{t+1} \times \left(1 - \frac{\text{half\_spread\_bps} + \text{slippage\_bps}}{10000}\right)$$

4. **Position Sizing & Risk Controls:**
   - Initial Capital: $\$10,000.00$.
   - Leverage: Strictly 1.0x (Cash spot equivalent).
   - Maximum Concurrent Positions: 1 (Sequential execution, zero pyramiding).
   - Units Transacted: $\text{Units} = \frac{\text{Current Cash}}{\text{Open}_{t+1}}$.

---

## 4. Frozen Parameter Table

| Parameter Name | Frozen Value | Permitted Modification |
| :--- | :---: | :---: |
| Timeframe | `1h` (3600 seconds) | NONE |
| Fast MA Type | Simple Moving Average (SMA) | NONE |
| Fast MA Period | 50 | NONE |
| Slow MA Type | Simple Moving Average (SMA) | NONE |
| Slow MA Period | 200 | NONE |
| Allowed Directions | LONG ONLY | NONE |
| Execution Timing | Next-Bar Open ($t+1$) | NONE |
| Max Leverage | 1.0x | NONE |
| Re-invest Net Profits | TRUE (Compounded) | NONE |

---

## 5. Certification of Freeze

By generating this document, `XAUUSD_FROZEN_SMA50_200_1H` is permanently locked. No parameters, thresholds, indicators, or rules may be altered regardless of the results observed during the upcoming Final Holdout (2025) evaluation.
