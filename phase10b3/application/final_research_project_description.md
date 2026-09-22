# PHASE 10B.3: FINAL RESEARCH PROJECT DESCRIPTION

**Project Title**: Passive Execution Economics, Queue Dynamics & Adverse Selection in Cryptocurrency Spot Markets  
**Research Initiative**: Program 10A / 10B Quantitative Market Microstructure Study  
**Platform**: Jev Crypto-Trading Research System  
**Principal Investigator**: [USER INPUT REQUIRED: Principal Investigator Name, Academic Title]  
**Academic Institution**: [USER INPUT REQUIRED: University / Department / Research Laboratory]  
**Institutional Email**: [USER INPUT REQUIRED: user@university.edu or institutional domain]  
**Date**: `2026-09-22`  
**Application Status**: READY FOR USER REVIEW (External Submission Pending Explicit User Authorization)  

---

## 1. RESEARCH ABSTRACT & SCIENTIFIC OBJECTIVE

This project is a **strictly non-commercial, non-live quantitative market microstructure study** investigating passive (maker) execution economics, queue depletion, fill probability, adverse selection markouts, and transaction-cost-adjusted expectancy in cryptocurrency spot markets.

In prior phases of this research program (Phases 1–9), extensive empirical backtesting and statistical audits established that sub-daily directional forecasting models on liquid spot crypto pairs fail to overcome standard taker execution friction (38–44 bps dynamic round-trip hurdle crossing the spread).

Program 10A tests the falsifiable empirical hypothesis:
> *Can passive limit-order execution structurally alter execution economics by capturing the bid-ask half-spread and paying maker fees/rebates rather than crossing the spread, creating positive net expectancy once queue position, partial fills, cancellation latency, adverse selection, inventory drag, and liquidation costs are realistically modeled?*

**Critical Scientific Boundary**:
The research does **NOT** assume, guarantee, or claim expected profitability or alpha. It is an empirical inquiry into market microstructure frictions, with preregistered falsification gates designed to conclusively reject passive execution if net economic expectancy remains negative.

---

## 2. METHODOLOGY & QUEUE MODEL SPECIFICATION

The empirical investigation requires discrete-event replay of historical order-book and trade flow:

1. **Queue Model Classification — L2 Queue-Ahead Estimation**:
   - Spot crypto exchange feeds (including Binance.US) provide **Market-By-Price (Level 2 / MBP)** data rather than individual order identifiers (Level 3 / MBO).
   - Therefore, the research strictly utilizes **queue-ahead estimation ($Q_{\text{ahead}}$)** under aggregated Level-2 market-by-price data, NOT exact order-level FIFO priority.
   - Upon quote insertion at target price $P$, $Q_{\text{ahead}}$ equals total resting depth at $P$.
   - Aggressive trades matching at $P$ deplete $Q_{\text{ahead}}$.
   - Order fills are modeled only after cumulative aggressive volume fully depletes $Q_{\text{ahead}}$.
     - Order cancellations occurring ahead in queue are conservatively modeled under worst-case bounds (assuming cancellations occur behind our queue position), preventing manufactured or optimistic fills.
2. **Sub-Second Adverse Selection Markouts**:
   - Quantifying price drift following simulated fills:
     $$\text{Markout}(\tau) = \text{Mid}(t + \tau) - P_{\text{fill}}$$
   - Markout horizons: $\tau \in [100\text{ ms}, 500\text{ ms}, 1\text{ s}, 5\text{ s}, 30\text{ s}, 5\text{ min}]$.
3. **Inventory Drag & Emergency Unwinding**:
   - Tracking inventory variance drag and modeling aggressive market order costs required to liquidate boundary-violating inventory.
4. **Statistical Testing**:
   - 7 preregistered hypotheses (`P10A-H01` to `P10A-H07`) evaluated with block bootstrap testing and multiple-testing corrections (Benjamini-Hochberg FDR).

---

## 3. ABSOLUTE SAFETY INVARIANTS

The research system operates under immutable, automated runtime invariants:
```python
PAPER_TRADING_ONLY = True
USE_LIVE_JEV = False
LEVERAGE = 1.0
LIVE_ORDERS = 0
WALLET_CONNECTIONS = 0
PRIVATE_KEYS = 0
```

* **No Live Trading Gateway**: The research platform contains zero connectivity to live exchange execution accounts.
* **No Fund Management**: The project does not manage proprietary capital or external assets.
* **Non-Commercial Publication**: Findings will be published purely as academic methodology, aggregated statistics, and research documentation.
