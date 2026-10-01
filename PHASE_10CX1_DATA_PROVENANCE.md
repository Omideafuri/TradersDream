# PHASE 10C.X.1 — DATA PROVENANCE REPORT

## 1. SOURCE REGISTRATION

- **Data Provider**: CryptoDataDownload ([cryptodatadownload.com](https://www.cryptodatadownload.com/data/binance/))
- **Venue**: **BINANCE SPOT** (Global offshore spot exchange)
- **Market / Symbol**: `BTCUSDT`
- **Granularity**: 1-minute native OHLCV $\rightarrow$ Deterministically aggregated to 5-minute OHLCV

---

## 2. RAW SOURCE ARTIFACTS

| Raw File | Source URL | SHA-256 Checksum | File Size | Record Count | Time Span (UTC) |
|:---|:---|:---|:---|:---|:---|
| `Binance_BTCUSDT_2023_minute.csv` | `https://www.cryptodatadownload.com/cdd/Binance_BTCUSDT_2023_minute.csv` | `0d60d40c4eb6caf1f6c88c733b349e2fffe4b9b02628d69d6f78248cdf4f3b86` | 55,575,196 bytes | 525,517 rows | 2023-01-01 00:00:00 $\rightarrow$ 2023-12-31 23:59:00 |
| `Binance_BTCUSDT_2024_minute.csv` | `https://www.cryptodatadownload.com/cdd/Binance_BTCUSDT_2024_minute.csv` | `92339659cff4357dae8847b28c5a4269bbfe4b9c1b876b79847a7df3e407af72` | 60,617,495 bytes | 571,339 rows | 2024-01-01 00:00:00 $\rightarrow$ 2025-01-31 23:59:00 |

Total Raw 1-Minute Rows: **1,096,856**  
Total Calendar Coverage: **762 days** (25 months)

---

## 3. PROCESSED 5-MINUTE DATASET

- **File Path**: `phase10cx1/data/processed/BINANCE_BTCUSDT_5m_FROM_CDD.csv`
- **SHA-256**: `d770f98099c872be465ef7889af501a2f55603bf56bb5f23a524f76b5d2836df`
- **Bar Count**: **219,378 bars**
- **Date Range**: 2023-01-01 00:00:00 UTC $\rightarrow$ 2025-01-31 23:55:00 UTC
- **Bucket Alignment**: UTC-aligned 5-minute discrete intervals (`timestamp_ms // 300000 * 300000`)
