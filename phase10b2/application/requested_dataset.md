# ACADEMIC / RESEARCH APPLICATION: REQUESTED DATASET SPECIFICATION

**Document Identifier**: `phase10b2/application/requested_dataset.md`  
**Provider**: Tardis.dev  
**Dataset Category**: Historical Cryptocurrency Spot Market Data  
**Application Status**: Prepared for User Review  

---

## 1. TARGET VENUE & INSTRUMENTS

* **Primary Venue**: Binance.US Spot (or Coinbase Exchange Spot)
* **Target Spot Instruments**:
  - `BTCUSDT` (Bitcoin / Tether Spot)
  - `ETHUSDT` (Ethereum / Tether Spot)
  - `SOLUSDT` (Solana / Tether Spot)
* **Venue Rationale**:
  - Binance.US provides high liquidity under standard US regulatory reporting and transparent public WebSocket feeds.
  - Matches the empirical baseline established during Phase 9 multi-asset research.

---

## 2. REQUESTED EVENT DATA TYPES

The research design requires two synchronized event streams per asset:

### 2.1 Incremental Level-2 Order Book Updates (`incremental_book_L2`)
* **Format**: Gzip compressed CSV (`exchange,symbol,timestamp,local_timestamp,is_snapshot,side,price,amount`).
* **Required Features**:
  - Microsecond-precision exchange matching engine timestamps.
  - Local arrival timestamps for message atomic batching.
  - Initial / periodic order-book depth snapshots flagged via `is_snapshot=true`.
  - Incremental order-book deltas with price-level deletion semantics (`amount=0.0`).

### 2.2 Tick-by-Tick Executed Trades (`trades`)
* **Format**: Gzip compressed CSV (`exchange,symbol,timestamp,local_timestamp,id,side,price,amount`).
* **Required Features**:
  - Unique exchange trade identifiers (`id`).
  - Taker aggressor classification (`side`: `buy` / `sell`).
  - Microsecond execution timestamps.

---

## 3. HISTORICAL COVERAGE REQUIREMENT

* **Minimum Continuous Period**: **30 consecutive calendar days** per asset.
* **Suggested Historical Window**:
  - `2024-03-01` through `2024-03-31` (Representative high-volatility & range-bound spot regime), OR
  - `2023-01-01` through `2023-01-31`
* **Alternative Research Trial Window**:
  - If a 30-day window cannot be granted under the free evaluation tier, a **14-day continuous evaluation window** (e.g., 2024-03-01 to 2024-03-14) is requested for exploratory qualification and initial model verification.

---

## 4. ESTIMATED DATA VOLUME

* **Daily Trades**: $\approx 250,000\text{ to }750,000$ trades/day ($\approx 25\text{ MB}$ compressed/day/symbol).
* **Daily L2 Deltas**: $\approx 5,000,000\text{ to }12,000,000$ updates/day ($\approx 250\text{ MB}$ compressed/day/symbol).
* **30-Day Total**: $\approx 25\text{ to }35\text{ GB}$ compressed across all 3 instruments.
