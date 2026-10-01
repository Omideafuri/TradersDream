# PHASE 12: MULTIPLE-TESTING & SELECTION-BIAS FORENSIC AUDIT

**Audit Date:** 2026-10-01  
**Instrument:** XAU/USD (Spot Gold)  
**Strategy ID:** `XAUUSD_FROZEN_SMA50_200_1H`  
**Candidate Hypothesis Space:** $M = 60$ Exploratory Strategies (Phase 11 Track 3)  
**Audit Finding:** `SELECTION BIAS DETECTED — RAW P-VALUE INVALIDATED UNDER FAMILY-WISE ERROR CONTROL`  

---

## 1. Executive Summary

Under Section 19 of the Phase 12 specification, an audit of multiple-comparison risk, data-mining bias, and selection distortion was performed. 

In Phase 11, the research team screened **60 distinct strategy-timeframe combinations** across SMA cross, EMA cross, Bollinger Bands, RSI momentum, and ATR channels on 15m, 1h, and 4h timeframes before designating `XAUUSD_FROZEN_SMA50_200_1H` as the single winning candidate.

Reporting an unadjusted single-hypothesis $p$-value ($p = 0.0228$ or $p = 0.0374$) without adjusting for the 60 candidate trials is a severe methodological violation.

---

## 2. Family-Wise Error Rate (FWER) & FDR Corrections

To account for $M = 60$ exploratory trials, three standard econometric adjustments were computed:

| Adjustment Method | Target $\alpha$ / Formula | Effective Threshold | Adjusted $p$-value ($p_{\text{raw}} = 0.0228$) | Status ($\alpha = 0.05$) |
| :--- | :--- | :--- | :--- | :--- |
| **Unadjusted Raw Test** | $\alpha$ | $0.0500$ | $0.0228$ | Nominally Significant |
| **Bonferroni (FWER)** | $\alpha / M = 0.05 / 60$ | **$0.000833$** | **$1.0000$** | **FAILS SIGNIFICANCE** |
| **Šidák Correction** | $1 - (1 - \alpha)^{1/M}$ | **$0.000854$** | **$0.7468$** | **FAILS SIGNIFICANCE** |
| **Holm-Bonferroni (Step-Down)** | $\alpha / (M - k + 1)$ ($k=1$) | **$0.000833$** | **$1.0000$** | **FAILS SIGNIFICANCE** |
| **Benjamini-Hochberg (FDR $q=0.05$)** | $(k / M) \times q$ | **$0.000833$** | **$0.4560$** | **FAILS SIGNIFICANCE** |

Under every standard multiple-testing framework (Bonferroni, Šidák, Holm, FDR), the raw $p$-value fails to achieve statistical significance.

---

## 3. The Winner's Curse & Selection Bias

1. **Harvey, Liu, & Zhu (2016) Threshold:**
   In financial economics, evaluating multiple strategy candidates requires a $t$-statistic threshold of at least **$t \ge 3.0$** ($p \le 0.0027$) to control for the hundreds of factor variations routinely evaluated in quantitative research. The strategy's $t = 2.029$ falls far short of this institutional threshold.
2. **Data-Mining Drift:**
   Selecting the highest-Sharpe parameter combination ($50/200$) from a grid of 60 models inflates the in-sample performance estimate. If 60 uncorrelated random walks are backtested, the probability that at least one achieves $p \le 0.05$ purely by chance is:
   $$P(\text{False Positive}) = 1 - (1 - 0.05)^{60} = 95.4\%$$
   A positive result was virtually guaranteed to emerge from the 60-model search space even in the total absence of true alpha.

---

## 4. Role of the 2025 Holdout

The only defense against selection bias is performance on an out-of-sample holdout that was never touched during the 60-model exploration phase:
- In the 2025 holdout, the frozen strategy achieved $+32.87\%$ net return across 15 trades with a Profit Factor of $3.836$.
- This out-of-sample survival provides evidence that the strategy was not purely an in-sample curve-fit.
- However, because the candidate search used in-sample training data (2021–2024) where the $50/200$ parameter had already been identified as a standard classical technical indicator, some structural degrees of freedom were consumed.

---

## 5. Audit Conclusion

The Phase 11 claim of statistical significance is **invalidated under family-wise error control**. The strategy survives as an economically viable empirical model primarily due to out-of-sample 2025 holdout performance and parameter-grid stability, NOT because of parametric statistical certainty.
