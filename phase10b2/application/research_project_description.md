# ACADEMIC / RESEARCH APPLICATION: PROJECT DESCRIPTION

**Project Title**: Passive Execution Economics, Queue Dynamics & Adverse Selection in Cryptocurrency Spot Markets  
**Research Initiative**: Program 10A / 10B Quantitative Market Microstructure Study  
**Platform**: Jev Crypto-Trading Research System  
**Principal Investigator**: [USER INPUT REQUIRED: Principal Investigator Name, Academic Title]  
**Academic Institution / Department**: [USER INPUT REQUIRED: University / Department / Research Laboratory]  
**Institutional Email**: [USER INPUT REQUIRED: user@university.edu or institutional domain]  
**Date**: `2026-09-22`  
**Application Status**: PREPARED FOR USER REVIEW (External Submission Pending Explicit User Authorization)  

---

## 1. RESEARCH ABSTRACT & SCIENTIFIC PURPOSE

This initiative is a **strictly non-commercial, non-live quantitative research study** investigating passive execution economics, queue-aware fill modeling, adverse selection markouts, and transaction-cost-adjusted expectancy in historical cryptocurrency spot markets.

In prior phases (Phases 1–9), our research established that sub-daily directional forecasting models on liquid crypto pairs fail to clear standard taker execution friction (38–44 bps dynamic hurdle crossing the spread). Program 10A investigates whether **passive (maker) liquidity provision** can structurally alter this cost dynamic by capturing the bid-ask half-spread and paying lower maker fees, rather than crossing the spread.

The central research hypothesis is strictly falsifiable:
> *A passive execution strategy may capture some portion of the bid-ask spread and/or maker fee economics, potentially changing the cost structure enough to create positive net expectancy, provided that fill probability, queue position, adverse selection, inventory risk, latency, cancellations, and liquidation costs are modeled realistically.*

This research makes no claim of guaranteed alpha, expected profitability, or commercial deployment. It is an empirical inquiry into market microstructure barriers.

---

## 2. SCIENTIFIC METHODOLOGY & RESEARCH DESIGN

The research strictly operates on historical event-level tick data using:
1. **L2 Queue-Ahead Estimation**: Because Binance.US spot order-book data is Market-By-Price (Level 2) and does not provide individual order IDs, queue position is modeled via **estimated queue depth ahead ($Q_{\text{ahead}}$)**, NOT exact order-level FIFO priority. Fills occur only when cumulative aggressive volume depletes visible depth ahead.
2. **Sub-Second Adverse Selection Markouts**: Measuring post-fill price drift ($\text{Mid}(t + \tau) - P_{\text{fill}}$) across horizons $\tau \in [100\text{ ms}, 500\text{ ms}, 1\text{ s}, 5\text{ s}, 30\text{ s}, 5\text{ min}]$.
3. **Inventory & Liquidation Drag**: Quantifying the variance drag of accumulating inventory and the cost of emergency aggressive unwinding.
4. **Preregistered Falsification Gates**: Evaluating 7 formal hypotheses (`P10A-H01` to `P10A-H07`) against block bootstrap statistical tests with multiple-testing correction.

---

## 3. ABSOLUTE RESEARCH INVARIANTS & NON-COMMERCIAL STATEMENT

The research platform operates under strict, auditable safety constraints:
```python
PAPER_TRADING_ONLY = True
USE_LIVE_JEV = False
LEVERAGE = 1.0
LIVE_ORDERS = 0
WALLET_CONNECTIONS = 0
PRIVATE_KEYS = 0
```

* **No Live Trading Execution**: The requested data will never be connected to automated live trading accounts, execution gateways, or proprietary capital deployment.
* **No Commercial Fund Management**: The project does not manage external client assets, run hedge fund operations, or provide commercial signal feeds.
* **Purely Academic & Methodological**: Findings will be synthesized into open reproducible scientific reports documenting market microstructure barriers.
