# XAU/USD ML RESEARCH TRACK — FEATURE SPECIFICATION

**Document Version:** 1.0.0  
**Research Track:** `ml_research/` (Strictly Isolated from `phase13/`)  
**Target Instrument:** `XAU/USD` (Spot Gold / US Dollar)  
**Primary Timeline:** Completed 1-Hour Bars ($1H$)  

---

## 1. Causal Timeline & Information Availability

Every feature $X_t$ evaluated at bar $t$ is computed strictly using market observations available at or before the Close of bar $t$ ($t_{\text{close}}$). 

```text
Completed 1H Bar t (Close t)
        ↓
Causal Features Computed strictly from [t_0, t]
        ↓
ML Prediction Generated at Close t
        ↓
Execution occurs at Bar t+1 Open (t+1 Open)
        ↓
Holding period to Bar t+1+H Open (t+1+H Open)
```

No future data, no centered windows, and no data from bar $t+1$ or beyond enters feature calculation.

---

## 2. Feature Inventory & Formulations

The feature set is compact, mathematically tractable, and interpretable (total: 24 features).

### A. Price / Return Features (6 features)
1. `ret_1h`: 1-hour percentage return $\frac{C_t - C_{t-1}}{C_{t-1}}$
2. `ret_2h`: 2-hour percentage return $\frac{C_t - C_{t-2}}{C_{t-2}}$
3. `ret_4h`: 4-hour percentage return $\frac{C_t - C_{t-4}}{C_{t-4}}$
4. `ret_8h`: 8-hour percentage return $\frac{C_t - C_{t-8}}{C_{t-8}}$
5. `ret_12h`: 12-hour percentage return $\frac{C_t - C_{t-12}}{C_{t-12}}$
6. `ret_24h`: 24-hour percentage return $\frac{C_t - C_{t-24}}{C_{t-24}}$

### B. Trend & Moving Average Features (7 features)
7. `dist_sma50`: Normalized distance from 50-hour SMA: $\frac{C_t - \text{SMA}_{50}(t)}{\text{SMA}_{50}(t)}$
8. `dist_sma200`: Normalized distance from 200-hour SMA: $\frac{C_t - \text{SMA}_{200}(t)}{\text{SMA}_{200}(t)}$
9. `sma50_diff_sma200`: Spread between fast and slow SMAs: $\frac{\text{SMA}_{50}(t) - \text{SMA}_{200}(t)}{C_t}$
10. `sma50_ratio_sma200`: Ratio of fast to slow SMA minus 1: $\frac{\text{SMA}_{50}(t)}{\text{SMA}_{200}(t)} - 1.0$
11. `sma50_slope`: 5-hour trajectory of fast SMA: $\frac{\text{SMA}_{50}(t) - \text{SMA}_{50}(t-5)}{5 \times C_t}$
12. `sma200_slope`: 10-hour trajectory of slow SMA: $\frac{\text{SMA}_{200}(t) - \text{SMA}_{200}(t-10)}{10 \times C_t}$
13. `sma_trend_regime`: Binary indicator of the frozen strategy condition ($1.0$ if $\text{SMA}_{50}(t) > \text{SMA}_{200}(t)$, else $0.0$).

### C. Volatility Features (5 features)
14. `atr14_norm`: Standard 14-period Average True Range normalized by close price: $\frac{\text{ATR}_{14}(t)}{C_t}$
15. `volatility_24h`: Rolling 24-hour sample standard deviation of 1-hour returns.
16. `range_1h`: Normalized bar range: $\frac{H_t - L_t}{C_t}$
17. `range_4h`: Normalized 4-hour high-low range: $\frac{\max_{i=0..3} H_{t-i} - \min_{i=0..3} L_{t-i}}{C_t}$
18. `range_24h`: Normalized 24-hour high-low range: $\frac{\max_{i=0..23} H_{t-i} - \min_{i=0..23} L_{t-i}}{C_t}$

### D. Momentum & Breakout Features (2 features)
19. `rsi14`: Standard 14-period Relative Strength Index normalized to $[0, 1]$: $\frac{\text{RSI}_{14}(t)}{100.0}$
20. `breakout_dist_24h`: Position within the 24-hour channel: $\frac{C_t - \min_{i=0..23} L_{t-i}}{\max_{i=0..23} H_{t-i} - \min_{i=0..23} L_{t-i} + \epsilon}$

### E. Market Structure / Volume Features (2 features)
21. `vol_ratio_24h`: Relative volume vs 24-hour moving average: $\frac{V_t}{\frac{1}{24}\sum_{i=0}^{23} V_{t-i} + \epsilon}$
22. `vol_change_1h`: Rate of volume change: $\frac{V_t - V_{t-1}}{V_{t-1} + \epsilon}$

### F. Cyclical Time Context (2 features)
23. `hour_sin`: $\sin\left(\frac{2\pi \cdot \text{hour}_t}{24}\right)$
24. `hour_cos`: $\cos\left(\frac{2\pi \cdot \text{hour}_t}{24}\right)$

---

## 3. Data Leakage Invariants

1. All rolling statistics use `closed='left'` or explicit trailing slices $[t-K, t]$.
2. Zero `shift(-k)` operations are permitted in feature code.
3. Preprocessing (StandardScaler) is fit strictly on the training partition and applied without refitting to validation/test partitions.
