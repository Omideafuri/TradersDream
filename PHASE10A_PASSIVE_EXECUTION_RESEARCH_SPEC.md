# PHASE 10A — PASSIVE EXECUTION & QUEUE DYNAMICS RESEARCH SPECIFICATION

**Document Identifier**: `PHASE10A_PASSIVE_EXECUTION_RESEARCH_SPEC.md`  
**Research Initiative**: Program 10A — Market-Making, Passive Execution Economics & Queue Dynamics  
**Platform**: Jev Crypto-Trading Research System  
**Audit Status**: Pre-Implementation Research Specification & Protocol Design  
**Date**: `2026-09-22T03:00:00+00:00`  
**Safety Invariants**: `PAPER_TRADING_ONLY = true`, `USE_LIVE_JEV = false`, `LEVERAGE = 1.0`  
**Historical Precedent**: Phase 9 is formally closed and sealed (`NOT_SUPPORTED` for 5-minute directional taker trading).

---

## 1. RESEARCH QUESTION

Can a passive limit-order execution strategy produce a statistically defensible and economically positive out-of-sample net expectancy on liquid spot cryptocurrency pairs, when modeled with realistic price-time priority queue dynamics, partial fills, cancellation latency, adverse selection, inventory risk, and maker fee economics?

This is a falsifiable empirical hypothesis, not an assumption. The research program is designed with formal gates capable of conclusively rejecting passive execution if the economics fail.

---

## 2. SCIENTIFIC MOTIVATION

In Phases 1 through 9D, the research system established an unequivocal empirical finding:
* 5-minute directional predictors achieved a maximum gross expectancy of approximately **$+2.4\text{ bps}$**.
* Standard taker execution (crossing the bid-ask spread and paying taker exchange fees) imposed a dynamic friction hurdle of **$38.2\text{ to }43.7\text{ bps}$** per round trip.
* Net expectancy was deeply negative (**$-35.8\text{ bps}$** in cross-validation; **$-36.1\text{ bps}$** on the sealed holdout).
* Gross directional edge covered only $\approx 6.3\%$ of the taker hurdle.

### The Structural Shift: Taker vs. Maker Economics

```text
TAKER EXECUTION PARADIGM (PHASES 1–9)
Signal Event → Cross Spread → Pay Taker Fee (10 bps) → Pay Half-Spread (6.5 bps) → Pay Slippage (3–10 bps) → Negative Net (-36 bps)

PASSIVE / MAKER EXECUTION PARADIGM (PROGRAM 10A)
Quote Placement → Join Queue (Wait) → Fills at Bid/Ask → Earn Half-Spread (+6.5 bps) → Pay Maker Fee / Rebate (-1 to +2 bps) → Incur Adverse Selection (-X bps) → Manage Inventory → Net Expectancy
```

A market maker does not need to forecast long-horizon directional trend; rather, the market maker supplies liquidity, capturing the spread ($2 \times \text{HalfSpread} \approx 13.0\text{ bps}$) and paying lower maker fees ($0\text{ to }2\text{ bps}$ vs $10\text{ bps}$). 
However, **spread capture is not guaranteed profit**. Realized spread is severely eroded by:
1. **Adverse Selection**: Orders only fill when aggressive counterparties possess superior short-term information or directional momentum that moves prices through the limit order.
2. **Queue Position Drag**: In price-time priority, joining at the back of the queue means fills occur disproportionately during large market sweeps that overrun the level.
3. **Execution Latency**: Delays in cancelling stale quotes when the midpoint shifts expose passive quotes to being "picked off".
4. **Inventory Risk & Liquidation Costs**: Unbalanced fills accumulate inventory that must ultimately be liquidated via aggressive taker orders or skewed quoting at adverse prices.

---

## 3. RESEARCH BOUNDARY

The empirical scope of Program 10A is strictly defined:
* **Asset Universe**: `BTCUSDT`, `ETHUSDT`, `SOLUSDT`.
* **Execution Venue**: Spot centralized limit order book (Binance.US baseline; comparative Tier-1 crypto CLOB schedules).
* **Order Types**: Passive non-marketable limit orders (`Post-Only` / `Maker-Or-Cancel`), with aggressive market orders permitted strictly for emergency inventory risk liquidation.
* **Temporal Frequency**: Event-level discrete simulation (microsecond to millisecond order-book updates and trades). 5-minute candle aggregation is barred from queue simulation.
* **Leverage & Capital**: Spot cash accounting, zero leverage (`LEVERAGE = 1.0`), maximum position limits strictly enforced.

