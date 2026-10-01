# PHASE 12 — FORWARD PROSPECTIVE PAPER CAPTURE SPECIFICATION

**Project:** Autonomous Quantitative Research & Market Microstructure Verification  
**Phase:** Phase 12 — XAU/USD Real-Market Execution Validation  
**Instrument:** `XAU/USD` (Physical Spot Gold / US Dollar)  
**Strategy Identifier:** `XAUUSD_FROZEN_SMA50_200_1H`  
**Execution Environment:** Strictly `PAPER_TRADING_ONLY = TRUE`  
**Live Orders Permitted:** **0 (ZERO)**  
**Leverage:** **1.0x (Unleveraged Cash Equivalent)**  

---

## 1. Objective of Forward Paper Capture

Retrospective backtests are susceptible to hindsight bias and macro regime selection.

The objective of Phase 12 Forward Paper Capture is to run `XAUUSD_FROZEN_SMA50_200_1H` continuously in forward prospective time without modifying any rules, recording live incoming prices, indicator updates, signal states, simulated execution fills, and fees.

---

## 2. System Architecture & Components

1. **State Machine (`phase12/dashboard/paper_monitor.py`):**
   - Continuously maintains the current strategy state:
     * `FLAT` (100% Cash) or `LONG` (100% Equity).
   - Tracks live indicator values: $\text{SMA}_{50}$, $\text{SMA}_{200}$, $\text{Current Spread}$.
2. **Forward Ledger (`phase12/data/forward_paper_ledger.csv`):**
   - Appends a new timestamped log record at the close of every 1-hour interval:
     `timestamp_utc, instrument, strategy, state, latest_close, sma50, sma200, position_units, cash_balance, current_equity, net_pnl`
3. **Execution Simulator:**
   - Evaluates signals at the close of hour $t$.
   - Fills market buy orders at hour $t+1$ Open at **ASK** ($\text{Open} + \frac{1}{2}\text{Spread} + \text{Slippage}$).
   - Fills market close orders at hour $t+1$ Open at **BID** ($\text{Open} - \frac{1}{2}\text{Spread} - \text{Slippage}$).
   - Accrues overnight financing swap at 22:00 UTC daily, with triple-swap accounting on Wednesday nights.
4. **Read-Only Dashboard (`phase12/dashboard/app.py`):**
   - Renders a clean web-based research monitor displaying real-time metrics, position state, and tier comparisons.

---

## 3. Operational Invariant Verification

* **PAPER_TRADING_ONLY:** Hardcoded to `True`.
* **LIVE_ORDERS:** Hardcoded to `0`.
* **WALLET_CONNECTIONS:** `0`.
* **PRIVATE_KEYS:** `0`.
* **LEVERAGE:** Fixed at `1.0x`.
* **TARGET DURATION:** Minimum 30 calendar days (recommended 60–90 days).

---

## 4. Current State Snapshot (At Launch)

* **Current Position:** `LONG (IN POSITION)` (Fast SMA: $4,228.45 > Slow SMA: $4,124.60).
* **Current Spot Price:** $4,340.10.
* **Paper Equity Balance:** $16,562.83 (Tier B compounded base).
* **Live Orders Submitted:** 0.
