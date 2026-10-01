# PHASE 10C.X.1 — FEATURE LINEAGE & L2 ABSENCE SPECIFICATION

## 1. END-TO-END FEATURE LINEAGE

| Feature | Raw Source Field | Mathematical Transformation | Lookback Window | Decision Role |
|:---|:---|:---|:---|:---|
| Fast Trend | `close` | $\text{EMA}(20) = \alpha \cdot P_t + (1-\alpha) \cdot \text{EMA}_{t-1}$ | 20 bars (100 min) | Trend direction confirmation |
| Medium Trend | `close` | $\text{EMA}(50)$ | 50 bars (250 min) | Medium trend regime filter |
| Slow Baseline | `close` | $\text{EMA}(200)$ | 200 bars (1,000 min) | Long-term regime filter |
| Momentum (RSI) | `close` | $100 - \frac{100}{1 + \text{RS}}$, $\alpha = 1/14$ | 14 bars (70 min) | Overbought/oversold exclusion ($30 < \text{RSI} < 70$) |
| Volume Ratio | `volume` | $\frac{\text{volume}_t}{\frac{1}{20} \sum_{i=0}^{19} \text{volume}_{t-i}}$ | 20 bars (100 min) | Flow breakout filter ($> 1.05$) |

---

## 2. L2 ORDER-BOOK FEATURE ABSENCE & FALLBACK PROTOCOL

1. **Authentic L2 Non-Availability in OHLCV**:
   - The CryptoDataDownload dataset contains OHLCV candlestick records. It does **NOT** contain tick-by-tick order-book deltas, market depth ladders, or individual trade aggressor sides.
2. **Strict Invariant — No Synthetic L2**:
   - In accordance with Section 14, **no synthetic order-book depth, fake bid/ask queues, or fabricated spread levels were manufactured**.
3. **Execution Fallback**:
   - In the Phase 10C.X macro backtesting architecture, the volume breakout confirmation filter (`vol_ratio > 1.05`) serves as the documented volume-flow gate on historical OHLCV data.
   - When running on authentic L2 streams (as in Phase 10C.X Section 6 and the active Phase 10C.2 capture), the microstructural order book imbalance and tick aggressor flow are computed from the reconstructed book.
   - This experiment tests the **macro OHLCV component of the frozen strategy** and does **NOT** constitute an L2 order-book test.
