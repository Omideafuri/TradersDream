# PHASE 10C — HISTORICAL L2 MARKET DATA SOURCE AUDIT

**Document Identifier**: `PHASE10C_DATA_SOURCE_AUDIT.md`  
**Phase**: Phase 10C Authentic L2 Data Acquisition & Qualification  
**Platform**: Jev Crypto-Trading Research System  
**Date**: `2026-09-29T07:40:00+00:00`  
**Safety Invariants Enforced**: `PAPER_TRADING_ONLY = true`, `USE_LIVE_JEV = false`, `LEVERAGE = 1.0`  
**Financial Commitment**: $0.00 (Zero paid subscriptions, zero payments, zero contract commitments)

---

## 1. Executive Summary & Audit Scope

Phase 10C was initiated to conduct a rigorous, scientifically defensible forensic audit of all available sources for historical event-level Level-2 (L2) market data. 

Phase 10B.6 completed code remediation, release verification, and proved order-book transactional atomicity across all test suites (245/245 passing). However, Phase 10C remained strictly blocked because authentic historical event-level L2 data had not yet been formally acquired and qualified.

The audit scope covers eight distinct candidate channels across five categories:
1. Exchange-native public archives (Binance Data Vision, Coinbase REST/Replay).
2. Specialized market data aggregators (Tardis.dev, Kaiko, Databento).
3. Community & secondary data platforms (ByKaranteli / CoinAPI).
4. Academic and open data repositories (Zenodo, Hugging Face, Kaggle, Academic Torrents).
5. Native real-time capture infrastructure (`phase10b4/collector`).

---

## 2. Scientific Classification Taxonomies

To prevent methodological error, data sources are classified into five mutually exclusive scientific tiers:

```text
[TIER 1] AUTHENTIC_L2_DATA:
         Contains raw or normalized incremental order-book deltas (add/modify/delete)
         and discrete book snapshots derived directly from exchange matching engine WebSocket streams.
         Supports deterministic order-book state ladder reconstruction.

[TIER 2] TRADE_ONLY_DATA:
         Contains discrete executed trade ticks (price, quantity, timestamp, trade ID, aggressor side).
         Does NOT contain depth or order-book updates; cannot reconstruct liquidity or queue depth.

[TIER 3] OHLCV_CANDLE_DATA:
         Aggregated periodic time bars (open, high, low, close, volume).
         Lacks all intra-bar microstructural ordering and book state.

[TIER 4] RECONSTRUCTED_PROXY_DATA:
         Synthesized, volume-profile estimated, or candle-interpolated depth states.
         STRICTLY REJECTED for microstructural execution research.

[TIER 5] SYNTHETIC_TEST_FIXTURES:
         Engineered mock objects for algorithmic unit testing (e.g. tests/test_phase10b_*.py).
         Must never be confused with empirical market evidence.
```

---

## 3. Comprehensive Source Investigation Matrix

| Candidate Source | Exchange / Venue | Data Category | Data Types Available | Licensing & Access Terms | Financial Cost | Deterministic L2 Reconstruction Capable? | Qualification Verdict |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Binance Data Vision** (`data.binance.vision`) | Binance.com (Global) | Exchange Public S3 Archive | Monthly/daily `trades`, `aggTrades`, `klines` (Spot). Spot depth omitted. | Public domain research archive. No auth required. | **$0.00** | **NO** (Spot depth deltas not archived; only USD-M Futures has depth) | **REJECTED — MISSING SPOT L2 DELTAS** |
| **Coinbase Native REST** | Coinbase Exchange | Exchange REST Endpoint | Rolling 100 executed trades, current snapshot `/book?level=2` | Free public API (rate-limited). No historical stream archive. | **$0.00** | **NO** (Real-time snapshot only; no historical delta replay) | **REJECTED — NO HISTORICAL ARCHIVE** |
| **Tardis.dev** (Free Tier) | Binance.US / Coinbase | Commercial Aggregator | `incremental_book_L2` (snapshots + deltas) & `trades` (with aggressor side) | Free access restricted strictly to 1st day of each month (`YYYY-MM-01`). | **$0.00** | **YES** (Microsecond exchange timestamps, discrete snapshots, atomic packet grouping) | **ACCEPTED (BOUNDED SAMPLE ONLY)** |
| **Tardis.dev** (Full Commercial) | Binance.US / Coinbase / Kraken | Commercial Aggregator | Full continuous daily `incremental_book_L2` and `trades` from 2019 to present | Commercial subscription / monthly API key ($300 minimum order requirement). | **$300 – $1,000 / mo** | **YES** (Continuous 30-day coverage available) | **DISQUALIFIED BY BUDGET CONSTRAINT ($0.00)** |
| **Kaiko Data** | Multi-exchange | Institutional Enterprise | Level-2 depth snapshots and tick trade archives | Enterprise contract required. No public download or programmatic trial. | **$1,500 – $5,000+ / mo** | **YES** (Snapshot-based L2 depth) | **REJECTED — ENTERPRISE BARRIER** |
| **Databento** | Multi-venue | High-Performance Market Data | MBP-10 (Market-By-Price top 10), trades, and MBO feeds | Pay-as-you-go per GB downloaded. Crypto venue coverage for Binance.US USDT pairs is limited. | **Pay-per-GB (~$0.10/GB)** | **YES** (Top 10 levels only, not full depth) | **REJECTED — INCOMPLETE SPOT COVERAGE & PAID** |
| **ByKaranteli / Kaggle / HF** | Binance Global / Multi | Secondary Community Mirrors | Daily summary snapshots, OHLCV bars, select trade dumps | Community uploaded. Sporadic updates, inconsistent schemas, missing sequence IDs. | **$0.00** | **NO** (Lacks atomic incremental delta packet stream) | **REJECTED — INSUFFICIENT PROVENANCE & SCHEMA DRIFT** |
| **Zenodo Open Archives** | Academic Repositories | Academic Open Access | Specific research paper datasets (e.g. 2018–2021 BTC/USDT trades, select order book snapshots) | Open access (CC-BY). Dates do not align with modern Binance.US market structure. | **$0.00** | **NO** (Static snapshots; lacks continuous microsecond delta stream) | **REJECTED — OBSOLETE REGIME & INCOMPLETE STREAM** |
| **Phase 10B.4 Live Collector** | Binance.US Public WebSocket | Live Repository Capture Engine | Real-time `depthUpdate` (`@depth@100ms`) and `trade` streams captured via WebSocket | Free public WebSocket connection. Captures events forward in time. | **$0.00** | **YES** (Authentic live events with sequence IDs `U`/`u`) | **VALID FOR FORWARD CAPTURE (NOT HISTORICAL)** |

