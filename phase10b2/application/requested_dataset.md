# ACADEMIC / RESEARCH APPLICATION: REQUESTED DATASET SPECIFICATION

**Document Identifier**: `phase10b2/application/requested_dataset.md`  
**Provider**: Tardis.dev  
**Dataset Category**: Historical Cryptocurrency Spot Market Data  
**Application Status**: PREPARED FOR USER REVIEW (Pending Explicit User Authorization)  

---

## 1. TARGET VENUE & INSTRUMENTS

* **Target Venue**: Binance.US Spot (`binance-us`)
* **Target Spot Instruments**:
  - `BTCUSDT` (Bitcoin / Tether Spot)
  - `ETHUSDT` (Ethereum / Tether Spot)
  - `SOLUSDT` (Solana / Tether Spot)
* **Venue Rationale**:
  - Binance.US provides high liquidity under transparent US regulatory standards.
  - Matches the multi-asset research baseline evaluated across Phases 9B–9E.

---

## 2. MINIMUM REQUIRED EVENT DATA STREAMS

In accordance with the minimum-data principle, the study requests only two synchronized event streams per asset:

### 2.1 Incremental Level-2 Order Book Updates (`incremental_book_L2`)
* **Format**: Gzip compressed CSV (`exchange,symbol,timestamp,local_timestamp,is_snapshot,side,price,amount`).
* **Required Technical Attributes**:
  - Microsecond exchange matching engine timestamps (`timestamp`).
  - Microsecond local packet arrival timestamps (`local_timestamp`) for atomic message batching.
  - Periodic / initial book depth snapshots (`is_snapshot=true`, top 1000 levels from `@depthSnapshot`) to seed and reset book state.
  - Incremental order-book deltas with price-level deletion semantics (`amount=0.0`).
* **Queue Model Constraint**:
  - Market-By-Price (MBP) data supports **estimated queue-ahead ($Q_{\text{ahead}}$)** modeling only. No Level-3 / MBO order-level priority is assumed.

### 2.2 Tick-by-Tick Executed Trades (`trades`)
* **Format**: Gzip compressed CSV (`exchange,symbol,timestamp,local_timestamp,id,side,price,amount`).
* **Required Technical Attributes**:
  - Unique exchange trade identifiers (`id`).
  - Explicit aggressor side classification (`side`: `buy` / `sell`).
  - Microsecond execution timestamps.

---

## 3. HISTORICAL COVERAGE REQUIREMENT

* **Preregistered Duration**: **30 consecutive calendar days** per asset.
* **Coverage Rationale**:
  - The Phase 10A research protocol strictly requires 30 continuous calendar days to capture multiple market regimes (trending, mean-reverting, high-volatility) without regime truncation bias.
  - Standard 7–14 day evaluation trials are recognized as insufficient to satisfy this preregistered requirement.
* **Suggested Historical Window**:
  - `2024-03-01T00:00:00.000000Z` through `2024-03-31T23:59:59.999999Z`

---

## 4. ESTIMATED DATA VOLUME

* **Daily Trades**: $\approx 250,000\text{ to }750,000$ trades/day ($\approx 25\text{ MB}$ compressed/day/symbol).
* **Daily L2 Deltas**: $\approx 5,000,000\text{ to }12,000,000$ updates/day ($\approx 250\text{ MB}$ compressed/day/symbol).
* **30-Day Total**: $\approx 25\text{ to }35\text{ GB}$ compressed across all 3 instruments.
