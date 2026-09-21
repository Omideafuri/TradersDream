# RESEARCH FREEZE MANIFEST
**System**: Jev Crypto-Trading Research System (Phases 1–8)  
**Status**: **FROZEN & FORMALLY CLOSED**  
**Final Master Classification**: **`NOT_SUPPORTED`**  
**Freeze Timestamp**: `2026-09-21T16:15:00Z`  
**Head Git Commit**: `095b809` (Phase 7 verification head)

---

## 1. Executive Freeze Statement
The exploratory and empirical research program evaluating the predictive and economic viability of Jev-assisted cryptocurrency trading on sub-daily candle resolutions ($5\text{m}, 15\text{m}, 30\text{m}, 1\text{h}, 4\text{h}$) is **permanently closed and frozen**.

**Core Finding**:
Across 8 rigorous phases of paper trading, backtesting, statistical validation, signal diagnosis, upstream reconstruction, multi-asset evaluation, temporal reassessment, and independent verification:
- No statistically defensible out-of-sample directional edge was established ($\text{Accuracy} \approx 45.8\% - 53.6\%$, indistinguishable from random coin flips).
- Transaction friction (30 bps round-trip taker fees and slippage) systematically exceeds raw signal amplitude across all assets and horizons.
- The sealed holdout partitions have been evaluated; no further model selection, threshold sweeps, or parameter tuning may use these historical datasets.

---

## 2. Environment & Dependency Lock
- **Python Runtime**: `Python 3.12.13`
- **Operating System**: Windows (AMD64)
- **Dependency Specifier**: `requirements.txt`
  - `httpx==0.28.1`
  - `pandas==2.2.3`
  - `numpy==2.2.3`
  - `python-dotenv==1.0.1`
  - `pytest==9.1.1`
  - `pytest-asyncio==1.4.0`
- **Execution Command**:
  ```powershell
  .venv\Scripts\python -m phase8.run
  ```

---

## 3. Dataset Integrity & Checksums
Base 5-minute historical datasets preserved in `data/historical/`:
| Asset | File | Rows | Start UTC | End UTC | SHA256 Checksum |
| :--- | :--- | :---: | :---: | :---: | :--- |
| `BTCUSDT` | `BTCUSDT_5m_candles.csv` | 1,500 | 2024-01-01T00:00:00 | 2024-01-06T04:55:00 | `3bbdfd6c25b607ee72fbf409e51dd2eb5845f8cb6eb7f2d4e73b22cfdc820a40` |
| `ETHUSDT` | `ETHUSDT_5m_candles.csv` | 1,500 | 2024-01-01T00:00:00 | 2024-01-06T04:55:00 | `9639e8a030ae16b8ef6c3b6924e29cb1f57ce355aa13bcf3d46bf365bca50df6` |
| `SOLUSDT` | `SOLUSDT_5m_candles.csv` | 1,500 | 2024-01-01T00:00:00 | 2024-01-06T04:55:00 | `9dcd24fbdb5a28525bcf7a6e1335cb8c75ecf23f81e35492d549887711910cf9` |

---

## 4. Sealed Holdout Cryptographic Fingerprints
The final 20% chronological holdout partitions (bars 1,200–1,499) remain frozen with immutable fingerprints:
- **BTCUSDT Holdout SHA256**: `143f295b95cb2e1ca6db69b8aeef7f53fdfd4107dc6d73f15c7e3f8ff3ec6aa8`
- **ETHUSDT Holdout SHA256**: `df0a8bc0ef0e54d1945f3efb24d77053e198aa7d9760228aa9c450c920f4c0eb`
- **SOLUSDT Holdout SHA256**: `444f6f8ec4c01d9f041ff91a5e12817ee83bb17b6291a2eb318c94eb972986fa`

---

## 5. Frozen Jev Architecture Configuration
- **Decision Engine**: `JevApiProvider` (Frozen Phase 5/6 System One API)
- **Prompt Specification**: `v5.0-structured-choice-abstention`
- **Feature Specification**: `v5.0-causal-market-structure`
- **Regime Engine**: `v5.0-6class-causal`
- **Uncertainty Model**: `v5.0-indicator-contradiction`
- **Abstention Gate**: `v5.0-explicit-no-edge-threshold-0.50`
- **Cost Hurdle Model**: 10 bps fee + 5 bps slippage per fill = 30 bps round-trip friction + 10 bps margin = 40 bps economic hurdle
- **Configuration SHA256 Hash**: `373e855b8ddc70e69f4076289987786d0b95a88ae6aa2bd147d1d69ef61fedf7`

---

## 6. Complete Artifact Integrity Chain
All historical research artifacts persist in `data/`:
- `data/historical/`: Canonical datasets and decision archives
- `data/backtest_results/`: Phase 2 engine replay outputs
- `data/validation_results/`: Phase 3 statistical robustness artifacts
- `data/phase4_results/`: Phase 4 signal diagnosis and MFE/MAE excursions
- `data/phase5_results/`: Phase 5 upstream reconstruction and information gain
- `data/phase6_results/`: Phase 6 cross-asset generalization and Benjamini-Hochberg FDR
- `data/phase7_results/`: Phase 7 multi-horizon temporal resolution study
- `data/phase8_results/`: Phase 8 final verification audit, reproducibility state, and discrepancies

---

## 7. Test Suite Status
- Total Passing Tests: **118 / 118 PASSING**
- Regressions: **0**
- Test Framework: `pytest -v`

---

## 8. Final Multi-Dimensional Classification
```text
PREDICTIVE_INFORMATION: NOT_SUPPORTED
STATISTICAL_EVIDENCE:   NOT_SUPPORTED
ECONOMIC_VIABILITY:     NOT_SUPPORTED
DEPLOYMENT_READINESS:   NOT_SUPPORTED

MASTER_CLASSIFICATION:  NOT_SUPPORTED
```

---

## 9. Conditions Required to Reopen Research
The current hypothesis ($H0$–$H7$) has failed. Any future investigation into AI-assisted crypto trading must initiate as an entirely new project under the following mandatory constraints:
1. **Multi-Month Real Datasets**: Independent, high-liquidity tick and volume feeds from primary exchanges (retiring the current synthetic benchmark series).
2. **Fresh Temporal Partitions**: Complete replacement of the train/validation/holdout split.
3. **Low-Turnover Architecture**: Higher temporal horizons (daily or multi-day swing holding) designed to mitigate exchange fee drag.
4. **Passive Order Execution**: Maker-only limit order models to eliminate taker execution friction.

**Live trading remains strictly prohibited.**
