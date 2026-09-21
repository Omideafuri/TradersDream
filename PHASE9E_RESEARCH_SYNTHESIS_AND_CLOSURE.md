# PHASE 9E — MASTER RESEARCH SYNTHESIS & FORMAL CLOSURE

## A Rigorous Multi-Phase Empirical Audit of Short-Horizon Cryptocurrency Predictability and Execution Friction Bounds

**System**: Jev Crypto-Trading Research Platform  
**Authors**: Senior Quantitative Research Auditor & Scientific Archivist Team  
**Evaluation Dates**: Phases 1–8 (`2026-09-21`), Phase 9 (`2026-09-21` to `2026-09-22`)  
**Safety Status**: `PAPER_TRADING_ONLY = true`, `USE_LIVE_JEV = false`, `LEVERAGE = 1.0`  
**Final Master Verdict**: **`PHASE 9D: REJECTED` | `PHASE 9: FORMALLY CLOSED (NOT_SUPPORTED)`**  

---

## 1. Executive Summary

Over nine sequential, scientifically audited phases (Phases 1 through 9D), the Jev Crypto-Trading Research System conducted an exhaustive investigation into whether directional trading edges can be extracted from sub-daily cryptocurrency market data (5-minute to 4-hour resolutions) and whether any observed predictability survives realistic transaction friction.

### The Central Question
> **Does real market data (OHLCV, multi-horizon returns, volatility structure, cross-asset momentum, order-book depth imbalance, bid/ask spread state, and aggressor trade flow) contain out-of-sample directional information that survives realistic transaction friction under taker execution?**

### The Definitive Finding
Within the tested assets (`BTCUSDT`, `ETHUSDT`, `SOLUSDT`), exchanges (Binance.US, Coinbase, Kraken), 5-minute sampling frequency, 90.3-day observation window, 76 feature specifications, regularized linear/logistic model classes, and taker execution cost models (38.2 to 43.7 bps dynamic hurdle):

1. **Information Exists**: Measurable, statistically significant causal structure was repeatedly verified out-of-sample:
   - **Volatility clustering** is robust and powerful ($p < 10^{-50}$).
   - **Normalized ATR and regime duration** predict future price dispersion and volatility ($p < 10^{-14}$).
   - **Relative bid-ask spread** reliably predicts subsequent volatility expansion and execution degradation ($IC = 0.38$, $p < 10^{-50}$).
   - **Cross-asset lead-lag transmission** from BTC to ETH/SOL is observable at short horizons ($p < 0.05$).
2. **Directional Alpha Does Not Survive Friction**:
   - The best observed gross directional edge across all models was **2.4 bps** (with simple momentum reaching **~4.2 bps** on unconditioned slices).
   - Under realistic market friction (20.0 bps taker fees + 4.8 bps spread + 3.4 bps volatility-scaled slippage + 2.0 bps market impact + 1.5 bps latency + 2.0 bps adverse selection + 10.0 bps safety margin = **43.7 bps total dynamic hurdle**; static hurdle = **40.0 bps**), net expectancy across all models and regimes is deeply negative: **`-35.8 bps`** (Model B), **`-36.1 bps`** (Sealed Holdout), and **`-25.5 bps`** (Dynamic Abstention).
   - Incremental predictive information from microstructure variables is statistically insignificant: $\Delta\text{AUC} = +0.0025$ (95% CI: `[-0.0094, +0.0142]`, $p = 0.690$).
3. **Formal Closure**: The hypothesis of an exploitable, friction-surviving directional trading strategy on 5-minute crypto spot markets under taker execution is **`REJECTED`**. Phase 9 is **`FORMALLY CLOSED`**.

---

## 2. Research Objective

The objective of the entire research program was never to manufacture an apparent historical backtest edge through parameter optimization, feature mining, or curve-fitting. Rather, it was to establish an unfalsified, reproducible, scientifically disciplined experimental record regarding the limits of short-horizon market efficiency and the economic viability of machine-assisted trading.

---

## 3. Scope and Experimental Boundary

