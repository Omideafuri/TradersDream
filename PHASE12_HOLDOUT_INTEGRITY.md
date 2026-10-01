# PHASE 12: 2025 HOLDOUT DATA INTEGRITY & CONTAMINATION AUDIT

**Audit Date:** 2026-10-01  
**Instrument:** XAU/USD (Spot Gold)  
**Strategy ID:** `XAUUSD_FROZEN_SMA50_200_1H`  
**Holdout Dataset:** `DAT_MT_XAUUSD_M1_2025.csv` (2025-01-01 to 2025-12-31)  
**Audit Finding:** `PARTIALLY VERIFIED — LOGICAL ENFORCEMENT VERIFIED, PHYSICAL COMMINGLING DETECTED`  

---

## 1. Executive Summary

Under Section 20 of the Phase 12 specification, an audit was conducted into the provenance, storage, and access history of the 2025 holdout dataset.

The investigation examined Git commit history, directory structures, script arguments, and report generation artifacts to determine whether:
1. 2025 data was accessed or evaluated during the Phase 11 strategy discovery phase;
2. Any indicator parameter, threshold, fee assumption, or session filter was tuned using 2025 information;
3. The freeze specification (`PHASE11_RESEARCH_FREEZE.md` and `PHASE12_STRATEGY_LOCK.json`) was enacted prior to final holdout unsealing.

---

## 2. Forensic Codebase & Git Audit Findings

### Codebase Isolation Inspection
A recursive search was executed across all exploratory scripts in `phase11/`:
- **Training Splits:** Exploratory search scripts (`phase11/exploration/strategy_screener.py`) contained explicit temporal filters:
  ```python
  df_train = df[df["dt_utc"] < "2024-01-01"]
  df_val   = df[(df["dt_utc"] >= "2024-01-01") & (df["dt_utc"] < "2025-01-01")]
  ```
- **Holdout Filter:** No exploratory screener included `2025` data in its parameter optimization loop.
- **Physical Commingling:** However, `DAT_MT_XAUUSD_M1_2025.csv` existed in `phase11/data/raw/` from the inception of the repository. Unlike institutional cryptographic multi-party enclaves where out-of-sample data is physically quarantined on an external disconnected host, the 2025 raw file was stored locally alongside the training files.

---

## 3. Contamination Risk Evaluation

| Audit Dimension | Standard Required | Codebase Evidence | Verdict |
| :--- | :--- | :--- | :--- |
| **Parameter Tuning** | 2025 data never used in parameter grid | Strategy screener evaluated only 2021–2024 data | **CLEAN** |
| **Strategy Selection** | Selection ranking executed prior to 2025 | SMA50/200 selected based on 2021–2024 Sharpe | **CLEAN** |
| **Threshold Calibration** | 0 bps / 6 bps friction fixed a priori | Fixed 6 bps round-trip applied universally | **CLEAN** |
| **Data Cleaning** | Cleaning pipeline identical across all years | Uniform 1m deduplication applied to 2021–2025 | **CLEAN** |
| **Physical Isolation** | 2025 file encrypted or stored off-site | File co-located in `phase11/data/raw/` | **SOFT SEAL ONLY** |

---

## 4. Formal Classification

Under Section 20 of the protocol:
- Because no evidence was found that 2025 data modified or tuned the strategy logic, the holdout is **not compromised by parameter leakage**.
- Because the dataset was physically accessible on local disk during the development lifecycle, the audit cannot assign an unconditional "cryptographically sealed" rating.

**Official Holdout Classification:**
$$\text{HOLDOUT STATUS: VERIFIED WITH QUALIFICATIONS (LOGICALLY ISOLATED / SOFT-SEALED)}$$
