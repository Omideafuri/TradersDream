# PHASE 10B.3: FINAL REQUESTED DATASET SPECIFICATION

**Document Identifier**: `phase10b3/application/final_requested_dataset.md`  
**Provider**: Tardis.dev  
**Dataset Class**: Historical Cryptocurrency Spot Market Data  
**Application Status**: READY FOR USER REVIEW (External Submission Pending Explicit User Authorization)  

---

## 1. TARGET VENUE & SPOT INSTRUMENTS

* **Target Venue**: Binance.US (`binance-us`)
* **Target Spot Instruments**:
  - `BTCUSDT` (Bitcoin / Tether Spot)
  - `ETHUSDT` (Ethereum / Tether Spot)
  - `SOLUSDT` (Solana / Tether Spot)
* **Venue Justification**:
  - High-liquidity US-regulated spot trading venue with transparent public WebSocket broadcast feeds.
  - Aligns with the empirical baseline established in Phase 9 multi-asset research.

---

## 2. MINIMUM REQUIRED EVENT DATA STREAMS

Adhering to the **minimum-data principle**, only two synchronized event streams per asset are requested:

### 2.1 Incremental Level-2 Order Book Updates (`incremental_book_L2`)
* **CSV Format**: `exchange,symbol,timestamp,local_timestamp,is_snapshot,side,price,amount` (gzipped CSV).
* **Technical Elements**:
  - `timestamp`: Matching engine event timestamp in microseconds since epoch.
  - `local_timestamp`: Message arrival timestamp at Tardis capture interface (London GCP) in microseconds since epoch; used for atomic WebSocket message batching.
  - `is_snapshot`: Full book snapshots (top 1000 levels from `@depthSnapshot`) tagged with `is_snapshot=true` for book seeding and recovery.
  - `amount`: Absolute depth at price level; `amount=0.0` represents price-level deletion.
* **Granularity Restriction**:
  - Market-By-Price (MBP) data. Evaluated strictly via **queue-ahead estimation ($Q_{\text{ahead}}$)**; no individual order IDs are present.

### 2.2 Tick-by-Tick Executed Trades (`trades`)
* **CSV Format**: `exchange,symbol,timestamp,local_timestamp,id,side,price,amount` (gzipped CSV).
* **Technical Elements**:
  - `id`: Exchange execution identifier for deduplication.
  - `side`: Taker aggressor classification (`buy` / `sell`).
  - `price` & `amount`: Executed trade price and volume.
  - `timestamp`: Microsecond execution timestamp.

---

## 3. HISTORICAL COVERAGE REQUIREMENT

* **Required Continuous Period**: **30 consecutive calendar days** per instrument.
* **Protocol Rationale**:
  - Phase 10A protocol explicitly mandates 30 continuous calendar days to span trending, consolidating, and high-volatility regimes.
  - A 7–14 day evaluation window is insufficient for the full preregistered protocol.
* **Suggested Historical Target**:
  - `2024-03-01T00:00:00.000000Z` through `2024-03-31T23:59:59.999999Z`

---

## 4. ESTIMATED DATA VOLUME

* **Daily Event Volume**: $\approx 250\text{k} - 750\text{k}$ trades/day; $\approx 5\text{M} - 12\text{M}$ book updates/day per instrument.
* **Total 30-Day Storage Requirement**: $\approx 25 - 35\text{ GB}$ compressed CSV.
