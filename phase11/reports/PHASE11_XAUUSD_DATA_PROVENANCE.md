# PHASE 11 — XAU/USD DATA PROVENANCE REPORT

**Phase:** Phase 11 — Quantitative XAU/USD Research Track  
**Date:** September 30, 2026  
**Auditor / Researcher:** Quantitative Research & Microstructure Verification Team  
**Status:** COMPLETE & INDEPENDENTLY QUALIFIED  

---

## 1. Executive Summary & Instrument Scope

This document establishes the formal forensic provenance of the dataset acquired for **Phase 11: XAU/USD Quantitative Trading Research**.

### Strict Scope Verification:
* **Target Instrument:** `XAU/USD` (Spot Gold vs. US Dollar).
* **Instrument Classification:** Over-The-Counter (OTC) Spot Commodity / Precious Metal.
* **Prohibited Substitutions Checked:**
  - COMEX Gold Futures (GC) — NOT USED.
  - Micro Gold Futures (MGC) — NOT USED.
  - Gold Exchange Traded Funds (e.g., GLD, IAU) — NOT USED.
  - Gold Mining Equities (e.g., GDX, NEM) — NOT USED.
  - Silver / Other Commodities (e.g., XAG/USD) — NOT USED.
  - Crypto / BTC / ETH — STRICTLY ISOLATED & NOT USED.
  - Synthetic gold indices — NOT USED.

The data acquired represents authentic, tick-aggregated 1-minute market price action for physical spot Gold priced in US Dollars (`XAU/USD`).

---

## 2. Primary Source & Acquisition Channel

* **Primary Provider:** `HistData.com` (MetaTrader Historical 1-Minute ASCII Archive).
* **Mirror / Retrieval Gateway:** Hugging Face Repository `fokan/xauusd-2009-2026`.
* **Download Agent:** `phase11/data/downloader.py`.
* **Raw Storage Directory:** `phase11/data/raw/`.
* **Processed Storage Directory:** `phase11/data/processed/`.
* **Temporal Coverage:** January 3, 2021 23:00:00 UTC through December 31, 2025 21:57:00 UTC (5 full calendar years).
* **Total Raw Data Size:** 115,678,783 bytes (~115.7 MB).
* **Total Authentic 1-Minute Records:** 1,726,249 clean bars (after deduplication of 300 boundary overlaps).

---

## 3. Raw Data Manifest & Cryptographic Hashes

Every raw file was downloaded via verified HTTPS, saved without alteration, and verified with SHA-256 checksums:

| Raw File Name | Calendar Year | File Size (Bytes) | Row Count | SHA-256 Hash |
| :--- | :---: | :---: | :---: | :--- |
| `DAT_MT_XAUUSD_M1_2021.csv` | 2021 | 23,680,882 | 353,446 | `e02c49ae7499f5ed65a1e2f94b1fc7e408ec25be8e25d2cba50baea9d81d2f95` |
| `DAT_MT_XAUUSD_M1_2022.csv` | 2022 | 23,760,076 | 354,628 | `569cb0fbec2ee300fa6c026046e7f8279fe100c50fc7d23d8c8dfca039b56f87` |
| `DAT_MT_XAUUSD_M1_2023.csv` | 2023 | 20,690,404 | 308,812 | `edb837ffecd22c6a2c27774e1d5569e5d4cb31056f7e8a93e3d489b0266e74eb` |
| `DAT_MT_XAUUSD_M1_2024.csv` | 2024 | 23,828,684 | 355,652 | `0e9487ddd2d27917ec79e51c888d2fef113fe270bdf0fc3456c68e146eb53e77` |
| `DAT_MT_XAUUSD_M1_2025.csv` | 2025 | 23,718,737 | 354,011 | `ea93f456b0e9d982ec79f8fa55342a3e0be951a8ba96677f54c9c10443c5e884` |

---

## 4. Timezone & Temporal Standardization

HistData raw ASCII feeds format timestamps in `YYYY.MM.DD HH:MM`. According to HistData's canonical documentation:
> *"All historical data is recorded in Eastern Standard Time (EST) without Daylight Saving Time adjustments."*

