# PHASE 10B.1 — MARKET DATA SOURCE COMPARISON MATRIX

**Document Identifier**: `phase10b1/reports/source_comparison.md`  
**Phase**: Phase 10B.1 Historical Event-Data Source Discovery  
**Audit Date**: `2026-09-22T03:20:00+00:00`  
**Evaluation Standard**: Rigorous factual qualification against Phase 10A Passive Execution requirements.

---

## 1. COMPREHENSIVE SOURCE EVALUATION MATRIX

| Criterion | Tardis.dev | Kaiko | Binance Data Vision | Coinbase Native | Databento |
|---|---|---|---|---|---|
| **Provider** | Tardis.dev | Kaiko Data | Binance Official | Coinbase Inc. | Databento Inc. |
| **Exchange** | Binance.US, Binance, Coinbase, Kraken, OKX | Binance, Coinbase, Kraken, Bitstamp | Binance.com | Coinbase Exchange | Coinbase, CME, etc. |
| **BTC Coverage** | `BTCUSDT`, `BTCUSD`, `BTCUSDC` | `BTC-USDT`, `BTC-USD` | `BTCUSDT` | `BTC-USD`, `BTC-USDT` | `BTC-USD`, `BTC-USDT` |
| **ETH Coverage** | `ETHUSDT`, `ETHUSD`, `ETHUSDC` | `ETH-USDT`, `ETH-USD` | `ETHUSDT` | `ETH-USD`, `ETH-USDT` | `ETH-USD` |
| **SOL Coverage** | `SOLUSDT`, `SOLUSD`, `SOLUSDC` | `SOL-USDT`, `SOL-USD` | `SOLUSDT` | `SOL-USD` | Limited / Evolving |
| **Spot / Futures** | Both (Separately cataloged) | Both | Both | Spot Only | Both |
| **Tick Trades** | **YES** (`trades` CSV/NDJSON) | **YES** (Normalized JSON/CSV) | **YES** (Monthly/daily CSV) | **NO** (Only last 100 rolling) | **YES** (MBP-10/Trades) |
| **Incremental L2** | **YES** (`incremental_book_L2`) | **YES** (Tick-level book updates) | **NO** (Not archived for spot) | **NO** (Snapshot only) | **YES** (MBP-10 / MBO) |
| **Full Snapshots** | **YES** (Embedded `is_snapshot=true` + snapshots) | **YES** (Periodic L2 snapshots) | **NO** (Not archived for spot) | **Current Only** | **YES** (Periodic snapshots) |
| **MBP / MBO** | **MBP** (Level 2 price-aggregated) | **MBP** (L2) / Select MBO | **N/A** (No order book data) | **MBP** (L2) via REST | **MBP-10 & MBO** |
| **Sequence IDs** | Preserves atomic arrival order via `local_timestamp` | Sequence / timestamp preserved | Trade IDs only; no book sequence | Trade IDs only | Sequence numbers included |
| **Exchange Timestamps** | **YES** (Exchange matching time) | **YES** (Exchange matching time) | **YES** (Transaction timestamp) | **YES** (Execution timestamp) | **YES** (Engine timestamp) |
| **Timestamp Resolution** | **Microsecond** | **Millisecond / Microsecond** | **Microsecond** (2025+) / ms | **ISO 8601 (ms)** | **Nanosecond** |
| **Historical Start** | 2019-09-25 (Binance.US BTC) | 2015+ (Exchange dependent) | 2017-08-17 (Binance spot) | Current real-time only | 2022+ (Venue dependent) |
| **30-Day Continuity** | **PASS** (Multi-year continuous) | **PASS** (Multi-year continuous) | **FAIL** (Missing L2 deltas) | **FAIL** (0 days historical) | **PASS** (Available on supported venues) |
| **Raw Exchange Format** | Replay/API gives raw WebSocket JSON | Raw S3 dumps (Enterprise) | Raw CSV trade logs | Public REST JSON | DBN / Raw packet captures |
| **Normalized Format** | Standardized CSV / Parquet | Standardized CSV / API | Standardized CSV | Standardized REST JSON | Standardized DBN / Parquet |
| **WebSocket Provenance** | Direct connection to exchange matching gateways | Direct co-located / gateway feeds | Internal database dump | Public REST only | Direct colocation / raw feeds |
| **Replay Capability** | **YES** (Client library historical replay) | **YES** (Historical streaming API) | **NO** | **NO** | **YES** (Live & historical replay) |
| **Download Capability** | **YES** (Gzip CSV batch download via HTTP/SDK) | **YES** (S3 flat files / REST) | **YES** (ZIP files) | **NO** | **YES** (HTTP / Python client) |
| **API Capability** | Python (`tardis-dev`), Node.js, REST | Python SDK, REST API, Snowflake | None (Static HTTP server) | REST API | Python, C++, Rust SDKs |
| **Sample Availability** | Free first-of-month sample downloads & 30-day trial | On request via enterprise sales | Free public downloads (trades only) | Current market only | Free sign-up test credits |
| **Data Gaps Disclosed** | **YES** (Documented in incident reports) | Disclosed in SLA reports | None documented | Not applicable | Logged in metadata |
| **Known Gaps** | Occasional exchange WS disconnects | Disclosed per feed | Maintenance gaps | Not applicable | Disclosed per feed |
| **Documentation Quality** | **High** (Public, complete schemas) | **High** (Enterprise documentation) | **Moderate** (Minimal documentation) | **Moderate** (Public docs) | **Very High** (Engineers/HFT focused) |
| **Licensing** | Academic, Solo, Professional, Enterprise | Enterprise annual contract | Public domain / Binance ToS | Public API ToS | Usage-based research/commercial |
| **Cost** | Min order $300; ~$300–$1,000/mo | ~$1,500–$5,000+/mo | Free ($0) | Free ($0) | Pay-as-you-go (~$0.05–$0.20/GB) |
| **Reproducibility** | **High** (Deterministic, checksummed) | **High** (Deterministic) | **High** (Static files) | **Low** (Ephemeral) | **High** (Deterministic binary DBN) |
| **Phase 10A Compatibility**| **FULL (MBP-Level)** | **FULL (MBP-Level)** | **INCOMPATIBLE (No L2)** | **INCOMPATIBLE (No History)**| **PARTIAL (Venue limits)** |

