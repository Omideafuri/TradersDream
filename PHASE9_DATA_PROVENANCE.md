# PHASE 9 DATA PROVENANCE MANIFEST
**System**: Phase 9 — Independent Market Data & Microstructure Research  
**Date**: 2026-09-22T02:00:00Z  
**Status**: ACTIVE / AUDITABLE  

---

## 1. Provenance Policy & Standards
Every dataset in the research corpus is assigned immutable metadata, cryptographic SHA256 fingerprints, and explicit categorical classifications for:
- **Synthetic Status**: `GENUINE`, `SYNTHETIC`, or `UNKNOWN`.
- **Independence Status**: `INDEPENDENT`, `NON_INDEPENDENT`, or `UNKNOWN`.

Silent overwrites are prohibited by `phase9/dataset_registry.py`. Any dataset mutation requires registering a new version ID (e.g. `_V2`).

---

## 2. Historical Datasets (Phases 1–8)

The historical datasets located in `data/historical/` are cataloged as immutable historical reference baselines:

### `HIST_BTCUSDT_5M_202401_V1`
- **Asset / Symbol**: `BTC` / `BTCUSDT`
- **Exchange / Source**: `LOCAL_HISTORICAL` / Binance Archive (Public)
- **Timeframe**: 5-minute candles (`5m`)
- **Row Count**: 1,500 rows
- **Temporal Span**: `2024-01-01T00:00:00Z` to `2024-01-06T04:55:00Z` (~5.2 days)
- **SHA256**: `3bbdfd6c25b607ee72fbf409e51dd2eb5845f8cb6eb7f2d4e73b22cfdc820a40`
- **Synthetic Status**: **`GENUINE`**
- **Independence Status**: **`INDEPENDENT`**
- **Notes**: Single-asset historical baseline. Free of look-ahead bias and forward leakage, but limited in duration.

### `HIST_ETHUSDT_5M_202401_V1`
- **Asset / Symbol**: `ETH` / `ETHUSDT`
- **Exchange / Source**: `LOCAL_HISTORICAL`
- **Timeframe**: 5-minute candles (`5m`)
- **Row Count**: 1,500 rows
- **Temporal Span**: `2024-01-01T00:00:00Z` to `2024-01-06T04:55:00Z`
- **SHA256**: `9639e8a030ae16b8ef6c3b6924e29cb1f57ce355aa13bcf3d46bf365bca50df6`
- **Synthetic Status**: **`SYNTHETIC`**
- **Independence Status**: **`NON_INDEPENDENT`**
- **Notes**: **`SYNTHETIC / NON-INDEPENDENT / HISTORICAL-ONLY`**. Identified in Phase 8 (`DISC-001`) as a deterministic price-scaled copy of BTC ($r = 1.0000$, return delta $\approx 0$). Preserved as historical record; prohibited as independent evidence.

### `HIST_SOLUSDT_5M_202401_V1`
- **Asset / Symbol**: `SOL` / `SOLUSDT`
- **Exchange / Source**: `LOCAL_HISTORICAL`
- **Timeframe**: 5-minute candles (`5m`)
- **Row Count**: 1,500 rows
- **Temporal Span**: `2024-01-01T00:00:00Z` to `2024-01-06T04:55:00Z`
- **SHA256**: `9dcd24fbdb5a28525bcf7a6e1335cb8c75ecf23f81e35492d549887711910cf9`
- **Synthetic Status**: **`SYNTHETIC`**
- **Independence Status**: **`NON_INDEPENDENT`**
- **Notes**: **`SYNTHETIC / NON-INDEPENDENT / HISTORICAL-ONLY`**. Identified in Phase 8 (`DISC-001`) as a deterministic price-scaled copy of BTC ($r = 0.99996$, return delta $\approx 3.12 \times 10^{-6}$). Preserved as historical record; prohibited as independent evidence.

---

## 3. External Ingestion Source Provenance

Public exchange adapters implemented in `phase9/ingestion/` provide authenticated-free access to public market data and microstructure snapshots:

| Adapter | Canonical Source | Endpoint | Status | Supported Telemetry |
| :--- | :--- | :--- | :---: | :--- |
| **`CoinbaseAdapter`** | `COINBASE` | `https://api.exchange.coinbase.com` | **`AVAILABLE`** | 1m/5m/15m/1h OHLCV, Level-2 Order Book, Public Trade Flow |
| **`KrakenAdapter`** | `KRAKEN` | `https://api.kraken.com/0/public` | **`AVAILABLE`** | 1m/5m/15m/30m/1h/4h OHLCV (rolling 720 bars), Level-2 Depth, Trades |
| **`OKXAdapter`** | `OKX` | `https://www.okx.com/api/v5` | **`AVAILABLE`** | 1m/5m/15m/1h/4h OHLCV, Level-2 Books, Trades, Perpetual Funding Rates |
| **`BinanceUSAdapter`** | `BINANCE_US` | `https://api.binance.us/api/v3` | **`AVAILABLE`** | 1m/3m/5m/15m/1h/4h/1d Klines, Depth, Trades with Aggressor Flag |
| **Binance Global** | `BINANCE_GLOBAL` | `https://api.binance.com` | **`GEO_RESTRICTED`** | Blocked via regional HTTP 451. Strictly bypassed/excluded. |

---

## 4. Known Data Limitations
1. **Historical Depth**: The existing local repository contains only 5.2 days of historical BTC data. Long-duration multi-month/multi-year historical series must be acquired via paginated backfills from available adapters before executing model training or holdout validation.
2. **Microstructure Persistence**: While live L2 depth snapshots and recent trade ticks can be captured causally, historical longitudinal L2 order books are not provided by free REST endpoints beyond short recent windows.
