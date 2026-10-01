# PHASE 12: RETURN & RISK-ADJUSTED METRIC AUDIT

**Audit Date:** 2026-10-01  
**Instrument:** XAU/USD (Spot Gold)  
**Strategy ID:** `XAUUSD_FROZEN_SMA50_200_1H`  
**Execution Standard:** Next-Bar-Open, 6.0 bps Round-Trip Friction  
**Audit Finding:** `VERIFIED — ASYMMETRIC TREND-FOLLOWING DISTRIBUTION`  

---

## 1. Executive Summary

Under Section 17 of the Phase 12 specification, all return metrics, compounding curves, and risk-adjusted ratios were independently reconstructed from the raw trade ledger. Mathematical formulas and temporal aggregation methods were audited to eliminate discrepancies caused by mixing trade-level, hourly, or daily return frequencies.

Key Metrics (2021-01-03 to 2025-12-31):
- **Starting Capital:** $10,000.00
- **Final Ending Capital:** $18,134.88
- **Cumulative Net Return:** +81.35%
- **Compound Annual Growth Rate (CAGR):** 12.64%
- **Annualized Sharpe Ratio (Trade-Level):** 0.907
- **Annualized Sortino Ratio (Trade-Level):** 2.040
- **Maximum Drawdown:** 9.39% (equity-curve closed trades) / 15.46% (hourly mark-to-market)
- **Calmar Ratio (Hourly MTM Max DD):** $12.64\% / 15.46\% = 0.818$

---

## 2. Annual Performance Breakdown

| Calendar Year | Trade Count | Win Rate | Net Realized P&L | Year-End Equity | Annual Return | Cumulative Return |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **2021** | 19 | 42.1% | +$115.17 | $10,115.17 | +1.15% | +1.15% |
| **2022** | 17 | 41.2% | +$208.94 | $10,324.11 | +2.07% | +3.24% |
| **2023** | 14 | 35.7% | +$1,513.16 | $11,837.27 | +14.66% | +18.37% |
| **2024** | 19 | 47.4% | +$1,810.82 | $13,648.09 | +15.30% | +36.48% |
| **2025 (Holdout)** | 15 | 46.7% | +$4,486.79 | $18,134.88 | +32.87% | +81.35% |
| **Full Sample (5 Yrs)** | **84** | **42.9%** | **+$8,134.88** | **$18,134.88** | **12.64% (CAGR)** | **+81.35%** |

### Critical Observation on Temporal Concentration
Performance is heavily back-loaded:
- **2021–2022 (Consolidation Regime):** Over the first two years (36 trades), total net P&L was only $+\$324.11$ ($+3.24\%$).
- **2023–2025 (Macro Gold Expansion):** Over the subsequent three years (48 trades), total net P&L surged by $+\$7,810.77$, with 2025 alone generating **55.2%** of all cumulative net profits ($+\$4,486.79$).

---

## 3. Mathematical Metric Definitions & Methodology

### Compound Annual Growth Rate (CAGR)
$$\text{CAGR} = \left( \frac{\text{Ending Equity}}{\text{Starting Equity}} \right)^{\frac{1}{T}} - 1 = \left( \frac{18,134.88}{10,000.00} \right)^{\frac{1}{5.0}} - 1 = 12.64\%$$

### Annualized Trade-Level Sharpe Ratio
Let $r_i$ be the net percentage return of trade $i$ ($i = 1 \dots N$, where $N = 84$).
$$\bar{r} = \frac{1}{N} \sum_{i=1}^N r_i = 0.767\%$$
$$s_r = \sqrt{\frac{1}{N-1} \sum_{i=1}^N (r_i - \bar{r})^2} = 3.462\%$$
With an average trading frequency of $K = N / 5.0 = 16.8\text{ trades/year}$:
$$\text{Sharpe}_{\text{trade}} = \frac{\bar{r}}{s_r} \times \sqrt{K} = \frac{0.00767}{0.03462} \times \sqrt{16.8} = 0.907$$

### Annualized Trade-Level Sortino Ratio
Let $d_i = \min(r_i, 0)$ be the negative trade returns:
$$\sigma_d = \sqrt{\frac{1}{N} \sum_{i=1}^N d_i^2} = 1.543\%$$
$$\text{Sortino}_{\text{trade}} = \frac{\bar{r}}{\sigma_d} \times \sqrt{K} = \frac{0.00767}{0.01543} \times \sqrt{16.8} = 2.040$$

The Sortino ratio (2.040) is substantially higher than the Sharpe ratio (0.907) because the strategy's return distribution exhibits positive skewness ($+3.64$), penalizing traditional two-sided volatility models while reflecting limited downside volatility.
