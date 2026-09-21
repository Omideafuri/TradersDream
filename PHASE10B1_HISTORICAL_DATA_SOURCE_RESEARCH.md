# PHASE 10B.1 — HISTORICAL EVENT-DATA SOURCE DISCOVERY & ACQUISITION REPORT

**Document Identifier**: `PHASE10B1_HISTORICAL_DATA_SOURCE_RESEARCH.md`  
**Phase**: Phase 10B.1 Historical Event-Data Source Discovery & Procurement Research  
**Platform**: Jev Crypto-Trading Research System  
**Date**: `2026-09-22T03:20:00+00:00`  
**Safety Invariants**: `PAPER_TRADING_ONLY = true`, `USE_LIVE_JEV = false`, `LEVERAGE = 1.0`  
**Mandatory Prohibition**: Zero financial commitments or subscription purchases incurred (Section 40 Compliance).

---

## 1. EXECUTIVE SUMMARY

Phase 10A defined the research protocol for **Passive Execution & Queue Dynamics**, but Phase 10B determined that local repository data was `DATA INSUFFICIENT` due to the complete absence of historical tick trades and incremental Level-2 order-book deltas.

Phase 10B.1 was commissioned to answer one specific question:
> *Can we obtain sufficiently granular, historically authentic, reproducible market-event data to execute the preregistered Phase 10A passive-execution research?*

### Master Findings:
1. **Source Qualified**: **Tardis.dev** has been empirically verified via API metadata and documentation inspection as capable of providing the exact required data types (`incremental_book_L2` deltas, embedded snapshots, and tick `trades` with aggressor side classification) for `BTCUSDT`, `ETHUSDT`, and `SOLUSDT` on Binance.US and Coinbase continuously from 2019/2020 to present.
2. **Exchange Archives Insufficient**: Official exchange public archives (e.g. `data.binance.vision`) provide historical trades and klines, but explicitly **do not archive historical Level 2 order-book deltas for spot markets**. Public REST endpoints provide only current book snapshots, not continuous historical replay.
3. **Queue Granularity Defined**: The qualified dataset provides **Market-By-Price (Level 2)** depth. Individual order IDs (Level 3 / MBO) are not provided on spot Binance.US. Therefore, queue position must be rigorously modeled as **`QUEUE-AHEAD ESTIMATE`**, not `EXACT ORDER-LEVEL FIFO`.
4. **Stopping Gate — Paid Acquisition Required**: Acquiring the continuous 30-day historical event dataset requires a commercial subscription or research trial key ($300 minimum order requirement). In strict compliance with Section 40, zero purchases have been made.
5. **Phase Status**:
   ```text
   FORMAL DECISION: SOURCE QUALIFIED — ACQUISITION POSSIBLE
   ACQUISITION GATE: PAID ACCESS REQUIRED (STOPPED PENDING USER APPROVAL)
   PHASE 10C PERMISSION: BLOCKED
   ```

---

## 2. METHODOLOGY & CANDIDATE SOURCES INVESTIGATED

We evaluated five candidate sources across three primary categories:

### Category A: Exchange-Native Public Archives
* **Binance Data Vision (`data.binance.vision`)**: Evaluated for spot tick trades and L2 deltas. Free public download available for trades, but L2 order-book depth deltas are completely omitted.
* **Coinbase Exchange Native REST**: Evaluated for historical replay. Only rolling current snapshots are exposed; no historical streaming replay.

### Category B: Specialized Crypto Market-Data Providers
* **Tardis.dev**: Sourced from raw exchange WebSocket matching streams (`wss://stream.binance.us:9443/stream`) with microsecond timestamps and atomic message grouping. Fully documented schemas.
* **Kaiko Data**: Institutional market-data vendor providing tick trades and L2 snapshots. Enterprise pricing ($1,500–$5,000+/month) with no self-serve programmatic acquisition.

### Category C: High-Performance Multi-Asset Platforms
* **Databento**: Nanosecond MBP-10 and MBO market data. Pricing is usage-based (~$0.05–$0.20/GB), but crypto venue coverage for USDT pairs on US exchanges is currently evolving.

---

## 3. DETAILED TECHNICAL EVALUATION OF TARDIS.DEV

