# PHASE 12 — DATA-SNOOPING & HOLDOUT INTEGRITY AUDIT

**Project:** Autonomous Quantitative Research & Market Microstructure Verification  
**Phase:** Phase 12 — XAU/USD Real-Market Execution Validation  
**Instrument:** `XAU/USD` (Physical Spot Gold / US Dollar)  
**Auditor:** Quantitative Forensics & Data-Snooping Integrity Group  
**Classification:** **`HOLDOUT INTEGRITY: PARTIALLY VERIFIED (LOGICALLY ISOLATED / COMMINGLED STORAGE)`**  

---

## 1. Audit Scope & Objective

To verify whether the final 20% holdout dataset (`2025-01-01` to `2025-12-31`) was genuinely untouched prior to strategy freezing, this audit inspects file creation timestamps, git history, and data-flow pipelines.

---

## 2. Chronological Timeline of Phase 11 Artifacts

1. **Raw Data Ingestion:**
   - Raw files for all 5 calendar years (`2021`, `2022`, `2023`, `2024`, `2025`) were downloaded simultaneously at the start of Phase 11 by `phase11/data/downloader.py`.
   - Both the training data and holdout data were placed in the local directory `phase11/data/raw/` at the same time.
2. **Resampling & Storage:**
   - `phase11/data/processor.py` processed all 5 years into `phase11/data/processed/XAUUSD_1H_2021_2025.csv` simultaneously.
3. **Exploration & Strategy Selection:**
   - In `phase11/research/run_research.py`, the strategy grid was explicitly sliced using:
     ```python
     dev_mask = df["dt_utc"] < "2024-01-01"
     val_mask = (df["dt_utc"] >= "2024-01-01") & (df["dt_utc"] < "2025-01-01")
     ```
   - Only `splits["dev"]` and `splits["val"]` were passed to the strategy search grid.
   - The holdout partition (`df["dt_utc"] >= "2025-01-01"`) was NOT evaluated in the 60-run strategy discovery grid.
4. **Strategy Freeze:**
   - The parameter freeze document `PHASE11_STRATEGY_FREEZE.md` was authored before `run_evaluations.py` was executed.
5. **Final Holdout Execution:**
   - `run_evaluations.py` executed the holdout partition once.

---

## 3. Adversarial Assessment of Potential Contamination

* **Logical Isolation (PASS):** In the codebase, the 2025 holdout bars were logically segmented and excluded from the optimization grid. Zero indicator parameters were tuned against 2025.
* **Physical Isolation (CAUTION):** Because all 5 years were downloaded and stored in the same repository from Day 1, the dataset was not physically segregated in a separate, encrypted air-gapped vault.
* **Macro Knowledge Contamination (CAUTION):** Any quantitative researcher operating in 2026 possesses general macroeconomic knowledge that Gold had a massive rally in 2024 and 2025 (surpassing $2,700 and $4,000). Selecting a "trend following" strategy is naturally informed by the known secular macro bull run in gold.

---

## 4. Formal Integrity Verdict

The holdout was **logically unpeaked in code**, but **cannot be certified as an air-gapped blind trial**.

Therefore, the holdout integrity is officially classified:
```text
HOLDOUT INTEGRITY: PARTIALLY VERIFIED (LOGICALLY ISOLATED / COMMINGLED STORAGE)
```
This is a standard limitation of retrospective backtesting. The only mechanism that guarantees 100% true out-of-sample validity is **forward prospective paper capture**, which has been initiated in Phase 12.