---

## 2. DETAILED FINDINGS BY PROVIDER

### 2.1 Tardis.dev (Primary Qualified Candidate)
* **Status**: **`QUALIFIED — PAID ACQUISITION REQUIRED`**
* **Capabilities**:
  - Provides synchronized `trades` and `incremental_book_L2` feeds with microsecond timestamps.
  - Covers `BTCUSDT`, `ETHUSDT`, and `SOLUSDT` on Binance.US continuously from September 2019 / September 2020 through the present day.
  - Supports initial depth snapshots embedded directly into the delta stream (`is_snapshot=true`).
* **Limitations**:
  - Data is Level 2 (MBP) price-aggregated depth. Queue position must be modeled as `QUEUE-AHEAD ESTIMATE`, not `EXACT ORDER-LEVEL FIFO`.
  - Acquisition requires a minimum financial commitment of $300 (or trial API access).

### 2.2 Kaiko (Institutional Candidate)
* **Status**: **`NOT QUALIFIED DUE TO ENTERPRISE BARRIER`**
* **Capabilities**: Institutional grade tick trades and L2 snapshots across major global venues.
* **Limitations**: Requires annual enterprise sales negotiation ($15,000–$60,000+ commitment) with no self-serve programmatic acquisition pathway.

### 2.3 Binance Data Vision (Exchange Official Public Archive)
* **Status**: **`NOT QUALIFIED DUE TO MISSING L2 DELTAS`**
* **Capabilities**: Provides free monthly CSV files of spot trades (`trades` and `aggTrades`) from 2017 to present.
* **Fatal Limitation**: Official Binance documentation confirms that **historical Level 2 order book deltas are NOT archived** for spot markets on `data.binance.vision`. Order book reconstruction is mathematically impossible from Binance Vision data alone.

### 2.4 Coinbase Native REST API
* **Status**: **`NOT QUALIFIED DUE TO ABSENCE OF HISTORICAL REPLAY`**
* **Fatal Limitation**: Public REST API provides only the current order-book snapshot (`/book?level=2`) and the latest 100 rolling trades. No historical depth archive exists.

### 2.5 Databento
* **Status**: **`QUALIFIED PARTIALLY — EVOLVING CRYPTO COVERAGE`**
* **Capabilities**: Nanosecond precision, MBP-10 and MBO formats, pay-per-GB usage pricing.
* **Limitations**: Crypto coverage currently prioritizes select venues (e.g. Coinbase) and USD pairs rather than full USDT spot depth across BTC/ETH/SOL.