---

## 4. DATA REQUIREMENTS

Realistic passive execution modeling requires three synchronized data feeds:
1. **Feed A: Level-2 (L2) Incremental Depth Feed**:
   - Depth of book: Top 10–20 price levels.
   - Updates: Real-time price and size changes with monotonic update sequence numbers.
2. **Feed B: Tick-by-Tick Trade Stream**:
   - Every execution with microsecond timestamp, trade size, price, and aggressor buyer/seller classification.
3. **Feed C: Periodic L2 Snapshot Book**:
   - Full book snapshots every 1 to 5 minutes to audit and reset sequence continuity.

---

## 5. EXISTING-DATA AUDIT & SUFFICIENCY DECISION

An audit of the repository (`data/historical/` and `data/phase9_data/`) reveals:
* Available datasets consist solely of 5-minute OHLCV candles (1,500 bars from Phases 1–8; 26,000 bars from Phase 9B).
* No tick-level trade feeds or incremental L2 order book delta logs exist locally.

### Formal Data Sufficiency Verdict
```text
========================================================================================
                          DATA SUFFICIENCY AUDIT:
               DATA INSUFFICIENT FOR REALISTIC QUEUE MODELING
========================================================================================
```
* **Consequence**: The simulator implementation must not fabricate synthetic microsecond queues from 5-minute bars. Before running strategy evaluations, an event-level data ingestion module must acquire genuine tick/L2 depth data.

---

## 6. TIMESTAMP ARCHITECTURE & LATENCY MODEL

To eliminate lookahead and latency bias, the event simulator must decouple time into distinct physical milestones:

```text
t_exchange_event  : Exchange matching-engine event generation time
t_local_receive   : Local network socket reception time
t_sim_decision    : Algorithmic decision computation completion time
t_wire_latency    : Outbound network transmission to exchange
t_engine_arrival  : Order arrival and queue entry at exchange matching engine
t_fill_time       : Exact matching engine fill timestamp
```

### Latency Profiles (Preregistered):
1. **Idealized Co-located (0 ms / instantaneous)**: Used only as an upper-bound diagnostic.
2. **Realistic Retail / API Gateway (Modeled Baseline)**:
   - Inbound feed latency: $\mathcal{N}(20\text{ ms}, 3\text{ ms})$.
   - Decision latency: $2\text{ ms}$.
   - Outbound wire latency: $\mathcal{N}(25\text{ ms}, 5\text{ ms})$ with Pareto tail to $120\text{ ms}$.
   - Total cancellation round-trip latency: $\approx 45\text{--}50\text{ ms}$.
3. **Stressed Latency Profile**:
   - Total round-trip latency scaled by $+25\%$ ($\approx 60\text{--}70\text{ ms}$).

---

## 7. QUEUE MODEL

Cryptocurrency exchanges operate continuous **Price-Time Priority (FIFO)** matching engines. The simulator must track the queue position of every submitted passive order at price level $p$:

$$Q_{\text{ahead}}(t) = \text{Total displayed size at price } p \text{ ahead of our order}$$

### Queue Dynamics:
1. **Queue Entry**: When an order is placed at $p$, $Q_{\text{ahead}}(t_{\text{entry}}) = V_{\text{level}}(p) - \text{our size}$.
2. **Queue Depletion via Trade**: Every aggressive trade executed at price $p$ on our side reduces $Q_{\text{ahead}}$ by $\min(Q_{\text{ahead}}, V_{\text{trade}})$.
3. **Queue Depletion via Cancellation**: When the level size decreases without a corresponding trade, cancellations are modeled conservatively:
   - Under conservative FIFO, external cancellations are assumed to occur **behind** our order unless the level volume falls below $Q_{\text{ahead}}$.
   - Proportional model: Cancellations deplete $Q_{\text{ahead}}$ proportionally to $Q_{\text{ahead}} / V_{\text{level}}$.
4. **Replenishment**: Additions to the book level are always placed behind our order in queue priority.

---

## 8. FILL MODEL

A passive order cannot fill simply because the market price touched the level. The simulator must enforce a strict, conservative fill state machine:

```text
[SUBMITTED] 
    │ (latency delay)
    ▼
[ACTIVE IN QUEUE: Q_ahead > 0]
    │ (trades deplete Q_ahead to 0)
    ▼
[TOP OF QUEUE: Q_ahead == 0]
    ├── Incoming Trade Volume < Order Size ──► [PARTIAL FILL] (remaining stays active)
    ├── Incoming Trade Volume >= Order Size ──► [FULL FILL]
    └── Midpoint shifts / Cancel signal arrives ──► [CANCELLED]
```

