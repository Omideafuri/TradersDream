# PHASE 10C.X.1 — DATA QUALITY & INTEGRITY AUDIT

## 1. CANDLE INVARIANT VERIFICATION

Every candle was audited against standard market data integrity rules:

| Invariant Check | Required Rule | Violations Found | Status |
|:---|:---|:---|:---|
| High vs Low | $\text{High} \ge \text{Low}$ | 0 | PASS |
| High vs Open | $\text{High} \ge \text{Open}$ | 0 | PASS |
| High vs Close | $\text{High} \ge \text{Close}$ | 0 | PASS |
| Low vs Open | $\text{Low} \le \text{Open}$ | 0 | PASS |
| Low vs Close | $\text{Low} \le \text{Close}$ | 0 | PASS |
| Positive Prices | $\text{Open}, \text{High}, \text{Low}, \text{Close} > 0$ | 0 | PASS |
| Non-Negative Volume | $\text{Volume} \ge 0$ | 0 | PASS |
| Deduplication | Unique timestamps | 0 duplicate rows | PASS |

---

## 2. CONTINUITY & INTERVAL AUDIT

- **Nominal Sampling Interval**: 60 seconds (1-minute)
- **Total Theoretical Minutes (2023-01-01 to 2025-01-31)**: 1,097,280 minutes
- **Observed 1-Minute Bars**: 1,096,856 bars
- **Total Missing Minutes**: 424 minutes
- **Completeness Rate**: **99.9614%**
- **Number of Discrete Gap Episodes**: 36 episodes
- **Longest Gap**: 311 minutes (5.18 hours, scheduled exchange maintenance)

---

## 3. FORENSIC FINDING — TIMESTAMP PRECISION SHIFT

During the ingestion audit, a critical formatting change was detected inside `Binance_BTCUSDT_2024_minute.csv`:
- Rows 44,609 to 571,338 (covering all of 2024) use standard **millisecond Unix timestamps** (13 digits, e.g. `1704067200000`).
- Rows 0 to 44,608 (covering January 2025) switch to **microsecond Unix timestamps** (16 digits, e.g. `1738367940000000`), which causes the raw `Date` string column in the CDD CSV to display corrupted year `1970` strings due to an unscaled division in their export pipeline.
- The `phase10cx1/processor.py` engine successfully detected this condition and scaled all timestamps to standardized UTC milliseconds prior to 5-minute aggregation. Zero data was lost or corrupted.
