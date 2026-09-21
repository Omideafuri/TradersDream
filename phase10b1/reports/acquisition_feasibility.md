# PHASE 10B.1 — DATA ACQUISITION FEASIBILITY & PROCUREMENT REPORT

**Document Identifier**: `phase10b1/reports/acquisition_feasibility.md`  
**Phase**: Phase 10B.1 Historical Event-Data Source Discovery & Acquisition  
**Audit Date**: `2026-09-22T03:20:00+00:00`  
**Safety Status**: Zero Financial Commitments Incurred (Section 40 Compliance Verified).

---

## 1. EXECUTIVE PROCUREMENT SUMMARY

To fulfill the Phase 10A protocol requirements:
* Target Assets: `BTCUSDT`, `ETHUSDT`, `SOLUSDT` (Spot).
* Target Feeds: Tick-by-tick trades (`trades`) + Incremental Level-2 order book updates with initial snapshots (`incremental_book_L2`).
* Minimum Historical Span: 30 consecutive calendar days per asset (e.g., 2026-06-23 through 2026-07-23, or 2024-01-01 through 2024-01-31).

Following a systematic market scan across exchange archives, public repositories, and commercial data providers, **Tardis.dev** has been identified and qualified as the **sole viable provider** capable of supplying continuous, synchronized, microsecond-timestamped historical L2 deltas and tick trades for spot Binance.US and Coinbase.

However, because full 30-day historical downloads exceed the scope of free first-of-month samples, **a paid data subscription or formal 30-day research trial key is required**.

---

## 2. PROCUREMENT COST ANALYSIS

| Option | Provider | Data Scope | Estimated Cost (USD) | Procurement Mechanism | Feasibility Status |
|---|---|---|---|---|---|
| **Option 1: 30-Day Research Trial Key** | Tardis.dev | 7–14 days rolling historical sample | **$0.00** | Submit academic / research trial request to Tardis support | **Recommended First Step** |
| **Option 2: Solo / Monthly Subscription** | Tardis.dev | Full multi-month / multi-year historical CSV downloads (Binance.US) | **$300.00 – $600.00** | Self-serve custom quote form with credit card / crypto payment | **Feasible upon User Authorization** |
| **Option 3: Enterprise Contract** | Kaiko | Tick trades + L2 depth flat files | **$15,000 – $30,000+** | Enterprise sales contract negotiation | **Infeasible (Cost Barrier)** |
| **Option 4: Pay-As-You-Go** | Databento | Nanosecond MBP-10 (Coinbase) | **$50.00 – $150.00** | Self-serve API credit account | **Partial (USDT pairs limited)** |

---

## 3. DATA VOLUME & STORAGE REQUIREMENTS

Based on empirical benchmarks from Binance.US order-book update rates:
* **Trades Stream**:
  - Estimated trade events per day: $\approx 250,000\text{ to }750,000$ trades/day for BTCUSDT; $\approx 150,000$ for ETH; $\approx 100,000$ for SOL.
  - Compressed CSV size: $\approx 15\text{--}35\text{ MB}$ per asset per day.
  - 30-day Trades total: $\approx 1.5\text{--}3.0\text{ GB}$ compressed across all 3 assets.
* **Incremental L2 Order-Book Updates (`incremental_book_L2`)**:
  - Estimated delta updates per day: $\approx 5,000,000\text{ to }15,000,000$ updates/day for BTCUSDT; $\approx 4,000,000$ for ETH; $\approx 3,000,000$ for SOL.
  - Compressed CSV size: $\approx 150\text{--}400\text{ MB}$ per asset per day.
  - 30-day Incremental L2 total: $\approx 15\text{--}35\text{ GB}$ compressed across all 3 assets.
* **Storage Footprint**: Total disk space required: $\approx 20\text{--}40\text{ GB}$ compressed, or $\approx 100\text{--}200\text{ GB}$ uncompressed Parquet/Arrow.
* **Storage Recommendation**: Store raw gzipped CSVs in `data/phase10b/raw/` and convert directly to columnar Parquet in `data/phase10b/normalized/` with snappy compression to minimize I/O overhead during backtesting.

---

## 4. LICENSING & TERMS OF USE

1. **Academic / Solo Research Terms**:
   - Permits internal research, quantitative analysis, strategy backtesting, and algorithmic model development.
   - Prohibits public redistribution or commercial resale of raw exchange-level data feeds.
   - Permits publication of derived academic findings, summary statistics, charts, and mathematical performance metrics.
2. **Attribution Requirements**:
   - Academic and research publications must cite Tardis.dev as the underlying market data provider.

---

## 5. REPRODUCIBILITY & PIPELINE INTEGRATION

The data schemas provided by Tardis match the Phase 10B ingestion requirements:
```text
Tardis incremental_book_L2
   ├── is_snapshot=true ──────────► Phase 10B L2Snapshot (load_snapshot)
   ├── is_snapshot=false ─────────► Phase 10B L2Delta (apply_delta)
   ├── price & amount ────────────► Phase 10B Price Ladder (amount=0 -> delete)
   └── local_timestamp ───────────► Phase 10B Atomic Message Grouping

Tardis trades
   ├── timestamp / local_ts ──────► Phase 10B TickTrade
   ├── price & amount ────────────► Phase 10B Price & Quantity bounds
   └── side (buy/sell) ───────────► Phase 10B AggressorSide (BUY/SELL)
```
Once the raw CSV files are placed in `data/phase10b/raw/`, the existing `phase10b/reconstructor.py`, `validator.py`, and `alignment.py` modules can parse and qualify the entire dataset deterministically.

---

## 6. STOPPING GATE: FINANCIAL AUTHORIZATION

In accordance with Section 40 of the Phase 10B.1 directive:
> **DO NOT BUY ANYTHING WITHOUT EXPLICIT USER AUTHORIZATION.**
> **STATUS: PAID ACQUISITION REQUIRED**

The research system has halted at the procurement gate:
* **Identified Source**: Tardis.dev
* **Target Dataset**: Binance.US `BTCUSDT`, `ETHUSDT`, `SOLUSDT` (30 days of `incremental_book_L2` + `trades`).
* **Estimated Cost**: $300.00 (minimum order requirement) or free trial request.
* **Action Required**: Await explicit user authorization before initiating commercial procurement.