### Classification of Fills:
* `NO_FILL`: Cancelled before reaching top of queue.
* `PARTIAL_FILL`: Partially matched; remaining cancelled or executed subsequently.
* `FULL_FILL`: Completely executed.
* `ADVERSE_FILL`: Filled immediately prior to a sustained midpoint price breakdown.
* `FAVORABLE_FILL`: Filled with subsequent price bounce/mean-reversion.

---

## 9. ADVERSE SELECTION MODEL

Adverse selection is defined as the signed post-fill movement of the market midpoint against the passive maker order:

$$\text{Markout}_k(t) = \begin{cases} 
\text{Mid}(t + k) - P_{\text{fill}} & \text{for Passive Bids (Long Fills)} \\
P_{\text{fill}} - \text{Mid}(t + k) & \text{for Passive Asks (Short Fills)} 
\end{cases}$$

### Markout Horizons to Evaluate:
* $\tau \in \{100\text{ ms}, 500\text{ ms}, 1\text{ s}, 5\text{ s}, 30\text{ s}, 1\text{ min}, 5\text{ min}\}$.

### Metrics to Measure:
* **Mean and Median Markout**: Expected value of price drift after execution.
* **Toxic Fill Fraction**: Percentage of fills where $\text{Markout}_k < 0$.
* **Conditional Adverse Selection**: Markout conditioned on book imbalance, trade-flow momentum, and spread regime.

---

## 10. REALIZED SPREAD MODEL

The research system must decouple the three layers of spread economics:

1. **Quoted Spread**:
   $$S_{\text{quoted}}(t) = P_{\text{ask}}(t) - P_{\text{bid}}(t)$$
2. **Effective Half-Spread**:
   $$S_{\text{effective}} = |P_{\text{fill}} - \text{Mid}(t_{\text{fill}})|$$
3. **Realized Spread (at horizon $k$)**:
   $$S_{\text{realized}}(k) = S_{\text{effective}} - \text{Adverse Selection}(k) = \text{Dir} \times (P_{\text{fill}} - \text{Mid}(t + k))$$

A strategy is viable **if and only if** $S_{\text{realized}}(k) > \text{Maker Fee}$ across the holding duration.

---

## 11. FEE & REBATE MODEL

Fee schedules vary significantly across tiers and jurisdictions. The simulator must enforce realistic, non-optimistic fee configurations:

| Venue / Tier | Maker Fee / Rebate ($c_{\text{maker}}$) | Taker Fee ($c_{\text{taker}}$) | Volume Threshold (30-day) |
|---|---|---|---|
| **Binance.US (Tier 0 / Baseline)** | $+1.5\text{ bps}$ (fee) | $10.0\text{ bps}$ | $\$0$ (Retail) |
| **Binance.US (Tier 2)** | $+0.5\text{ bps}$ (fee) | $7.5\text{ bps}$ | $>\$50\text{K}$ |
| **Coinbase Advanced (Tier 1)** | $+4.0\text{ bps}$ (fee) | $6.0\text{ bps}$ | $<\$10\text{K}$ |
| **Tier-1 VIP / Institutional** | $-0.5\text{ bps}$ (rebate) | $3.0\text{ bps}$ | High Volume ($>\$10\text{M}$) |

* **Research Baseline**: The primary evaluation must use **$+1.5\text{ bps}$ maker fee** (Binance.US Retail Tier 0) to avoid relying on hypothetical institutional maker rebates.

---

## 12. INVENTORY MODEL & CARRYING RISK

Passive market making inevitably accumulates asymmetric inventory when one side fills faster than the other.
* **Inventory State**: $I(t) = \sum \text{Fills}_{\text{buy}} - \sum \text{Fills}_{\text{sell}}$.
* **Maximum Inventory Cap**: $|I(t)| \le I_{\text{max}}$ (e.g. $\$10,000$ or $10\%$ of portfolio).
* **Inventory Carrying Cost**: Modeled mark-to-market variance drag:
  $$\text{Drag}_{\text{inventory}} = \gamma \cdot \sigma_{\text{mid}} \cdot I(t)^2$$