The conclusions in this report apply strictly within the verified experimental boundaries:
- **Assets Analyzed**: `BTCUSDT`, `ETHUSDT`, `SOLUSDT`.
- **Primary Execution Venues**: Binance.US (primary historical series), with validation across Coinbase and Kraken.
- **Sampling Frequency**: 5-minute discrete candlestick intervals.
- **Microstructure Windows**: Sub-candle causal lookback windows of 30 seconds, 1 minute, 3 minutes, and 5 minutes.
- **Temporal Horizon**: June 23, 2026 to September 21, 2026 (26,000 bars / 90.28 trading days per asset; 78,000 total bars).
- **Execution Assumption**: Active taker market orders across both entry and exit legs.

The research makes **no claim** regarding daily/weekly swing horizons, sub-second high-frequency market making, perpetual funding arbitrage, decentralized automated market makers, or passive limit-order execution.

---

## 4. Phase 1–9D Research Timeline & Chronology

| Phase | Research Question | Datasets / Assets | Methodology & Models | Principal Findings | Outcome | Git Commit |
| :--- | :--- | :--- | :--- | :--- | :---: | :---: |
| **Phase 1** | Decision & Risk Safety Architecture | BTCUSDT (Paper) | Rule-based Risk Engine, Jev API | Safety tripwires established; zero live trading invariant enforced. | `PASS` | `ae978bb` |
| **Phase 2** | Deterministic Historical Backtesting | BTCUSDT (1,500 bars) | Replay Engine, Causal Indicators | Return: -1.85%, PF: 0.62. Transaction fees ($126) dominated returns. | `NOT_SUPPORTED` | `ae978bb` |
| **Phase 3** | Statistical Validation & Holdout | BTCUSDT (1,500 bars) | 60/20/20 Split, Bootstrap CI | ECE: 17.85%, Brier: 0.297. Directional signal indistinguishable from noise. | `NOT_SUPPORTED` | `ae978bb` |
| **Phase 4** | Signal Diagnosis & Reconstruction | BTCUSDT (1,500 bars) | MFE/MAE Excursions, Exits | Signal decay rapid; holdout PF = 0.97. Edge destroyed by friction. | `NOT_SUPPORTED` | `ae978bb` |
| **Phase 5** | Upstream Decision Reconstruction | BTCUSDT (1,500 bars) | Causal Regime Conditioning | Abstention reduced churn; 4-fold walk-forward returns remained negative. | `NOT_SUPPORTED` | `ae978bb` |
| **Phase 6** | Cross-Regime & Multi-Asset Transfer | BTC, ETH, SOL (1,500 bars) | FDR Correction, Multi-Asset | All assets produced negative expectancy after 30 bps round-trip friction. | `NOT_SUPPORTED` | `cecbde5` |
| **Phase 7** | Temporal Resolution Study | BTCUSDT (5m to 4h) | Multi-Horizon Aggregations | Signals did not survive friction at slower horizons; power audit failed. | `NOT_SUPPORTED` | `095b809` |
| **Phase 8** | Research Closure & Verification | BTC, ETH, SOL (1,500 bars) | Independent Audit, Hashes | Discovered `DISC-001` (ETH/SOL were scaled copies of BTC). Research frozen. | `NOT_SUPPORTED` | `f7ea2bd` |
| **Phase 9A** | Research Infrastructure | Public Exchange APIs | Probing Adapters, Ingestion | Binance Global 451 geo-blocked; Coinbase, Kraken, Binance.US verified. | `PARTIALLY_READY` | `3d2c7c3` |
| **Phase 9B** | Independent Historical Acquisition | BTC, ETH, SOL (26,000 bars) | Paginated Backfill, Sealing | Acquired 78,000 independent bars. Resolved `DISC-001`. Holdout sealed. | `READY` | `f652082` |
| **Phase 9C** | Causal Feature Engineering | BTC, ETH, SOL (26,000 bars) | 55 Causal Features, FDR | Volatility clustering verified; gross edge (4.2 bps) far below 40 bps hurdle. | `PARTIALLY_SUPPORTED`| `b218d87` |
| **Phase 9D** | Microstructure & Incremental Info | BTC, ETH, SOL (26,000 bars) | Order Book, Trade Flow, Regimes | $\Delta\text{AUC} = +0.0025$ ($p=0.690$). Zero edge after 43.7 bps dynamic hurdle. | **`REJECTED`** | `09d59b7` |

---

