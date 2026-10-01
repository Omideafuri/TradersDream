# PHASE 13: PROSPECTIVE FORWARD PAPER VALIDATION — LAUNCH REPORT

**Launch Timestamp:** 2026-10-01T00:50:41Z  
**Project:** Autonomous Quantitative Research & Prospective Microstructure Validation  
**Instrument:** XAU/USD (Spot Physical Gold vs US Dollar)  
**Strategy ID:** `XAUUSD_FROZEN_SMA50_200_1H`  
**Execution Environment:** `PAPER_TRADING_ONLY = TRUE`  
**Launch Status:** `LAUNCHED — PAPER ONLY`  
**Auditor Classification:** FORENSIC QUANTITATIVE SYSTEMS AUDITOR  

---

## A. Executive Summary

Phase 13 establishes a strict, prospective, forward paper-trading validation system for the frozen systematic strategy `XAUUSD_FROZEN_SMA50_200_1H`. This phase was launched after the complete forensic completion and auditing of Phase 11 (Strategy Discovery) and Phase 12 (Adversarial Microstructure & Execution Audit).

The primary objective of Phase 13 is to observe and evaluate the strategy's behavior in real time against **genuinely new market data** arriving after the historical research window (2021-01-01 through 2025-12-31 UTC). The system operates strictly in paper-trading mode, with hardcoded assertions preventing any real capital exposure, wallet interaction, or live order placement.

All Phase 11 and Phase 12 artifacts, models, backtest ledgers, and raw data are physically segregated and cryptographically sealed. The forward capture pipeline ingests live physical spot XAU/USD price quotes via an unauthenticated REST feed (`https://api.gold-api.com/price/XAU`), maintains an immutable 32-column append-only paper ledger, persists state in atomic JSON, and enforces runtime anti-lookahead assertions.

---

## B. Frozen Strategy Specification

The strategy specification is completely frozen. No parameter search, threshold tuning, indicator modification, or execution adjustment is permitted during Phase 13.

* **Strategy Identifier:** `XAUUSD_FROZEN_SMA50_200_1H`
* **Underlying Instrument:** Spot Gold quoted in US Dollars (`XAU/USD`). Strictly no substitutions (no COMEX GC/MGC futures, no GLD/IAU ETFs, no crypto-collateralized tokens such as PAXG or XAUT, and no meme tokens).
* **Bar Construction:** 1-Hour candles constructed from completed top-of-the-hour quote buckets, aligned to UTC.
* **Trend Indicators:**
  * **Fast SMA:** 50-period Simple Moving Average computed strictly on completed 1-hour bar closes:
    $$\text{SMA}_{50, t} = \frac{1}{50} \sum_{i=0}^{49} \text{Close}_{t-i}$$
  * **Slow SMA:** 200-period Simple Moving Average computed strictly on completed 1-hour bar closes:
    $$\text{SMA}_{200, t} = \frac{1}{200} \sum_{i=0}^{199} \text{Close}_{t-i}$$
  * **Diagnostic Indicator:** ATR 14 is logged for volatility diagnostics only; it has zero influence on signal generation or position sizing.
* **Causal Signal Logic:**
  * **Long Entry Signal:** Evaluated at the exact close of completed bar $t$:
    $$\text{If } \text{State}_t = \text{FLAT} \quad \text{AND} \quad \text{SMA}_{50, t} > \text{SMA}_{200, t} \implies \text{Queue BUY at Open}_{t+1}$$
  * **Exit Signal:** Evaluated at the exact close of completed bar $t$:
    $$\text{If } \text{State}_t = \text{LONG} \quad \text{AND} \quad \text{SMA}_{50, t} \le \text{SMA}_{200, t} \implies \text{Queue SELL at Open}_{t+1}$$
* **Directional Constraint:** Long-only. Strictly no short positions, no hedging, no pyramiding, no overlapping positions, and no partial exits.
* **Position Sizing & Leverage:**
  * Exactly 1.0x leverage (zero margin borrowing).
  * 100% sequential compounding equity allocation:
    $$\text{Units}_{t+1} = \frac{\text{Cash}_t}{\text{FillPrice}_{t+1}}$$
* **Execution Timing & Microstructure:**
  * Fills occur at the first available trade/quote of bar $t+1$ (`Open_{t+1}`).
  * Signal timestamp must be strictly earlier than execution timestamp: $t_{\text{signal}} < t_{\text{exec}}$.
  * Entry orders fill at the Ask price; exit orders fill at the Bid price. Midpoint execution is prohibited.

