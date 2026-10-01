# PHASE 10C.X — STRATEGY FREEZE MANIFEST

**Freeze Status**: ACTIVE & IMMUTABLE  
**Git Commit Hash**: `9e720c54bf856976e001c3d3257a20cc9514f754`  
**Symbol**: `BTCUSDT`  
**Venue**: `binance-us`  
**Execution Mode**: RESEARCH REPLAY (PAPER TRADING ONLY)  
**Safety Invariants**:
- `PAPER_TRADING_ONLY`: `True`
- `USE_LIVE_JEV`: `False`
- `LEVERAGE`: `1.0`
- `LIVE_ORDERS`: `0`
- `WALLET_CONNECTIONS`: `0`
- `PRIVATE_KEYS`: `0`

---

## 1. STRATEGY SPECIFICATION & PARAMETERS

| Parameter | Frozen Value | Description |
|:---|:---|:---|
| Initial Balance | $10,000.00 | Account starting cash |
| Max Position Size | 10.0% (0.10) | Maximum portfolio allocation per trade |
| Max Open Positions | 1 | Strictly single concurrent position |
| Stop Loss | 1.5% (0.015) | Fixed distance from fill price |
| Take Profit | 3.0% (0.030) | Fixed distance from fill price |
| Max Holding Period | 48 bars (4.0 hrs) | Time-based position liquidation |
| Indicator 1 | EMA(20) | Fast exponential moving average |
| Indicator 2 | EMA(50) | Medium exponential moving average |
| Indicator 3 | EMA(200) | Long-term trend filter |
| Indicator 4 | RSI(14) | Momentum oscillator |
| RSI Long Cutoff | < 70.0 | Long entry ceiling (not overbought) |
| RSI Short Cutoff | > 30.0 | Short entry floor (not oversold) |
| Volume Ratio Cutoff | > 1.05 | Current bar volume vs 20-period moving average |
| Microstructure Imbalance | Top-10 Depth & Trade Flow | Imbalance threshold ±0.10 |

---

## 2. EXECUTION SCENARIOS UNDER AUDIT

| Parameter | Scenario A (Optimistic) | Scenario B (Base Case) | Scenario C (Conservative) |
|:---|:---|:---|:---|
| Execution Latency | 5 ms | 25 ms | 100 ms |
| Fee Schedule | VIP / Zero Maker (0.0002) | Standard Retail Taker (0.0010) | Standard Retail Taker (0.0010) |
| Slippage Model | Half-spread only (0.00025) | Spread + Half Tick (0.0006) | Spread + Full Tick + Impact (0.0012) |
| Adverse Selection | 0.0 bps | 1.0 bps | 3.0 bps |
| Queue Fill Model | Immediate at touch | Queue-based with latency | Conservative fill at worse tick |

---

## 3. ABSOLUTE FREEZE CERTIFICATION

I hereby certify that:
1. No parameter tuning, threshold searching, or indicator optimization occurred during Phase 10C.X.
2. All parameters above were declared and frozen prior to running the blind historical test.
3. No historical results were used to modify strategy behavior.