* **Standard Offset:** Eastern Standard Time (EST) is permanently UTC-5.
* **Conversion Formula:**
  $$\text{Timestamp}_{\text{UTC}} = \text{Timestamp}_{\text{EST}} + 5\text{ hours}$$
  $$\text{Epoch Milliseconds} = (\text{Timestamp}_{\text{UTC}} - \text{1970-01-01T00:00:00Z}) \text{ in ms}$$
* **Trading Calendar Behavior:**
  - Gold spot market opens Sunday ~18:00 EST (23:00 UTC) and closes Friday ~17:00 EST (22:00 UTC).
  - Weekend closures span approximately 48 hours.
  - Across the 5-year capture, exactly 260 weekend market closures occurred, perfectly matching the 52 weeks/year $\times$ 5 years expected market structure.

---

## 5. Processed Datasets & Resampling Integrity

All multi-timeframe datasets were deterministically aggregated from the 1,726,249 authentic 1-minute bars using zero-lookahead, left-closed time buckets:

$$\text{bucket} = \left\lfloor \frac{\text{timestamp\_ms}}{\Delta t} \right\rfloor \times \Delta t$$
$$\text{Open} = \text{First}_{t \in \text{bucket}}(\text{Open}), \quad \text{High} = \max_{t \in \text{bucket}}(\text{High}), \quad \text{Low} = \min_{t \in \text{bucket}}(\text{Low}), \quad \text{Close} = \text{Last}_{t \in \text{bucket}}(\text{Close})$$

| Timeframe | File Name | Bars | File Size (Bytes) | SHA-256 Hash |
| :---: | :--- | :---: | :---: | :--- |
| **1m** | `XAUUSD_M1_CLEAN_2021_2025.csv` | 1,726,249 | 125,990,159 | `6e71c041cf36d064734fdd7a4ed4df32ab6deaa476bc6e44f9b10a07ff1d0a65` |
| **5m** | `XAUUSD_5M_2021_2025.csv` | 345,351 | 27,277,031 | `0dba1d94c01fec0c9003511f1d8a4b6a9371dedab0d4f6ba6017590a708f2a1d` |
| **15m** | `XAUUSD_15M_2021_2025.csv` | 115,124 | 9,092,772 | `84eed4f40ca151fd81ce820ed9a523428c14babeaf5d34f7d83a4012cadc53a0` |
| **30m** | `XAUUSD_30M_2021_2025.csv` | 57,567 | 4,546,723 | `0242190bef52204ccb108b927c03e42503f59c7e7d1ccf89c576449635e11fb4` |
| **1h** | `XAUUSD_1H_2021_2025.csv` | 28,796 | 2,274,323 | `b17d067c93d441e35168f014a18461d7bb2005ce0dcebb1f11f41183caee3620` |
| **4h** | `XAUUSD_4H_2021_2025.csv` | 7,967 | 629,234 | `6a309eaafcdad49eb03192d11b42ee11379203cbea0d9486a17c3e60ee0042e1` |

---

## 6. Chronological Partitioning Integrity

To prevent data leakage, overfitting, and selection bias, the 5-year dataset is partitioned chronologically into three non-overlapping subsets:

1. **Development Set (60% / 3 Years):**
   - Span: `2021-01-03 23:00:00 UTC` to `2023-12-29 21:57:00 UTC`
   - Purpose: Feature discovery, indicator calibration, baseline comparison.
2. **Validation Set (20% / 1 Year):**
   - Span: `2024-01-01 23:00:00 UTC` to `2024-12-31 21:57:00 UTC`
   - Purpose: Model selection, multi-timeframe confirmation, rule freezing.
3. **Final Holdout Set (20% / 1 Year):**
   - Span: `2025-01-01 23:00:00 UTC` to `2025-12-31 21:57:00 UTC`
   - Purpose: Out-of-sample blind validation. **SEALED UNTIL STRATEGY FREEZE.**

---

## 7. Forensic Sign-Off

The dataset has been verified to be authentic, uncorrupted, strictly monotonic, free of synthetic extrapolation, and completely isolated from the ongoing crypto research track.
