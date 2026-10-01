# PHASE 12 — CRITICAL DATA PROVENANCE & FEED INTEGRITY AUDIT

**Project:** Autonomous Quantitative Research & Market Microstructure Verification  
**Phase:** Phase 12 — XAU/USD Real-Market Execution Validation  
**Instrument:** `XAU/USD` (Physical Spot Gold / US Dollar)  
**Auditor:** Forensic Data Integrity & Market Data Verification Group  
**Classification:** **`PROVENANCE: PARTIALLY VERIFIED`**  

---

## 1. Scope & Adversarial Data Verification

This document provides a forensic audit of the historical data files used in Phase 11 and Phase 12.

Rather than accepting the dataset as "authentic institutional data" simply because it passes mathematical OHLC invariants, this audit traces the exact provenance chain from the upstream producer to local storage.

---

## 2. Upstream Provenance Chain

* **Local Storage Path:** `phase11/data/raw/` (`DAT_MT_XAUUSD_M1_2021.csv` through `2025.csv`).
* **Retrieval Gateway:** Hugging Face Repository `fokan/xauusd-2009-2026`.
* **Primary Originator:** `HistData.com` (MetaTrader Historical 1-Minute ASCII Archive).
* **Format:** MetaTrader ASCII CSV format:
  `YYYY.MM.DD,HH:MM,Open,High,Low,Close,Volume` (No header row).
* **Source Feeds:** MetaTrader retail brokerage bridge servers (historically aggregated from retail liquidity providers such as Gain Capital / FOREX.com and FXCM).

---

## 3. Cryptographic Hashes & File Integrity

All raw files downloaded in Phase 11 were re-hashed independently in Phase 12. Hashes are 100% identical and unchanged:

| Raw File Name | Calendar Year | File Size (Bytes) | Row Count | SHA-256 Checksum | Verification |
| :--- | :---: | :---: | :---: | :--- | :---: |
| `DAT_MT_XAUUSD_M1_2021.csv` | 2021 | 23,680,882 | 353,446 | `e02c49ae7499f5ed65a1e2f94b1fc7e408ec25be8e25d2cba50baea9d81d2f95` | **VERIFIED** |
| `DAT_MT_XAUUSD_M1_2022.csv` | 2022 | 23,760,076 | 354,628 | `569cb0fbec2ee300fa6c026046e7f8279fe100c50fc7d23d8c8dfca039b56f87` | **VERIFIED** |
| `DAT_MT_XAUUSD_M1_2023.csv` | 2023 | 20,690,404 | 308,812 | `edb837ffecd22c6a2c27774e1d5569e5d4cb31056f7e8a93e3d489b0266e74eb` | **VERIFIED** |
| `DAT_MT_XAUUSD_M1_2024.csv` | 2024 | 23,828,684 | 355,652 | `0e9487ddd2d27917ec79e51c888d2fef113fe270bdf0fc3456c68e146eb53e77` | **VERIFIED** |
| `DAT_MT_XAUUSD_M1_2025.csv` | 2025 | 23,718,737 | 354,011 | `ea93f456b0e9d982ec79f8fa55342a3e0be951a8ba96677f54c9c10443c5e884` | **VERIFIED** |

---

## 4. Forensic Limitations & Caveats

Despite the integrity of the file downloads and invariant checks, the forensic audit identifies the following critical structural limitations:

1. **Absence of Simultaneous Dual Bid/Ask Quotes:**
   - In MetaTrader standard M1 ASCII exports, each bar contains a single Open, High, Low, and Close price. By MT4/MT5 convention, these represent the **Bid price** at each minute boundary.
   - The dataset does **NOT** contain raw simultaneous Ask quotes.
   - Consequently, Ask prices used for Long entries must be modeled using broker-realistic spread parameters ($\text{Ask} = \text{Bid} + \text{Spread}$).
2. **Absence of Order-Book Liquidity (L2 Depth):**
   - The volume column in MetaTrader ASCII feeds reflects tick count (number of quote updates during that minute), NOT physical contracts or ounce volume.
   - There is no visible Level-2 depth. Market impact for ultra-large orders cannot be modeled from L1 tick volume alone.
3. **Broker-Specific Pricing Adjustments:**
   - HistData prices reflect OTC retail broker pricing. While highly correlated with institutional LBMA gold fixings and COMEX front-month futures, minor basis discrepancies of $\pm \$0.20$ to $\$0.50$ per ounce can exist between individual broker pricing engines.

---

## 5. Formal Provenance Classification

Per Section 4 of the Phase 12 mandate:
> *"If provenance cannot be established [as authentic dual-sided executable broker tick data], explicitly classify it as: PROVENANCE: PARTIALLY VERIFIED."*

Therefore, the dataset is officially designated:
```text
PROVENANCE: PARTIALLY VERIFIED
```
The data is authentic historical broker-indicative Bid price action suitable for macro swing research, but cannot be classified as full institutional Level-1/Level-2 dual-quote archive data.
