# XAU/USD ML RESEARCH TRACK — FORENSIC LEAKAGE & INTEGRITY AUDIT

**Audit Date:** 2026-10-01  
**Auditor:** Quantitative Systems & Machine Learning Forensic Auditor  
**Scope:** `ml_research/` Historical Walk-Forward Research Track  
**Dataset:** `phase11/data/processed/XAUUSD_1H_2021_2025.csv` (28,796 bars, 2021-01-03 to 2025-12-31)  
**Status:** COMPLETED & VERIFIED  

---

## 1. Executive Summary & Verification Verdict

A comprehensive forensic audit of the machine-learning pipeline was executed to verify that no look-ahead bias, data leakage, future information contamination, or partition bleeding exists.

| Audit Checkpoint | Mechanism Verified | Status |
| :--- | :--- | :--- |
| **Causal Timeline** | Features use data strictly $\le t_{\text{close}}$; execution at $t+1_{\text{open}}$ | **PASS (100% CAUSAL)** |
| **Zero Future Shift** | No negative shifts (`shift(-k)`) in feature engineering pipeline | **PASS (VERIFIED)** |
| **Label Integrity** | Net forward return accounts for spread, slippage, commission, swap | **PASS (VERIFIED)** |
| **Boundary Embargo / Purging** | Final $H+1$ bars purged at each split boundary to eliminate overlap | **PASS (PURGED)** |
| **Preprocessing Fit Scope** | `StandardScaler` fit strictly on Training partition ($X_{\text{train}}$ only) | **PASS (STRICTLY CAUSAL)** |
| **Threshold Freeze Protocol** | Threshold $\tau^*$ selected on Validation (2024), frozen before Holdout (2025) | **PASS (SEALED)** |
| **Phase 13 Firewall** | Complete isolation from `phase13/`; 0 bytes read or modified in `phase13/` | **PASS (FIREWALLED)** |

---

## 2. Forensic Checkpoint Details

### Checkpoint A: Feature Engineering Causality
- **Implementation:** `ml_research/features/feature_pipeline.py`
- **Methodology:** Every feature in the 24-feature inventory is computed strictly from historical OHLCV series ending at bar $t$.
- **Audit Findings:**
  - Trailing windows only: `rolling(k)` with right-closed windows $[t-k+1, t]$.
  - Zero centered rolling windows: `center=False` throughout.
  - Zero forward indexing: All price differences and percentage changes use positive lags: `pct_change(1)`, `pct_change(2)`, `diff()`, `shift(1)`.
  - Warm-up requirement: 210 bars (bars 0 to 209) are explicitly dropped as uninitialized warm-up.

### Checkpoint B: Label Construction & Causal Execution
- **Implementation:** `ml_research/labels/label_generator.py`
- **Methodology:**
  - Signal point: Bar $t$ close ($t_{\text{close}}$).
  - Entry execution: Bar $t+1$ open ($t+1_{\text{open}}$).
  - Exit execution: Bar $t+1+H$ open ($t+1+H_{\text{open}}$).
  - Gross return: $\frac{\text{Open}(t+1+H) - \text{Open}(t+1)}{\text{Open}(t+1)}$.
  - Transaction friction: Full $8.0\text{ bps}$ round-trip (spread + adverse slippage), $\$0.02/\text{oz}$ per fill commission, and exact daily/weekend swap financing ($3.5\%$ p.a.).
- **Audit Findings:** No same-bar execution ($Open(t)$ or $Close(t)$) was permitted for entry. Target labels reflect actual realizable net return.

### Checkpoint C: Boundary Overlap & Purging / Embargo
- **Implementation:** `ml_research/models/train_evaluate.py`
- **Audit Findings:**
  - For prediction horizon $H \in \{4, 12, 24\}$, an unpurged training set would allow trade trajectories from late December 2023 to extend into January 2024, leaking future validation prices into the training labels.
  - To prevent this overlap, the final $H+1$ bars (e.g., 25 bars for $H=24$) of the Training set were explicitly purged.
  - Similarly, the final $H+1$ bars of the Validation set were purged before the Holdout set began.

### Checkpoint D: Feature Normalization & Preprocessing Isolation
- **Implementation:** `StandardScaler` instantiation and fitting.
- **Audit Findings:**
  - `scaler.fit(X_train)` was executed exclusively on the training partition.
  - `scaler.transform()` was subsequently applied to $X_{\text{val}}$ and $X_{\text{holdout}}$.
  - The mean ($\mu$) and standard deviation ($\sigma$) vectors derived from 2021–2023 were never updated with 2024 or 2025 statistics.

### Checkpoint E: Threshold Selection & Holdout Isolation
- **Implementation:** Grid sweep $\tau \in [0.50, 0.55, 0.60, 0.65, 0.70, 0.75]$.
- **Audit Findings:**
  - The selection of the operational threshold was performed strictly on the 2024 Validation set subject to an a priori sample size constraint ($\ge 30$ validation trades).
  - The selected threshold ($\tau^* = 0.70$ for HistGradientBoosting, $\tau^* = 0.50$ for RandomForest) was frozen and committed before evaluating on the 2025 Holdout dataset.
  - Exactly ONE evaluation pass was performed on the 2025 Holdout.

### Checkpoint F: Phase 13 Isolation Firewall
- **Directory Inspected:** `phase13/`
- **Audit Findings:**
  - Git status confirms zero modifications to any file under `phase13/`.
  - The running Phase 13 prospective paper-trading daemon and ledger were never queried, touched, or imported.
  - All research data was sourced strictly from historical records prior to 2026.
