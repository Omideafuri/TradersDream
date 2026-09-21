# PHASE 9B PROVENANCE & INDEPENDENCE REPORT
**Date**: `2026-09-21T22:41:26.281589+00:00`  
**Registry**: `phase9/manifests/dataset_registry.json`  
**Status**: **`VERIFIED INDEPENDENT`**  

---

## 1. Registered Datasets
| Dataset ID | Asset | Rows | Source | SHA256 Hash | Synthetic Status | Independence Status |
| :--- | :---: | :---: | :--- | :--- | :---: | :---: |
| `HIST_BINANCE_US_BTCUSDT_5M_2026_V1` | **BTC** | 26,000 | Binance.US v3 | `f72be9be809e599481909d12126f47c6569faaa85717a3dc9109c4800250b515` | `GENUINE` | `INDEPENDENT` |
| `HIST_BINANCE_US_ETHUSDT_5M_2026_V1` | **ETH** | 26,000 | Binance.US v3 | `f5de00e066017bfaefbaa6ada2bd97ff0cb460366651d0076c918c6e6d5e51eb` | `GENUINE` | `INDEPENDENT` |
| `HIST_BINANCE_US_SOLUSDT_5M_2026_V1` | **SOL** | 26,000 | Binance.US v3 | `7a128e5aafb7f5b81ff8c01c8b7fd906459a2b455be9354714e858f8e6672f9d` | `GENUINE` | `INDEPENDENT` |

## 2. Cross-Asset Independence Matrix
| Asset Pair | Overlapping Bars | Pearson Return r | Spearman Return r | Price Ratio Std | Synthetic Scaling Detected | Verdict |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **BTC_ETH** | 26,000 | 0.7491 | 0.6339 | 0.0591 | False | **`INDEPENDENT`** |
| **BTC_SOL** | 25,999 | 0.6671 | 0.5443 | 0.0557 | False | **`INDEPENDENT`** |
| **ETH_SOL** | 25,999 | 0.6846 | 0.5518 | 0.0547 | False | **`INDEPENDENT`** |

## 3. Resolution of DISC-001
- **Historical Synthetic Data**: Preserved in `data/historical/` and marked as `SYNTHETIC / NON_INDEPENDENT` in the registry.
- **Phase 9 Independent Data**: The newly acquired datasets for BTC, ETH, and SOL exhibit genuine market price drift (price ratio std > 0.05, Pearson return r between 0.60 and 0.85). They originate from separate live market trades and are confirmed mathematically independent.