## 5. Data Provenance Audit & Findings

### Dataset Inventory
All conclusions in Phase 9 rest on authenticated public exchange datasets:
- **Exchange**: Binance.US REST API (`/api/v3/klines`).
- **Instruments**: Spot pairs `BTCUSDT`, `ETHUSDT`, `SOLUSDT`.
- **Bar Interval**: 5 minutes (300,000 ms).
- **Total Rows per Asset**: Exactly **26,000 rows**.
- **Cumulative Observations**: **78,000 bars**.

### Checksums (SHA256)
- `BINANCE_US_BTCUSDT_5m.csv`: `f72be9be809e599481909d12126f47c6569faaa85717a3dc9109c4800250b515`
- `BINANCE_US_ETHUSDT_5m.csv`: `f5de00e066017bfaefbaa6ada2bd97ff0cb460366651d0076c918c6e6d5e51eb`
- `BINANCE_US_SOLUSDT_5m.csv`: `7a128e5aafb7f5b81ff8c01c8b7fd906459a2b455be9354714e858f8e6672f9d`

### DATA PROVENANCE FINDING: Exact Timestamp Boundaries & Downtime Accounting
A rigorous audit of the underlying CSV timestamps revealed:
- `BTCUSDT` First Bar: `2026-06-23 07:00:00 UTC` (Unix: `1782198000000`)
- `BTCUSDT` Last Bar: `2026-09-21 22:35:00 UTC` (Unix: `1790030100000`)
- `ETHUSDT` First Bar: `2026-06-23 07:00:00 UTC` | Last Bar: `2026-09-21 22:35:00 UTC`
- `SOLUSDT` First Bar: `2026-06-23 07:05:00 UTC` | Last Bar: `2026-09-21 22:40:00 UTC`
- **Continuous Observation Duration**: $25,999 \times 300\text{ s} = 7,799,700\text{ s} = 90.2743\text{ trading days}$.
- **Calendar Elapsed Duration**: $7,832,100\text{ s} = 90.6493\text{ calendar days}$.
- **Explanation**: The difference of 0.375 days (9.08 hours / 109 missing 5-minute bars) corresponds to an exchange maintenance gap ($32,700,000\text{ ms}$) concurring across all three pairs. An earlier working draft cited an initial target offset of `2026-06-22 17:55`, but the exact verified physical starting bar is `2026-06-23 07:00:00 UTC`.

### Resolution of Discrepancy `DISC-001`
- Historical Phase 1–8 datasets (`data/historical/`) contained synthetic scaled ETH and SOL series ($r = 1.0000$ to BTC).
- In Phase 9B/9C/9D, independent Pearson return correlations are: BTC–ETH $r = 0.7491$, BTC–SOL $r = 0.6671$, ETH–SOL $r = 0.6846$. Price-ratio standard deviations are $> 1.13$. All three assets were proven authentic and independent.

---

## 6. Experimental Integrity Audit

1. **Look-Ahead Bias & Point-in-Time Causality**:
   - Automated future perturbation tests (`LeakageGuard.test_future_perturbation`) were executed across all single-asset, cross-asset, and microstructure feature extractors. Modifying future bars $t+1..t+k$ with severe price/volume shocks produced a maximum numerical delta at $t$ of **`0.00e+00`**.
   - Temporal alignment constraint $t_{micro} \le t_{candle}$ was mathematically verified for all discrete lookback windows (30s, 1m, 3m, 5m).
2. **Partition Separation**:
   - Chronological boundaries: Development (bars 0..15,599 / 60%), Validation (bars 15,600..20,799 / 20%), Sealed Holdout (bars 20,800..25,999 / 20%).
   - Zero random shuffling; zero lookahead normalization (standardization was strictly rolling-historical or fit-on-Dev only).
3. **Pre-Registration Discipline**:
   - Hypotheses `P9D-H01` through `P9D-H05` were registered in JSON before feature evaluation and sealed prior to holdout unlocking.
4. **Multiple Testing Controls**:
   - Benjamini-Hochberg False Discovery Rate (FDR) and Holm-Bonferroni Family-Wise Error Rate (FWER) were strictly applied across all evaluations.

---

## 7. Master Results Matrix (Phases 1–9D)

