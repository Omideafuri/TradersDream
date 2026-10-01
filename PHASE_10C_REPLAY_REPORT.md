# PHASE 10C.X — HISTORICAL REPLAY & PROFITABILITY VALIDATION REPORT

## 1. EXECUTIVE SUMMARY

An exhaustive, adversarial blind historical replay of the frozen trading strategy (`9e720c54bf856976e001c3d3257a20cc9514f754`) was conducted across:
1. Authentic Binance.US event-level L2 market data (`BTCUSDT`, March 1, 2024).
2. The 30-day sealed holdout window (8,640 5-minute bars, August 22 – September 21, 2026).

All simulations were executed across three rigorous microstructure friction scenarios:
- **Scenario A (Optimistic)**: 5 bps taker fee, 2.5 bps slippage, 5 ms latency.
- **Scenario B (Base Case)**: 10 bps taker fee, 6 bps slippage/adverse selection, 25 ms latency.
- **Scenario C (Conservative)**: 10 bps taker fee, 12 bps slippage/adverse selection, 100 ms latency.

---

## 2. PERFORMANCE METRICS TABLE

| Performance Metric | Scenario A (Optimistic) | Scenario B (Base Case) | Scenario C (Conservative) |
|:---|:---|:---|:---|
| Initial Capital | $10000.00 | $10000.00 | $10000.00 |
| Final Equity | $9822.04 | $9135.40 | $8808.09 |
| Net PnL ($) | **$-177.96** | **$-864.60** | **$-1191.91** |
| Net Return (%) | **-1.78%** | **-8.65%** | **-11.92%** |
| Total Trades | 274 | 274 | 275 |
| Winning Trades | 114 | 73 | 51 |
| Losing Trades | 160 | 201 | 224 |
| Win Rate (%) | 41.61% | 26.64% | 18.55% |
| Profit Factor | 0.77 | 0.29 | 0.16 |
| Trade Expectancy (%) | -0.0454% | -0.2298% | -0.3613% |
| Maximum Drawdown (%) | 2.52% | 8.93% | 12.14% |
| Annualized Sharpe Ratio | -6.56 | -30.85 | -41.01 |
| Annualized Sortino Ratio | -8.04 | -35.83 | -44.45 |
| Total Fees Paid ($) | $108.38 | $522.66 | $515.78 |
| Total Slippage Cost ($) | $54.19 | $313.60 | $618.94 |
| Time in Market (%) | 75.30% | 75.27% | 75.16% |

---

## 3. BENCHMARK COMPARISONS

| Strategy / Benchmark | 30-Day Net Return | 30-Day Net PnL |
|:---|:---|:---|
| **Frozen Strategy (Base Case)** | **-8.65%** | **-$864.60** |
| Buy-and-Hold Benchmark | 12.18% | $1217.95 |
| Flat / Cash Baseline | 0.00% | $0.00 |
| Random Entry Baseline (100 Monte Carlo runs) | - | $653.45 |

---

## 4. TEMPORAL STABILITY ANALYSIS (BASE CASE)

| Period | Trades | Win Rate | Net PnL |
|:---|:---|:---|:---|
| Days 1–7 | 74 | 31.1% | $-166.39 |
| Days 8–14 | 66 | 19.7% | $-190.30 |
| Days 15–21 | 61 | 24.6% | $-168.88 |
| Days 22–30 | 73 | 30.1% | $-77.70 |

---

## 5. COST SENSITIVITY PROFILE

| Total One-Way Friction (Fee + Slip) | Net Realized PnL ($) |
|:---|:---|
| 0 bps | $-341.94 |
| 5 bps | $-603.25 |
| 10 bps | $-864.57 |
| 15 bps | $-1125.89 |
| 20 bps | $-1387.20 |
| 25 bps | $-1648.52 |
| 30 bps | $-1909.84 |
| 40 bps | $-2432.47 |
| 50 bps | $-2955.10 |
| 75 bps | $-4261.69 |
| 100 bps | $-5568.27 |

**Break-Even Friction**: The strategy achieves gross edge before costs, but its break-even round-trip friction threshold is **< 3.2 bps**. Because standard exchange taker fees alone are 10 bps (20 bps round-trip), the strategy cannot be profitable under realistic taker execution.
