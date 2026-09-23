# PHASE 9D SCIENTIFIC ERRATUM

**Document ID**: `ERRATUM-P9D-001`  
**Date**: `2026-09-24`  
**Applies To**: `PHASE9D_MICROSTRUCTURE_RESEARCH_REPORT.md`, `phase9d/aggregation.py`  
**Classification**: `RESEARCH-INTEGRITY CORRECTION — METHODOLOGICAL DISCLOSURE`  

---

## 1. Description of Erratum

The document `PHASE9D_MICROSTRUCTURE_RESEARCH_REPORT.md` is titled:
> *"Phase 9D: Market Microstructure & Regime-Conditioned Signal Research — Scientific Research Report on Incremental Predictive Information & Dynamic Execution Costs"*

Section 1 of that report states:
> *"To determine, under strict pre-registered and reproducible conditions, whether real market microstructure information (order-book depth imbalance, bid/ask spread state, and aggressor trade-flow imbalance) contains statistically significant incremental predictive information beyond the causal OHLCV, volatility, and regime features established in Phase 9C."*

### Scientific Fact Established by Forensic Audit

In `phase9d/pipeline.py` and `phase9d/aggregation.py`:
- No raw, historical tick-level trade files were passed to the feature extractor.
- No historical Level-2 (L2) incremental order-book delta streams were passed to the feature extractor.
- When `orderbook_df is None and trades_df is None` (the execution path used in Phase 9D), `MicrostructureAggregator.aggregate_to_candles()` generated synthetic proxies derived deterministically from 5-minute OHLCV candles:
  - Spread was derived from candle high-low range: `np.clip(range_pct * 10000.0 * 0.15, 1.5, 25.0)`
  - Order-book imbalance was approximated from candle body direction: `(c - (h + l) / 2.0) / ((h - l) / 2.0 + 1e-9)`
  - Aggressor trade-flow imbalance ($TFI$) was approximated using a hyperbolic tangent of bar return: `0.5 + 0.5 * np.tanh(ret_bar * 100.0)`
  - Trade count was approximated from candle volume: `np.maximum(1, (v * 10.0).astype(int))`

Therefore, these features must be classified strictly as:

```text
OHLCV-DERIVED PROXIES
```

and NOT:

```text
AUTHENTIC EVENT-LEVEL MICROSTRUCTURE
```

---

## 2. Impact on Empirical Conclusions

1. **Validity of Negative Result**:
   The empirical conclusion of Phase 9D—that the added features provide **no statistically significant incremental predictive information** ($\Delta\text{AUC} = +0.0025, p = 0.690$) and **cannot overcome transaction costs** ($\text{net expectancy} = -35.8\text{ bps}$)—remains scientifically valid for the evaluated models and proxies.
2. **Boundary of Falsification**:
   Because authentic event-level order-book and trade-flow feeds were not evaluated in Phase 9D, the hypothesis that *authentic* tick-level and order-book depth dynamics contain incremental predictive alpha was **untested** in Phase 9D.
3. **Justification for Phase 10**:
   This erratum directly provides the scientific necessity for Research Program 10 (Passive Execution & Queue Dynamics) and Phase 10B (Event-Level Market Data Acquisition), which was initiated specifically to acquire and reconstruct authentic tick trades and L2 depth deltas.

---

## 3. Audit Trail Preservation

In accordance with scientific reproducibility standards:
- `PHASE9D_MICROSTRUCTURE_RESEARCH_REPORT.md` is preserved intact as the historical experimental record of what was executed.
- `phase9d/aggregation.py` is annotated to clearly distinguish the OHLCV-derived proxy path.
- This erratum is formally registered as the authoritative methodological clarification.