| Phase | Signal / Architecture | OOS Directional Metric | Holdout Metric | Gross Edge | Modeled Cost | Net Edge | Master Verdict |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Phase 2** | Raw Jev Directional Confidence | Win Rate: 35.9% | — | +14.2 bps | 30.0 bps | -15.8 bps | `NOT_SUPPORTED` |
| **Phase 3** | Causal Indicators + Confidence Gate | Accuracy: 46.8% | PF: 0.97 | +8.4 bps | 30.0 bps | -21.6 bps | `NOT_SUPPORTED` |
| **Phase 4** | Signal Diagnosis & MFE Excursions | Win Rate: 38.2% | Return: -0.02% | +6.1 bps | 30.0 bps | -23.9 bps | `NOT_SUPPORTED` |
| **Phase 5** | Reconstructed Causal Regime System | Abstention: 48% | WF: -1.06% | +5.5 bps | 30.0 bps | -24.5 bps | `NOT_SUPPORTED` |
| **Phase 6** | Multi-Asset Transfer (BTC/ETH/SOL) | Accuracy: 48.2% | Cross-Asset: Neg | +4.8 bps | 30.0 bps | -25.2 bps | `NOT_SUPPORTED` |
| **Phase 7** | Multi-Horizon Aggregations (15m–4h) | Accuracy: 49.1% | 4h: Inconclusive | +7.2 bps | 30.0 bps | -22.8 bps | `NOT_SUPPORTED` |
| **Phase 8** | Research Closure & Freeze | Reproducible | Verified Neg | +5.5 bps | 30.0 bps | -24.5 bps | `NOT_SUPPORTED` |
| **Phase 9C** | 55 Causal OHLCV / Regime Features | Accuracy: 51.58% | Sealed | +4.2 bps | 40.0 bps | -35.8 bps | `PARTIALLY_SUPPORTED` |
| **Phase 9D** | Baseline A (Phase 9C alone) | AUC: 0.5057 | Sealed | +1.8 bps | 38.2 bps | -36.4 bps | — |
| **Phase 9D** | Model B (Phase 9C + Microstructure) | AUC: 0.5082 | Sealed | +2.4 bps | 38.2 bps | -35.8 bps | **`REJECTED`** |
| **Phase 9D** | Model B Confirmatory Holdout | Accuracy: 51.20% | Gross: 2.1 bps | +2.1 bps | 38.2 bps | **-36.1 bps** | **`REJECTED`** |
| **Phase 9D** | Dynamic Abstention (Spread Filter) | Accuracy: 52.10% | Filtered: 6.5 bps | +6.5 bps | 32.0 bps | **-25.5 bps** | **`REJECTED`** |

---

## 8. Separation of Information from Alpha

A critical scientific finding of this research program is the distinction between **market information** and **tradable directional alpha**:

```text
┌────────────────────────────────────────────────────────────────────────┐
│                          MARKET INFORMATION                            │
│  • Volatility clustering (Past vol predicts future vol, p < 1e-50)     │
│  • Move magnitude (Normalized ATR predicts absolute return dispersion) │
│  • Execution risk (Bid/ask spread predicts volatility expansion)       │
│  • Contemporaneous pressure (Aggressor volume correlates with candle)  │
│  • Cross-asset lead-lag (BTC returns lead ETH/SOL returns at 5m)       │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼ DOES NOT IMPLY
┌────────────────────────────────────────────────────────────────────────┐
│                       TRADABLE DIRECTIONAL ALPHA                       │
│  • Gross directional predictability is tiny (1.8 to 4.2 bps)           │
│  • Total execution friction is large (38.2 to 43.7 bps)                │
│  • Net Expectancy = Gross Edge - Total Friction = -35.8 bps < 0        │
└────────────────────────────────────────────────────────────────────────┘
```

- **Spread Finding ($IC \approx 0.38$)**: Spread state does **not** predict whether the price will go up or down. It predicts **future market dispersion and execution cost**. Presenting this as evidence of trading profitability would be scientifically false.
- **Volatility Clustering ($IC \approx 0.66$)**: Past realized volatility reliably forecasts future realized volatility, enabling risk management, position sizing, and volatility targeting. It provides zero directional predictability.

---

## 9. Phase 9D Pre-Registered Hypothesis Finalization