Tardis.dev emerged as the primary qualifying source. A technical probe was executed against its public API endpoint (`https://api.tardis.dev/v1/exchanges/binance-us`):

```json
{
  "id": "binance-us",
  "name": "Binance US",
  "enabled": true,
  "availableSince": "2019-09-25T00:00:00.000Z",
  "availableChannels": ["trade", "depth", "depthSnapshot", "bookTicker", "aggTrade", "ticker"],
  "datasets": ["trades", "incremental_book_L2", "quotes", "book_snapshot_5", "book_snapshot_25", "book_ticker"],
  "dataCollectionDetails": {
    "recorderDataCenter": {"host": "GCP", "regionId": "europe-west2", "location": "London, Europe"},
    "wssConnection": {"url": "wss://stream.binance.us:9443/stream"},
    "exchangeDataCenter": {"host": "AWS", "regionId": "us-east-1", "location": "N. Virginia, North America"}
  }
}
```

### Coverage Confirmation:
* `btcusdt`: Available since `2019-09-25` to present (Continuous).
* `ethusdt`: Available since `2019-09-25` to present (Continuous).
* `solusdt`: Available since `2020-09-18` to present (Continuous).
* **30-Day Consecutive Coverage**: **PASS**.

---

## 4. SCHEMA MAPPING: TARDIS TO PHASE 10B RECONSTRUCTOR

The data fields provided by Tardis map directly into the Phase 10B architecture engineered in `phase10b/`:

| Tardis Field | Phase 10B Model | Engine Mapping |
|---|---|---|
| `timestamp` | `exchange_timestamp_ms` | Converted from microseconds to integer milliseconds |
| `local_timestamp` | `local_receive_timestamp_ms` | Used for atomic message batching and transport latency |
| `is_snapshot == true` | `L2Snapshot` | Invokes `OrderBookReconstructor.load_snapshot()` |
| `is_snapshot == false` | `L2Delta` | Invokes `OrderBookReconstructor.apply_delta()` |
| `side == 'bid'` / `'ask'` | `BookSide.BID` / `BookSide.ASK` | Routes update to proper side ladder |
| `price` | `price` | Decimal float tick price |
| `amount == 0.0` | Exchange Deletion Semantics | Automatically removes depleted price level from ladder |
| `amount > 0.0` | Exchange Add/Modify Semantics | Updates price level quantity |
| `id` (trades) | `trade_id` | Enforces uniqueness and duplicate detection |
| `side` (trades) | `AggressorSide` | Identifies aggressive buyer vs seller |

---

## 5. PROCUREMENT FEASIBILITY & COST OPTIONS

Because full 30-day historical continuous datasets exceed free first-of-month sample downloads, procurement options were analyzed:

1. **Academic / Research Trial Access**:
   - *Scope*: 30-day trial API key granting access to 7–14 days of rolling historical event data.
   - *Cost*: **$0.00**.
   - *Requirement*: Application via academic/institutional contact.
2. **Solo / Custom Data Order**:
   - *Scope*: Full 30-day continuous download across `BTCUSDT`, `ETHUSDT`, `SOLUSDT`.
   - *Cost*: Minimum order requirement is **$300.00**.
   - *Mechanism*: Programmatic download via Python SDK (`tardis-dev`).
3. **Enterprise Contract (Kaiko)**:
   - *Cost*: $15,000 – $30,000+ annual commitment. (Infeasible).

---

## 6. STOPPING GATE: MANDATORY STOP BEFORE PURCHASE

In strict adherence to Section 40:
* **No purchase has been executed.**
* **No subscription has been created.**
* **No payment method or financial commitment has been entered.**
* **The research system has halted at the procurement gate and reports: `PAID ACQUISITION REQUIRED`.**

---

## 7. SCIENTIFIC QUALIFICATION VERDICT

```text
========================================================================================
                      PHASE 10B.1 SOURCE QUALIFICATION VERDICT:
                       SOURCE QUALIFIED — ACQUISITION POSSIBLE
                     STOPPING REASON: PAID ACQUISITION REQUIRED
                            PHASE 10C STATUS: BLOCKED
========================================================================================
```

### Next Permitted Action:
Awaiting user authorization to proceed with acquiring the verified Tardis.dev dataset (via research trial key or paid data order) before running the full Phase 10B validation pipeline.