---

## 4. Technical Analysis of Candidate Sources

### 4.1. Binance Data Vision (`data.binance.vision`)
Inspection of the underlying Amazon S3 bucket (`https://s3-ap-northeast-1.amazonaws.com/data.binance.vision`) revealed:
- `data/spot/daily/`: Contains exclusively `aggTrades/`, `klines/`, and `trades/`.
- **Finding**: Binance does **not** archive historical incremental Level-2 order-book deltas for spot markets. Spot order-book depth is completely omitted.
- USD-M Futures (`data/futures/um/daily/bookDepth/`) does archive depth, but utilizing futures data violates core invariants:
  1. Leverage / Derivatives Prohibited: The project is strictly an unleveraged spot paper trading system (`LEVERAGE = 1.0`).
  2. Exchange Divergence: Binance Global futures liquidity, funding rates, and liquidation mechanics differ substantially from Binance.US spot microstructure.

### 4.2. Tardis.dev Public Free Tier
- **Empirical Validation**: Tardis provides publicly downloadable, unauthenticated CSV archives for the first day of each calendar month at `https://datasets.tardis.dev/v1/binance-us/`.
- Verified accessible endpoints:
  - `https://datasets.tardis.dev/v1/binance-us/incremental_book_L2/2024/03/01/BTCUSDT.csv.gz` (8.66 MB compressed, 90.64 MB uncompressed, 1,245,143 records).
  - `https://datasets.tardis.dev/v1/binance-us/trades/2024/03/01/BTCUSDT.csv.gz` (0.19 MB compressed, 0.97 MB uncompressed, 12,320 records).
- **Access Boundary Verified**: Requesting day 2 (`2024/03/02`) or any other non-first-day returns unauthenticated/blocked status. Continuous 30-day coverage is impossible to obtain for free from this source.

### 4.3. Academic and Community Platforms (Zenodo, Hugging Face, Kaggle)
- Datasets on Hugging Face and Kaggle (e.g. ByKaranteli mirrors) provide aggregated 1-minute order book summaries or top-5 snapshots, not raw tick-level event deltas.
- No public academic repository hosts a verified, continuous 30-day microsecond-level incremental L2 feed for Binance.US BTC/USDT.

---

## 5. Audit Conclusion & Phase Gate Finding

1. **Authentic L2 Data Identified**: Authentic historical L2 order-book events and tick trades exist and are freely accessible via Tardis.dev for first-of-month sample dates (`2024-03-01`).
2. **Coverage Constraint**: Free historical L2 data is limited to discrete, disconnected single-day slices. Continuous 30-day historical L2 archives cannot be procured without financial expenditure.
3. **Formal Classification**:
   - Technical Validity: **VALID**
   - Data Sufficiency for 30-day continuous backtest: **INSUFFICIENT**
   - Phase 10C Result: **PARTIALLY_QUALIFIED**
   - Phase 10D Status: **BLOCKED** pending continuous data acquisition.