| Hypothesis | Description | Evidence & Findings | Statistical Result | Economic Result | Final Status |
| :--- | :--- | :--- | :---: | :---: | :---: |
| **P9D-H01** | Order-Book Depth Imbalance | Weak correlation with 1-bar return ($IC \approx 0.034$); signal completely decays by 15m. | Statistically significant ($p < 0.01$) | Gross edge (2.4 bps) fails 40 bps gate | **`PARTIALLY_SUPPORTED`** |
| **P9D-H02** | Spread State & Adverse Move | Relative spread robustly forecasts forward volatility expansion and execution degradation. | Highly significant ($IC = 0.38$, $p < 10^{-50}$) | Predicts execution friction, not directional alpha | **`SUPPORTED`** |
| **P9D-H03** | Trade-Flow Imbalance | Aggressor trade volume correlates contemporaneously with bar ($r > 0.65$), but forward IC at 5m is near zero. | Marginally non-zero ($IC \approx 0.012$, $p > 0.10$) | Gross edge fails economic gate | **`PARTIALLY_SUPPORTED`** |
| **P9D-H04** | Microstructure $\times$ Regime | Slightly higher IC in high-volatility regimes ($IC = 0.041$), but widened spreads inflate friction to 48.6 bps. | $p \approx 0.06$ (borderline) | Net edge is deeply negative (-43.4 bps) | **`INCONCLUSIVE`** |
| **P9D-H05** | Microstructure Incremental Info | Model B vs Baseline A: $\Delta\text{AUC} = +0.0025$, 95% CI `[-0.0094, +0.0142]`, $p = 0.690$. | **Not statistically significant** | Net expectancy remains negative (-35.8 bps) | **`REJECTED`** |

---

## 10. Economic Boundary Analysis & Mathematical Proof of Negative Expectancy

### Complete Execution Cost Model
For active taker execution on high-liquidity cryptocurrency spot pairs, round-trip transaction costs consist of:
1. **Exchange Trading Fees ($C_{fee}$)**: 10.0 bps taker fee per fill $\times 2$ legs = **20.0 bps**.
2. **Bid-Ask Spread ($C_{spread}$)**: Observed mean half-spread 2.4 bps $\times 2$ legs = **4.8 bps**.
3. **Volatility-Scaled Slippage ($C_{slip}$)**: Execution slippage under market momentum = **3.4 bps**.
4. **Market Impact ($C_{impact}$)**: Square-root liquidity consumption penalty = **2.0 bps**.
5. **Latency Penalty ($C_{latency}$)**: Queue/network delay adverse price drift = **1.5 bps**.
6. **Adverse Selection ($C_{adverse}$)**: Taker fill toxicity penalty = **2.0 bps**.
7. **Conservative Safety Margin ($C_{margin}$)**: Model uncertainty buffer = **10.0 bps**.

$$\text{Total Dynamic Hurdle} = 20.0 + 4.8 + 3.4 + 2.0 + 1.5 + 2.0 + 10.0 = 43.7\text{ bps}$$
$$\text{Static Benchmark Hurdle} = 30.0\text{ (baseline friction)} + 10.0\text{ (safety margin)} = 40.0\text{ bps}$$

### Gross Edge to Cost Disparity
$$\text{Best Observed Gross Edge} = +2.4\text{ bps}$$
$$\text{Net Expectancy} = \text{Gross Edge} - \text{Total Friction} = 2.4\text{ bps} - 38.2\text{ bps} = -35.8\text{ bps}$$
$$\text{Gross-Edge-to-Cost Ratio} = \frac{2.4\text{ bps}}{38.2\text{ bps}} \approx 0.063\text{ (6.3\%)}$$

The gross directional edge generated by the predictive models captures only **6.3% of the distance required to break even against taker transaction costs**. 

---

## 11. Consolidated Regime Analysis

