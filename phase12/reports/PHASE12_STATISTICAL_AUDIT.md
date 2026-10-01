# PHASE 12: STATISTICAL SIGNIFICANCE REASSESSMENT AUDIT

**Audit Date:** 2026-10-01  
**Instrument:** XAU/USD (Spot Gold)  
**Strategy ID:** `XAUUSD_FROZEN_SMA50_200_1H`  
**Sample Size:** $N = 84$ trades (January 2021 – December 2025)  
**Statistical Finding:** `WEAK NOMINAL SIGNIFICANCE — UNRELIABLE UNDER SELECTION ADJUSTMENT`  

---

## 1. Executive Summary

Under Section 18 of the Phase 12 specification, the statistical significance claims made in Phase 11 ($N = 84$, $t = 2.022$, $p = 0.0232$) were independently audited, recomputed, and stress-tested using both parametric and non-parametric resampling methods.

Key Findings:
1. **Parametric Reproduction:** Trade-level mean return is $\bar{r} = +0.767\%$ with standard deviation $s = 3.462\%$. The independent Student $t$-statistic is $t = 2.0292$, yielding a one-tailed $p$-value of $p = 0.0228$ (two-tailed $p = 0.0456$), confirming Phase 11's uncorrected calculations.
2. **Bootstrap 95% Confidence Interval:** Over 10,000 bootstrap resamples, the 95% CI for the mean trade return is $[+0.091\%, +1.575\%]$. Because the lower bound is slightly above zero, nominal positive expectancy is supported under standard IID resampling.
3. **Permutation Test:** A 10,000-iteration sign-permutation test yields an empirical $p$-value of $p = 0.0374$.
4. **Methodological Defect in IID Assumption:** Treating trade returns as independent observations is fundamentally flawed in trend-following strategies due to volatility clustering, regime persistence, and market beta exposure.
5. **Multiple Testing Vulnerability:** When adjusted for the 60 candidate models tested in Phase 11, the significance disappears entirely ($p_{\text{adj}} = 1.0000$).

---

## 2. Statistical Metrics Comparison

| Test / Metric | Phase 11 Claim | Phase 12 Independent Audit | Verdict |
| :--- | :--- | :--- | :--- |
| **Trade Count ($N$)** | 84 | 84 | Exact Match |
| **Mean Trade Return ($\bar{r}$)** | +0.76% | +0.767% | Exact Match |
| **Sample Std Dev ($s$)** | 3.46% | 3.462% | Exact Match |
| **Standard Error ($\text{SE}$)** | 0.377% | 0.3778% | Exact Match |
| **Student $t$-Statistic** | 2.022 | 2.0292 | Verified ($\Delta = 0.007$) |
| **Parametric $p$-value (1-tailed)** | 0.0232 | 0.0228 | Verified Nominal Significance |
| **Bootstrap 95% CI (10,000 runs)** | Not Reported | [+0.091%, +1.575%] | Strictly Positive Lower Bound |
| **Permutation $p$-value (10,000 runs)** | Not Reported | 0.0374 | Rejects Null at $\alpha=0.05$ |
| **Bonferroni Adjusted $p$-value ($M=60$)** | Omitted | **1.0000** | **NOT SIGNIFICANT** |

---

## 3. Methodological Violations in Naive $t$-Testing

Calling this strategy "statistically proven" based on a raw $p = 0.0232$ violates core quantitative principles:

1. **Trade Returns Are Not Independent (Non-IID):**
   - Trades cluster during specific macro volatility regimes (e.g. 2024–2025 geopolitical escalation).
   - In 2021–2022, 36 trades produced a cumulative net return of only $+3.24\%$ ($\bar{r} = +0.09\%$, $t = 0.28$, $p = 0.39$ — completely indistinguishable from random noise).
2. **Positive Skewness Distorts Normal Approximations:**
   - The trade return distribution has a skewness of $+3.64$ and kurtosis of $+18.2$.
   - The median trade return is negative ($-0.16\%$, $-\$29.31$). A classical Student $t$-test assumes normality and is highly sensitive to right-tail outliers.
3. **Extreme Trade Concentration:**
   - The top 8 trades (9.5% of sample) account for $117.7\%$ of cumulative net profits.
   - Dropping the top 5 trades reduces net return from $+81.35\%$ to $+12.40\%$, dropping the $t$-statistic to $0.48$ ($p = 0.32$).

---

## 4. Conclusion

While the strategy exhibits positive historical performance, **it is NOT statistically proven**. Its apparent significance ($p \approx 0.023$) is a naive artifact that fails to survive multiple-testing correction and relies on a tiny subset of large outlier trend events.