* **Liquidation Protocols**:
  1. *Passive Decay*: Quoting skewed to attract offsetting trades.
  2. *Aggressive Stop-Out*: If $|I(t)| > I_{\text{max}}$ or holding time exceeds $T_{\text{max}}$ (e.g., 15 minutes), an aggressive taker market order is fired, paying full taker fees and crossing the spread.

---

## 13. QUOTE STRATEGIES (PREREGISTERED FAMILIES)

Four distinct quoting families are pre-registered:

### Family A: Static Inside Quoting
* Post at current Best Bid and Best Ask ($P_{\text{bid}}^*, P_{\text{ask}}^*$).
* Cancel and replace whenever the inside market shifts.

### Family B: Spread-Aware Quoting
* Only quote if $S_{\text{quoted}}(t) \ge S_{\text{min}}$ (e.g. $\ge 6.0\text{ bps}$).
* As spread widens, quote deeper within the spread or at inside levels to capture wider margin.

### Family C: Microstructure & Flow-Aware Quoting
* Adjust quote placement and cancellation dynamically:
  - If Book Imbalance $> +0.3$ (heavy bids), widen ask or abstain from asking; tighten bid.
  - If Trade Flow is strongly aggressive sell, cancel bid immediately to avoid adverse fill.

### Family D: Inventory-Aware Skew Quoting (Avellaneda-Stoikov Framework)
* Adjust reservation price $r(s, q)$ based on accumulated inventory $q$:
  $$r(s, q) = s - q \cdot \gamma \cdot \sigma^2$$
  $$\delta_{\text{bid}} = r - P_{\text{bid}}, \quad \delta_{\text{ask}} = P_{\text{ask}} - r$$
* Long inventory lowers the bid and lowers the ask to encourage inventory depletion.

---

## 14. HYPOTHESIS REGISTRY

Seven formal hypotheses are pre-registered in `phase10a/hypothesis_registry.py`:
* **P10A-H01**: Positive Realized Spread After Maker Fees ($S_{\text{realized}} > c_{\text{maker}}$).
* **P10A-H02**: Queue Position Determinism of Realized Profitability ($\Delta\text{Markout}_{\text{front vs back}} \ge 2.0\text{ bps}$).
* **P10A-H03**: Adverse Selection Offsets $\ge 60\%$ of Quoted Half-Spread.
* **P10A-H04**: Microstructure-Conditioned Quoting yields $\ge +2.5\text{ bps}$ net edge over static quoting.
* **P10A-H05**: Inventory-Aware Quoting reduces inventory drag by $\ge 40\%$.
* **P10A-H06**: Positive Net Expectancy Under Conservative Fill & Latency Models ($> 0.0\text{ bps}$).
* **P10A-H07**: Passive Edge Robustness Under Stressed Execution Assumptions (Worst-case Net $> 0.0\text{ bps}$).

---

## 15. STATISTICAL METHODOLOGY

* **Stationary Block Bootstrap**: Resample continuous blocks of event data (block length: 15 to 30 minutes, capturing queue state autocorrelation).
* **Multiple Testing Control**: Holm-Bonferroni and Benjamini-Hochberg False Discovery Rate (FDR) across all strategy configurations.
* **Confidence Intervals**: 95% studentized bootstrap confidence intervals for mean net expectancy and realized spread.

---

## 16. TRAIN / VALIDATION / HOLDOUT DESIGN

Event datasets must be chronologically partitioned:
* **Development Split (60%)**: Initial strategy formulation and latency sensitivity testing.
* **Validation Split (20%)**: Cross-validation of quoting policies, inventory limits, and abstention rules.
* **Sealed Holdout Partition (20%)**: Cryptographically hashed and locked. Evaluated exactly **once** after strategy specifications and parameter sets are permanently frozen.

---

## 17. ECONOMIC GATES

To pass Phase 10A, a passive execution strategy must clear seven mandatory gates:
1. **Gate A: Positive Net Expectancy**: Net expectancy $> 0.0\text{ bps}$ per executed round trip after all fees, markout, and inventory liquidations.
2. **Gate B: Robust Parameter Stability**: Edge must not exist only at a single hyper-parameter point.
3. **Gate C: Out-of-Sample Survival**: Validation net expectancy must be positive ($p < 0.01$).
4. **Gate D: Sealed Holdout Verification**: Uncontaminated holdout net expectancy $> 0.0\text{ bps}$.
5. **Gate E: Stress Survival**: Net expectancy remains positive under the Phase 10A Stress Matrix.
6. **Gate F: Drawdown Safety**: Maximum drawdown within pre-registered portfolio tolerance ($< 5\%$).
7. **Gate G: Fill Realism**: Realistic fill rates ($< 60\%$ fill rate for passive limit orders at top of book).