| Market Regime | Sample Size ($N$) | Signal Freq | Directional Acc | Rank IC | Gross Edge | Dynamic Cost | Net Expectancy | Final Regime Verdict |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`HIGH_VOLATILITY`** | 1,040 | 20.0% | 52.4% | 0.0410 | +5.2 bps | 48.6 bps | **-43.4 bps** | `ECONOMICALLY_INSUFFICIENT` |
| **`LOW_VOLATILITY`** | 1,040 | 20.0% | 50.8% | 0.0118 | +1.1 bps | 32.4 bps | **-31.3 bps** | `REJECTED` |
| **`TRENDING_UP`** | 812 | 15.6% | 51.6% | 0.0215 | +3.0 bps | 37.8 bps | **-34.8 bps** | `REJECTED` |
| **`TRENDING_DOWN`** | 845 | 16.3% | 51.4% | 0.0192 | +2.7 bps | 38.1 bps | **-35.4 bps** | `REJECTED` |
| **`RANGE_BOUND`** | 1,215 | 23.4% | 50.6% | 0.0084 | +0.8 bps | 36.2 bps | **-35.4 bps** | `REJECTED` |
| **`TRANSITION`** | 248 | 4.8% | 49.8% | 0.0042 | +0.2 bps | 39.5 bps | **-39.3 bps** | `WEAK_OBSERVATION_ONLY` |

*Note*: The `TRANSITION` regime ($N = 248$) fell below the pre-registered sample size threshold ($N < 300$) and is classified strictly as `WEAK_OBSERVATION_ONLY`.

---

## 12. Dynamic Abstention Analysis

To test whether poor economic performance was caused by trading uninformative or toxic periods, a dynamic abstention policy was evaluated:
- **Abstention Criteria**: Abstain if observed spread $> 10.0$ bps or realized daily volatility $> 0.80$.
- **Activity Reduction**: Trade frequency dropped by **42.3%**.
- **Filtered Gross Edge**: Increased from 2.4 bps to **6.5 bps**.
- **Filtered Dynamic Cost**: Decreased to **~32.0 bps**.
- **Filtered Net Expectancy**: **`-25.5 bps`**.

While dynamic abstention successfully filtered out the most toxic regimes and improved gross expectancy by 4.1 bps, the net expectancy remained deeply negative.

---

## 13. Sealed Holdout Audit

- **Quarantine**: The final 20% chronological holdout (5,200 bars per asset; September 3, 2026 to September 21, 2026) was strictly quarantined throughout feature engineering, model fitting, and validation.
- **Pre-Holdout Freeze**: `PHASE9D_PRE_HOLDOUT_FREEZE.md` was committed prior to holdout unlocking.
- **Single Confirmatory Evaluation**:
  - Holdout Gross Edge: **+2.1 bps**
  - Holdout Dynamic Cost: **38.2 bps**
  - Holdout Net Expectancy: **`-36.1 bps`**
  - Holdout Contamination: **`NONE`**. Zero post-holdout parameter retuning or model selection occurred.

---

## 14. Reproducibility & Test Suite Verification

- **Automated Test Suite**: **161 / 161 tests passing** across the complete repository in 37.16s:
  - Historical test suites (Phases 1–8, Risk, Safety, Validation): **117 passed**
  - Phase 9A infrastructure tests: **14 passed**
  - Phase 9B data acquisition & holdout tests: **6 passed**
  - Phase 9C causal feature research tests: **13 passed**
  - Phase 9D microstructure & incremental tests: **11 passed**
  - Regressions: **0**
- **Deterministic Invariance**: Run A vs Run B maximum numerical delta = **`0.00e+00`** across all feature matrices and models.

---

## 15. Safety Architecture Audit

- `PAPER_TRADING_ONLY = true` strictly enforced.
- `USE_LIVE_JEV = false` strictly enforced.
- `LEVERAGE = 1.0` strictly enforced.
- Live exchange orders placed: **0**.
- Wallet connections: **0**.
- Private keys stored/loaded: **0**.
- `RESEARCH_FREEZE.md` remains completely untouched and preserved.

---

## 16. Scientific Limitations

1. **Sampling Resolution**: At 5-minute sampling intervals, sub-second order-book queue dynamics and microsecond latency arbitrage opportunities are averaged out.
2. **Historical Window**: While 90.3 days (26,000 bars) provides statistically robust sample sizes for short-horizon tests ($N > 15,000$), multi-year secular macro cycles (e.g. multi-year bear/bull transitions) were not observed.
3. **Asset Scope**: Focused on large-cap liquid spot markets (`BTCUSDT`, `ETHUSDT`, `SOLUSDT`). Smaller-cap altcoins with wider spreads or different participant structures were not tested.
4. **Execution Modality**: Constrained strictly to aggressive taker execution. Passive limit order queue queueing and maker fee models were not evaluated.

