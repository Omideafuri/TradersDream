# PHASE 10C.X.1 — REPRODUCIBILITY & VERIFICATION GUIDE

## 1. VERIFICATION COMMANDS

To reproduce the exact audit results, metrics, and tables:

```bash
# 1. Download raw data from CryptoDataDownload
python -m phase10cx1.downloader

# 2. Process, aggregate, and audit data quality
python -m phase10cx1.processor

# 3. Execute master evaluation and generate all reports
python -m phase10cx1.evaluator
```

---

## 2. CRYPTOGRAPHIC INTEGRITY TABLE

| Artifact File | Expected SHA-256 Checksum |
|:---|:---|
| `phase10cx1/data/raw/cryptodatadownload/binance_btcusdt_1m/Binance_BTCUSDT_2023_minute.csv` | `0d60d40c4eb6caf1f6c88c733b349e2fffe4b9b02628d69d6f78248cdf4f3b86` |
| `phase10cx1/data/raw/cryptodatadownload/binance_btcusdt_1m/Binance_BTCUSDT_2024_minute.csv` | `92339659cff4357dae8847b28c5a4269bbfe4b9c1b876b79847a7df3e407af72` |
| `phase10cx1/data/processed/BINANCE_BTCUSDT_5m_FROM_CDD.csv` | `d770f98099c872be465ef7889af501a2f55603bf56bb5f23a524f76b5d2836df` |