---

## C. Safety Verification

An automated static and dynamic audit of the entire codebase was conducted to verify that live trading is technically impossible.

### 1. Invariant Assertions
The following invariants are hardcoded at the class and module levels in `ForwardRunner`, `StateManager`, `ExecutionSimulator`, and `IntegrityMonitor`:

```python
PAPER_TRADING_ONLY = True
LIVE_ORDERS = 0
WALLET_CONNECTIONS = 0
PRIVATE_KEYS = 0
LEVERAGE = 1.0
```

### 2. Code-Level Endpoint & Key Scan Results
* **Order Placement Calls:** Zero (`0`). No calls to `create_order`, `submit_order`, `place_order`, `send_order`, or exchange execution SDKs exist in the repository.
* **Private API Keys:** Zero (`0`). Code searches for `API_SECRET`, `PRIVATE_KEY`, `SEED_PHRASE`, and private exchange auth returned zero unredacted production secrets.
* **Broker Trading Gateways:** Zero (`0`). No FIX protocol engines, Interactive Brokers TWS/Gateway APIs, MetaTrader bridges, or ccxt authenticated trading wrappers are instantiated.
* **Cryptocurrency / Web3 Wallets:** Zero (`0`). No web3.py, eth-account, bip39, or crypto wallet transaction modules exist in the codebase.
* **Network Connectivity:** The forward monitor connects exclusively to public, unauthenticated HTTP GET endpoints for quote reads.

---

## D. Strategy Hashes

To guarantee immutability across the prospective forward observation period, SHA-256 cryptographic checksums were generated for all strategy specification and execution files. These are stored in `phase13/PHASE13_STRATEGY_HASH.json` and verified prior to every polling cycle:

| File Path | SHA-256 Digest | Status |
| :--- | :--- | :---: |
| `PHASE12_STRATEGY_LOCK.json` | `72ec09151c7c25bded64abcc5b853cc0f2169c19b3619a920d03e2ae0840df4e` | Verified Match |
| `phase13/config/phase13_forward_config.json` | `47e5ec73e142e71ce7f7035d794a7a3cb1f52c3ad6cd6dee421f3c2c03c086ac` | Verified Match |
| `phase13/engine/execution_simulator.py` | `9271cf78aeb692663546bf36a91ed607e734eb54d1e948db85290eaad9f7cc66` | Verified Match |
| `phase13/engine/state_manager.py` | `121d064183a07ecab961f2c7753cc70233c9ac4df7352b910e5121024d5e9d29` | Verified Match |
| `phase13/engine/integrity_monitor.py` | `9f6bb4b875b956859189be37c238793474110a9aa101e5464d027344b223305b` | Verified Match |
| `phase13/engine/forward_monitor.py` | `0d9bafe28b8d43436989eaca1db7ab052c9c6e6d00222ba67adf6babcf328a30` | Verified Match |

Any mutation of these files causes `IntegrityMonitor` to abort the experiment immediately with status `INTEGRITY_BREACH`.

---

## E. Data Source & Microstructure Modeling

### 1. Ingestion Feed
* **Primary Source:** Public Spot Gold REST Feed: `https://api.gold-api.com/price/XAU`
* **Instrument:** Spot Physical Gold (XAU) priced in US Dollars (USD).
* **Format:** Real-time spot pricing with millisecond server timestamps.
* **Raw Archival:** Every response is persisted as timestamped JSON in `phase13/data/raw_forward_quotes/`.

### 2. Forensic Feed Qualification & Rejections
* **Yahoo Finance (`XAU-USD`):** Forensically tested and rejected. Ticker represents a Binance Smart Chain meme token (`XAU9999 Meme USD`, price $\sim \$10^{-11}$), NOT physical gold.
* **COMEX Gold Futures (`GC`, `MGC`):** Rejected. Futures introduce contract expirations, roll calendar yield, backwardation/contango distortion, and margin/leverage dynamics that do not represent spot XAU/USD.
* **Gold ETFs (`GLD`, `IAU`):** Rejected. Equity ETFs trade only during US market hours (09:30–16:00 EST), omitting European/Asian price discovery and introducing tracking errors and expense ratios.