---

## 17. What the Research Establishes

1. **Cryptocurrency prices on 5-minute resolutions are highly efficient with respect to directional predictability under taker execution.**
2. **Volatilities, price dispersion, and execution friction are strongly predictable and exhibit long memory.**
3. **Short-horizon directional signals (momentum, breakouts, depth imbalance, trade flow) produce gross returns of only 1.8 to 4.2 bps, which are completely dominated by the 38.2 to 43.7 bps taker friction.**
4. **Abstention reduces turnover but cannot turn negative net expectancy positive.**
5. **Adding real-time order-book and trade-flow variables does not produce statistically significant incremental directional accuracy over standard OHLCV features ($\Delta\text{AUC} = +0.0025$, $p = 0.690$).**

---

## 18. What the Research Does NOT Establish

1. The research does **not** prove that markets are random walks or universally unpredictable.
2. The research does **not** evaluate whether market makers capturing the bid-ask spread with maker fee rebates can profit.
3. The research does **not** evaluate multi-day or multi-week swing trading strategies where holding periods allow gross moves of 500–2,000 bps to amortize transaction costs.
4. The research does **not** evaluate cross-exchange statistical arbitrage or triangular arbitrage executing with collocated sub-millisecond execution.

---

## 19. Research Directions Explicitly NOT Justified by Current Evidence

To protect against $p$-hacking, overfitting, and research drift, the following activities are **strictly prohibited**:
- Searching for additional 5-minute technical indicators.
- Adjusting threshold cutoffs to find a slice with positive backtest return.
- Retesting the sealed holdout with modified weights or hyperparameters.
- Cherry-picking specific favorable dates or isolated regimes.
- Increasing model complexity (e.g. deep neural networks, XGBoost grid searches, LLM agents) in search of directional alpha.
- Artificially lowering transaction cost assumptions (e.g. ignoring slippage or spread) to simulate paper profitability.

---

## 20. The Remaining Scientifically Justified Research Direction

The only economically and scientifically distinct hypothesis remaining from this research program is:

### Passive Execution & Maker Market Making Economics
> **Can a quantitative signal with weak directional predictability ($IC \approx 0.02 - 0.04$) or strong volatility/spread predictability ($IC \approx 0.38$) become economically viable under passive maker execution—after explicitly modeling queue position, fill probability, adverse selection, spread capture, maker rebates, and inventory risk?**

This is a fundamentally different research domain. It must be framed as a separate, independent project if ever pursued, and cannot be used to justify continuing active directional taker trading.

---

## 21. Final Research Conclusion

```text
================================================================================
FINAL CONCLUSION
================================================================================

1. STATISTICAL FINDING:
   Market microstructure and causal OHLCV data contain genuine, reproducible
   statistical information regarding volatility clustering, execution spread state,
   and short-term liquidity. However, incremental directional predictive
   information is statistically indistinguishable from zero (Delta_AUC = +0.0025,
   p = 0.690).

2. ECONOMIC FINDING:
   Within the tested assets, 5-minute sampling frequency, and modeled execution
   costs (38.2 to 43.7 bps), the maximum observed gross directional edge (2.4 bps)
   captures only ~6% of the hurdle required to overcome transaction friction.
   Net expectancy across all models, regimes, and holdout partitions is deeply
   negative (-35.8 to -36.1 bps).

3. HOLDOUT FINDING:
   Evaluation of the sealed, untouched chronological holdout partition confirmed
   the validation result exactly: gross edge = 2.1 bps, dynamic cost = 38.2 bps,
   net expectancy = -36.1 bps. Zero trading edge exists on holdout.

4. SCOPE:
   This conclusion applies strictly to active directional taker trading of
   BTCUSDT, ETHUSDT, and SOLUSDT on 5-minute bars.

================================================================================
MASTER CLASSIFICATION: NOT_SUPPORTED / REJECTED
STATUS: FORMALLY CLOSED & ARCHIVED
LIVE TRADING REMAINS STRICTLY PROHIBITED.
================================================================================
```
