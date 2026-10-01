# FUTURE RESEARCH IDEAS (POST PHASE 10C.X.1)

**Status**: RESEARCH IDEAS FOR FUTURE AUDITED PHASES ONLY  
**Rule**: STRICTLY PROHIBITED FROM IMPLEMENTATION IN PHASE 10C.X OR 10C.X.1.

---

## 1. Passive Market Making & Maker Fee Architecture (Phase 10D)
- **Problem**: Retail taker orders (10 bps/side = 20 bps round-trip) exceed the strategy's gross expectancy across all multi-year historical regimes.
- **Hypothesis**: Replacing taker market orders with passive post-only limit orders earns maker fee rebates (-1 bps to 0 bps on VIP tiers) and captures the half-spread instead of crossing it.
- **Requirement**: Requires authentic Level-2 order-book queue simulation (currently being captured by the active Phase 10C.2 background collector).

## 2. Dynamic Volatility-Scaled Holding Period
- **Problem**: Fixed 24-bar (2-hour) holding period forces liquidation during consolidation or slow overnight regimes.
- **Hypothesis**: Scaling holding period inversely with ATR or realized volatility allows positions sufficient time to reach targets in low-volatility markets.

## 3. High-Timeframe Trend Co-Integration
- **Problem**: 5-minute moving average crossovers generate frequent false breakouts in multi-day range-bound regimes.
- **Hypothesis**: Requiring alignment with 1-hour or 4-hour regime filters (e.g. 4h 200 EMA) eliminates high-frequency churn during macro consolidation.