### 3. Observed vs. Modeled Data Accounting
In strict compliance with Section 6 of the research specification, the paper engine distinguishes between observed market data and modeled execution parameters:
* **Bid Quote:** `OBSERVED` directly from the feed.
* **Ask Quote:** Because the raw feed supplies spot reference price without a simultaneous broker ask book, the system explicitly logs `ASK_DATA_AVAILABLE = FALSE`.
* **Execution Spread:** Modeled conservatively at **4.0 basis points round-trip** (2.0 bps half-spread).
* **Execution Slippage:** Modeled at **2.0 basis points adverse slippage** per side.
* **Broker Commission:** Modeled at **$0.05 per troy ounce**.
* **Overnight Financing (Swap):** Modeled at **3.5% per annum** charged daily at 22:00 UTC, with a **3x triple rollover on Wednesday night** to cover the weekend.

---

## F. Initial Strategy State at Launch

* **Launch Timestamp (UTC):** `2026-10-01T00:50:41.504639+00:00`
* **Initial Spot XAU/USD Price:** `$4,146.00 / oz`
* **Warmup Seeding Data:** Last 250 completed hourly bars from the Phase 11 2021–2025 dataset (ending 2025-12-31 21:00:00 UTC).
* **Warmup Final Close:** `$4,318.38`
* **Warmup Fast Indicator ($\text{SMA}_{50}$):** `$4,345.14`
* **Warmup Slow Indicator ($\text{SMA}_{200}$):** `$4,409.73`
* **Initial State Classification:** `FLAT` ($\text{SMA}_{50} \le \text{SMA}_{200}$, trend is bearish / uncrossed).
* **Paper Cash Balance:** `$10,000.00`
* **Paper Total Equity:** `$10,000.00`
* **Pending Orders:** `None`
* **Forward Bars Completed:** `0`
* **Forward Trades Executed:** `0`

---

## G. Historical Baseline Reference

For context and comparison, the historical performance of `XAUUSD_FROZEN_SMA50_200_1H` established during Phase 11 and verified during the Phase 12 adversarial audit is summarized below. **These historical statistics are strictly quarantined and will never be blended or commingled into the Phase 13 forward paper ledger:**

| Metric | Phase 11 Discovery (2021–2024) | Phase 12 Holdout (2025) | Phase 12 Combined (2021–2025) |
| :--- | :---: | :---: | :---: |
| **Observation Window** | 4.0 Years | 1.0 Year | 5.0 Years |
| **Total Completed Bars** | 22,940 | 5,856 | 28,796 |
| **Net Strategy Return** | +63.88% | +28.94% | +111.31% |
| **Buy & Hold Return** | +38.64% | +64.21% | +127.67% |
| **Total Closed Trades** | 102 | 24 | 126 |
| **Win Rate** | 35.29% | 41.67% | 36.51% |
| **Profit Factor** | 1.48 | 1.83 | 1.54 |
| **Annualized Sharpe Ratio**| 0.81 | 1.14 | 0.88 |
| **Maximum Drawdown** | -16.42% | -7.31% | -16.42% |

---

## H. Known Limitations & Research Qualifications

In accordance with Section 27.H, the qualifications and limitations identified in Phase 12 are explicitly retained:

1. **Absence of Simultaneous Raw Broker Ask Quotes:** The forward feed supplies spot market price. While spot market price accurately captures the macroeconomic valuation of physical gold, retail broker execution spreads vary between 2.5 bps and 6.0 bps depending on liquidity session. Modeled spread is fixed at 4.0 bps.
2. **Absence of Level-2 Order Book Depth:** Spot gold is traded OTC via the London Bullion Market Association (LBMA) and interbank liquidity networks. Centralized order books do not exist for spot gold, making passive queue priority unobservable.
3. **Right-Skewed Return Distribution:** Historical profitability relies heavily on large trend runs (top 3 trades represent $>40\%$ of historical gains). The forward test must observe whether such trending regimes persist or whether whipsaw conditions dominate.
4. **Multiple Testing Adjustments:** Phase 12 established that multiple testing across technical parameter spaces reduces statistical significance under conservative Bonferroni/FWER adjustments.

---

## I. Formal Launch Status

All pre-launch checks, immutability audits, unit tests, and runtime safety constraints have passed with zero exceptions.

$$\mathbf{LAUNCH\ STATUS:\ LAUNCHED\ —\ PAPER\ ONLY}$$

*The measurement clock has started. Data ingestion is active and recording to `phase13/data/forward_paper_ledger.csv`.*
