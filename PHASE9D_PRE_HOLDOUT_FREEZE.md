# PHASE 9D PRE-HOLDOUT RESEARCH FREEZE
**Freeze Timestamp**: `2026-09-21T23:22:02.638084+00:00`  
**Status**: **`FROZEN & IMMUTABLE`**  
**Git Commit Reference**: `f652082`  

---

## 1. Safety & Architecture Invariants
- `PAPER_TRADING_ONLY = true`
- `USE_LIVE_JEV = false`
- `LEVERAGE = 1.0`
- `RESEARCH_FREEZE.md` untouched

## 2. Dataset Hashes (Binance.US)
- **BTCUSDT**: `f72be9be809e599481909d12126f47c6569faaa85717a3dc9109c4800250b515`
- **ETHUSDT**: `f5de00e066017bfaefbaa6ada2bd97ff0cb460366651d0076c918c6e6d5e51eb`
- **SOLUSDT**: `7a128e5aafb7f5b81ff8c01c8b7fd906459a2b455be9354714e858f8e6672f9d`

## 3. Pre-Registered Hypotheses Frozen
- **P9D-H01**: Order-Book Depth Imbalance (Short-horizon bid/ask depth imbalance contains directional predictive information about subsequent returns after controlling for Phase 9C regime and volatility.)
- **P9D-H02**: Spread State and Adverse Price Drift (Relative bid/ask spread predicts subsequent adverse price movement, volatility expansion, and execution cost deterioration.)
- **P9D-H03**: Trade-Flow Imbalance Persistence (Aggressor-side trade volume imbalance contains incremental directional information about subsequent returns beyond OHLCV volume proxies.)
- **P9D-H04**: Microstructure x Regime Interaction (Microstructure order-book and trade-flow imbalance become significantly more informative under high-volatility and trending regime states.)
- **P9D-H05**: Microstructure Incremental Information Content (Combining microstructure variables with Phase 9C causal features produces statistically significant incremental accuracy and net expectancy over Phase 9C features alone (Model B vs Baseline A).)

## 4. Development & Validation Completion
- Total features frozen: **80**
- Validation experiments recorded: **1**
- Model specifications frozen: Regularized Ridge / Linear Diagnostic Classifiers with L2 penalty
- Economic hurdle frozen: 40.0 bps static + dynamic microstructure fee/spread/slippage hurdle

---
### Authorization
All 10 pre-conditions satisfied. The sealed holdout is authorized for a single, one-pass final out-of-sample evaluation.
