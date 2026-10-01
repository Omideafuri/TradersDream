# PHASE 10C.X — DATA PROVENANCE & LINEAGE AUDIT

## 1. DATASET REGISTRATION & VERIFICATION

| Dataset Role | File Path | SHA-256 Checksum | Record Count | Time Span (UTC) |
|:---|:---|:---|:---|:---|
| Authentic L2 Incremental Book | `phase10b4/data/sample_binance-us_incremental_book_L2_2024-03-01_BTCUSDT.csv` | `f15a7d14691d85c62b496b1b57598c791fe18b1ebc0cc4bb05d8fd962fbc79df` | 8,000 rows (2,231 pkts, 7,997 deltas) | 2024-03-01 00:00:00 to 00:08:16 |
| Authentic L2 Trade Executions | `phase10b4/data/sample_binance-us_trades_2024-03-01_BTCUSDT.csv` | `bd02cb034ef0baf027ce9040d8ab465af3c8283fe31b3fc1dbc87fad0c953fcc` | 38 trades | 2024-03-01 00:00:16 to 00:08:14 |
| 30-Day Sealed Holdout Candles | `data/phase9_data/BINANCE_US_BTCUSDT_5m.csv` | `f72be9be809e599481909d12126f47c6569faaa85717a3dc9109c4800250b515` | 8,640 bars (last 30d of 26,000 bars) | 2026-08-22 00:00:00 to 2026-09-21 00:00:00 |

---

## 2. LINEAGE AND CONTAMINATION AUDIT

1. **Phases 1–8 Isolation**: Phases 1–8 utilized `data/historical/BTCUSDT_5m_candles.csv` (1,500 bars from Jan 1–6, 2024). Neither the Phase 9 holdout nor the March 1, 2024 L2 data was exposed to the model during Phases 1–8.
2. **Phase 9 Holdout Integrity**: The 30-day temporal replay utilizes the sealed holdout portion (bars 20,800 to 25,999) of `data/phase9_data/BINANCE_US_BTCUSDT_5m.csv`. This partition was frozen in `PHASE9D_PRE_HOLDOUT_FREEZE.md` and was never accessible to feature optimization.
3. **Phase 10B/C L2 Fixture**: The authentic Binance.US March 1, 2024 L2 dataset was retrieved from Tardis.dev solely as a technical qualification fixture in Phase 10B.4. It was never used to fit or train trading rules.
4. **Historical L2 Data Availability Constraint**:
   - As established in `PHASE10C_DATA_SOURCE_AUDIT.md`, 30 continuous calendar days of tick-by-tick L2 data for Binance.US spot are not freely hosted in open-access public repositories (free access is limited to the 1st of each month; full 30-day continuous depth feeds require commercial subscriptions of $300–$1,000/month).
   - In accordance with Phase 10C.1 and Phase 10C.2, continuous authentic L2 collection was launched on live Binance.US spot WebSocket infrastructure (PID 7236/9736) to acquire 30 continuous days forward.
   - For historical backtesting in Phase 10C.X, the test evaluates the authentic March 1, 2024 L2 stream for microstructural accuracy and the sealed 30-day holdout for macro-temporal robustness.