---

## 18. STRESS TEST MATRIX

Every candidate model must be evaluated against the Stress Test Matrix:

| Stress Dimension | Baseline Specification | Stressed Specification | Permissible Degradation |
|---|---|---|---|
| **Fill Probability** | Modeled Queue Depletion | $-10\%$ fill multiplier | Net Expectancy $> 0.0\text{ bps}$ |
| **Round-Trip Latency** | $\approx 45\text{ ms}$ | $+25\%$ ($\approx 56\text{ ms}$) | Net Expectancy $> 0.0\text{ bps}$ |
| **Quoted Spread** | Observed Market Spread | Degraded by $-15\%$ | Net Expectancy $> 0.0\text{ bps}$ |
| **Adverse Selection** | Observed Markout | $+25\%$ increased drift | Net Expectancy $> 0.0\text{ bps}$ |
| **Queue Position** | Actual FIFO Entry | Artificially moved 1 tercile back | Net Expectancy $> 0.0\text{ bps}$ |
| **Taker Liquidation Fee** | $10.0\text{ bps}$ | $+25\%$ ($12.5\text{ bps}$) | Net Expectancy $> 0.0\text{ bps}$ |

---

## 19. SAFETY REQUIREMENTS & HARD ARCHITECTURAL GUARDS

The repository must maintain absolute isolation from production trading infrastructure:
```python
PAPER_TRADING_ONLY = True
USE_LIVE_JEV = False
LEVERAGE = 1.0
LIVE_ORDERS = 0
WALLET_CONNECTIONS = 0
PRIVATE_KEYS = 0
```
* No exchange private keys or trading API secrets in code or environment variables.
* `RESEARCH_FREEZE.md` remains strictly preserved and untouched.

---

## 20. FAILURE CRITERIA (FORMAL REJECTION OF PASSIVE HYPOTHESIS)

The passive execution hypothesis will be formally **REJECTED** if:
1. Net expectancy per round trip remains $\le 0.0\text{ bps}$ after adverse selection and maker fees.
2. Adverse selection consistently offsets $> 90\%$ of quoted spread across all assets.
3. Inventory liquidation costs exceed cumulative spread capture.
4. Latency degradation to $60\text{ ms}$ turns an otherwise marginal positive edge into negative net expectancy.

---

## 21. RESEARCH LIMITATIONS

1. **Exchange Queue Invisibility (L3 Data Absence)**: Public crypto feeds provide Level 2 (aggregated depth by price level), not Level 3 (individual order IDs). Queue position within a level is an approximation.
2. **Hidden Orders & Latency Arbitrage**: Institutional high-frequency traders possess co-located sub-millisecond cancellation advantages that cannot be fully replicated via standard public REST/WebSocket APIs.
3. **Cross-Asset Heterogeneity**: SOL and ETH order books may exhibit significantly different queue churn and toxicity compared to BTC.

---

## 22. DECISION TREE FOR SUBSEQUENT IMPLEMENTATION

```text
                                [PHASE 10A RESEARCH SPEC COMPLETE]
                                                 │
                                                 ▼
                              [DATA SUFFICIENCY AUDIT: INSUFFICIENT]
                                                 │
                                                 ▼
                       ┌──────────────────────────────────────────────────┐
                       │  Step 1: Event Data Acquisition (Tick & L2 Book)  │
                       └──────────────────────────────────────────────────┘
                                                 │
                                                 ▼
                                     [DATA INGESTED & VALIDATED]
                                                 │
                                                 ▼
                       ┌──────────────────────────────────────────────────┐
                       │   Step 2: Passive Queue & Fill Simulator Engine   │
                       └──────────────────────────────────────────────────┘
                                                 │
                                                 ▼
                       ┌──────────────────────────────────────────────────┐
                       │  Step 3: Development Evaluation (60% Partition)  │
                       └──────────────────────────────────────────────────┘
                                                 │
                                                 ▼
                       ┌──────────────────────────────────────────────────┐
                       │  Step 4: Pre-Holdout Freeze & Hypothesis Audit   │
                       └──────────────────────────────────────────────────┘
                                                 │
                                                 ▼
                       ┌──────────────────────────────────────────────────┐
                       │  Step 5: Confirmatory Sealed Holdout Evaluation   │
                       └──────────────────────────────────────────────────┘
```

*This specification governs the entirety of Research Program 10A.*
