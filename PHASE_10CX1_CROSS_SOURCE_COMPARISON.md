# PHASE 10C.X.1 — CROSS-SOURCE COMPARISON

## 1. VENUE SPECIFICATION & COMPARABILITY MATRIX

| Comparison Dimension | Binance Spot (CryptoDataDownload) | Binance.US Spot (Phase 9 Holdout) |
|:---|:---|:---|
| **Regulatory Jurisdiction** | Global Offshore | United States Domestic |
| **Market Microstructure** | Global Tier-1 Liquidity Pool | Segmented US Liquidity |
| **Historical Coverage** | 762 days (2023-01-01 to 2025-01-31) | 90 days (June – Sept 2026) |
| **Granularity** | 1-minute $\rightarrow$ aggregated 5-minute | Native 5-minute |
| **Trade Frequency (Strategy)** | ~2,500 trades per year | ~274 trades per month |
| **Base Case Net Return** | **-91.53%** | **-8.65%** |
| **Win Rate** | **19.98%** | **26.64%** |
| **Profit Factor** | **0.25** | **0.29** |

---

## 2. CROSS-SOURCE SYNTHESIS

1. **Directional Consistency**: Across both venues (global Binance Spot and domestic Binance.US Spot), the frozen strategy produces **negative net returns under realistic taker fees**.
2. **Friction Impact**: In both datasets, transaction costs (taker fees + slippage) exceed the strategy's gross expectancy.
3. **Venue Independence**: The negative profitability conclusion is not an artifact of Binance.US liquidity or data idiosyncrasies; it replicates across global Binance Spot historical data.
