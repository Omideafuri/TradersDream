# PHASE 10B.2 — ACADEMIC RESEARCH TRIAL & DATA ACCESS VERIFICATION REPORT

**Document Identifier**: `PHASE10B2_ACADEMIC_ACCESS_AND_DATA_ACQUISITION_REPORT.md`  
**Phase**: Phase 10B.2 Academic Research Trial & Data Access Verification  
**Platform**: Jev Crypto-Trading Research System  
**Date**: `2026-09-22T03:55:00+00:00`  
**Safety Invariants**: `PAPER_TRADING_ONLY = true`, `USE_LIVE_JEV = false`, `LEVERAGE = 1.0`  
**Financial Status**: Zero commitments incurred ($0.00 spent, zero payment methods entered)  
**Submission Status**: `APPLICATION READY FOR USER REVIEW — EXTERNAL SUBMISSION PENDING EXPLICIT USER AUTHORIZATION`  

---

## 1. TARDIS.DEV ACADEMIC STATUS & EVALUATION SUMMARY

Phase 10B.1 qualified **Tardis.dev** as the sole candidate vendor providing continuous historical tick-by-tick trades and Level-2 order-book deltas for spot cryptocurrency instruments.

In Phase 10B.2, an exhaustive investigation of Tardis.dev's academic trial and evaluation programs was conducted using official first-party documentation, API endpoint schemas, and data catalogs:
* **Academic Program Status**: Tardis provides recognized academic research discounts and custom research data access grants for accredited academic institutions and non-commercial quantitative researchers.
* **Evaluation Trial Availability**: A free 30-day evaluation trial API key is available via standard registration without requiring credit card or payment information.
* **Sample Data Availability**: Fully open, unauthenticated sample archives covering the first day of every historical month are publicly downloadable for schema verification.

---

## 2. ELIGIBILITY REQUIREMENTS

Qualifying for the formal academic program requires satisfying several objective verification criteria:
1. **Accredited Institution Affiliation**: The applicant or institution must be an accredited university, college, or recognized non-profit academic research laboratory.
2. **Institutional Email Domain**: Inquiries and applications must originate from an authentic institutional domain (`.edu`, `.ac.uk`, or recognized research institute domain).
3. **Non-Commercial Research Purpose**: The research scope must be strictly non-commercial, focused on quantitative backtesting, market microstructure modeling, and peer-reviewed or publicly archived academic methodology.
4. **Non-Redistribution Agreement**: The applicant must formally commit to zero redistribution of raw market-event data.
5. **Mandatory Attribution**: All resulting publications, preprints, and reports must include formal citation and attribution to Tardis.dev.

---

## 3. TRIAL TERMS & EVALUATION SCOPE

The standard evaluation trial offers the following parameters:
* **Duration**: 30 calendar days of active trial API key validity.
* **Historical Reach**: Rolling window of the most recent 7 to 14 days of full tick/L2 event data across all supported venues.
* **Rate Limits**: Programmatic API access throttled to reasonable evaluation limits.
* **Payment Credentials**: **$0.00 cost; strictly zero payment credentials required**. No automatic conversion into a paid subscription occurs upon expiration.

---

## 4. COMMERCIAL PRICING STRUCTURE & MINIMUMS

If an academic grant is not awarded or if historical coverage requirements exceed the free evaluation scope:
* **Commercial Minimum Order**: Tardis requires a minimum commercial order of **$300.00 USD** for historical on-demand data downloads.
* **Subscription Pricing**: Standard commercial plans start at approximately $300 to $600/month for single-venue access.
* **Academic Pricing**: Discounted rates or custom research access packages are determined case-by-case upon evaluation of the application package.
* **Current Action**: **No commercial purchase has been made or authorized.**

---

## 5. APPLICATION MATERIALS PREPARED

To ensure full compliance and rapid turnaround upon user authorization, complete application materials were prepared and saved locally in `phase10b2/application/`:
1. `phase10b2/application/research_project_description.md`:
   - Outlines the scientific inquiry into passive execution economics, queue-aware fill modeling, adverse selection markouts, and transaction-cost hurdles.
   - Strictly highlights non-live trading constraints and non-commercial methodology.
2. `phase10b2/application/requested_dataset.md`:
   - Formally specifies the target instruments, data channels, required fields, and timeframes.
3. `phase10b2/application/data_usage_statement.md`:
   - Details commitments regarding non-redistribution, local workstation security, citation standards, and signature blocks.
4. **Current Submission State**:
   - `APPLICATION: USER AUTHORIZATION REQUIRED`. No materials have been submitted to any external endpoint.

---

## 6. EXACT DATASETS REQUESTED

The research protocol requires two synchronized streaming event datasets:
1. `incremental_book_L2`:
   - Initial depth snapshots (`is_snapshot = true`) establishing the full resting ladder.
   - Price-level updates (`is_snapshot = false`) conveying add/modify/delete depth changes.
2. `trades`:
   - Individual executed transactions.
   - Explicit aggressor classification (`side`: `buy` vs. `sell`) to drive queue depletion.

---

## 7. EXCHANGE COVERAGE VERIFICATION

* **Target Venue**: Binance.US (`binance-us`).
* **Active Recording Date**: Continuously captured and recorded by Tardis since **2019-09-25T00:00:00.000Z**.
* **Collection Infrastructure**: Recorded directly from the official WebSocket endpoint (`wss://stream.binance.us:9443/stream`) via low-latency co-located recording nodes.

---

## 8. SYMBOLS VERIFIED

Three primary liquid spot pairs were qualified and confirmed available in the Tardis catalog:
* `BTCUSDT`: Recorded continuously from `2019-09-25` to present.
* `ETHUSDT`: Recorded continuously from `2019-09-25` to present.
* `SOLUSDT`: Recorded continuously from `2020-09-18` to present.

All three assets possess the requisite multi-year historical depth to extract any requested historical month.

---

## 9. TIMESTAMP SEMANTICS

The Tardis event schema provides two distinct timestamp coordinates with microsecond resolution:
1. `timestamp` ($\mu\text{s}$): The matching engine execution or event timestamp generated by the exchange. Converted to milliseconds for order-book alignment (`exchange_timestamp_ms`).
2. `local_timestamp` ($\mu\text{s}$): The precise timestamp at which the WebSocket packet arrived at the recording network interface. Enables empirical modeling of packet transport latency and network jitter.

---

## 10. SEQUENCE SEMANTICS & ATOMIC MESSAGE BATCHING

Binance.US broadcasts incremental L2 deltas grouped within discrete WebSocket messages.
* **Atomic Batching**: Multiple price-level updates arriving within the same WebSocket payload share an identical `local_timestamp`.
* **State Integrity**: As engineered in `phase10b/reconstructor.py`, order book integrity is evaluated at the end of each atomic batch rather than mid-batch, preventing spurious crossed-book artifacts during multi-level book updates.

---

## 11. 30-DAY COVERAGE ASSESSMENT

* **Preregistered Requirement**: Phase 10A mandates a minimum continuous window of **30 consecutive calendar days** across multiple regimes.
* **Evaluation Trial Reality**: The free self-serve evaluation trial provides **7 to 14 days** of continuous rolling data.
* **Free Monthly Samples Reality**: The free sample archive provides the 1st of every month across history, but does NOT provide continuous 30-day blocks.
* **Coverage Gap**:
  - The evaluation trial is sufficient for pipeline integration, schema validation, and 14-day preliminary queue simulation.
  - Full 30-day continuous backtesting requires either an approved formal academic research access extension or paid dataset procurement ($300 minimum order).

---

## 12. LICENSING & NON-REDISTRIBUTION COVENANTS

Tardis licensing terms strictly govern historical market data:
* **Zero Raw Redistribution**: Raw or parsed tick-level datasets cannot be redistributed, shared publicly, or uploaded to public repositories.
* **Permitted Academic Publication**: Researchers may publish derived aggregates, figures, summary statistics, and quantitative model evaluations provided Tardis is cited as the market data provider.
* **Compliance Invariant**: Raw datasets will reside exclusively on local storage within `.gitignore` protected paths.

---

## 13. SAMPLE VALIDATION & ENGINE COMPATIBILITY

Inspection of sample Tardis CSV structures confirms complete drop-in compatibility with the Phase 10B infrastructure:
```text
trades: exchange,symbol,timestamp,local_timestamp,id,side,price,amount
incremental_book_L2: exchange,symbol,timestamp,local_timestamp,is_snapshot,side,price,amount
```
* Fits `phase10b.models.TickTrade` directly via `id`, `side`, `price`, `amount`, and `timestamp`.
* Fits `phase10b.models.L2Snapshot` and `phase10b.models.L2Delta` via `is_snapshot`, `price`, `amount`, and `timestamp`.
* Price-level deletion semantics (`amount == 0.0`) match the logic implemented in `OrderBookReconstructor.apply_delta()`.

---

## 14. QUEUE GRANULARITY CLASSIFICATION

A critical market-microstructure finding for spot crypto exchanges:
* **Feed Classification**: **Market-By-Price (Level 2 / MBP)**.
* **Order ID Availability**: Spot Binance.US does NOT publish individual order IDs or order-level cancellations (Level 3 / MBO).
* **Queue Model Classification**: Queue priority must be strictly classified as **`ESTIMATED QUEUE-AHEAD ($Q_{\text{ahead}}$)`**, not `EXACT ORDER-LEVEL FIFO`.
* **Scientific Implication**:
  - Passive order placement records visible depth at the price level as queue-ahead.
  - Aggressive fills at that level deplete queue-ahead.
  - Fills occur only when cumulative aggressive volume exceeds $Q_{\text{ahead}}$.
  - Cancellations ahead of our order are conservatively assumed to be zero (worst-case FIFO queue degradation), preventing optimistic fill bias.

---

## 15. ADVERSE SELECTION FEASIBILITY

With microsecond matching engine timestamps and tick-by-tick aggressor flags:
* Post-fill markouts can be calculated with sub-second precision:
  $$\text{Markout}(\tau) = \text{Mid}(t + \tau) - P_{\text{fill}}$$
* Horizons supported: $\tau \in \{100\text{ ms}, 500\text{ ms}, 1\text{ s}, 5\text{ s}, 30\text{ s}, 5\text{ min}\}$.
* Adverse selection can be directly regressed against fill size, queue wait time, and contemporaneous order-flow imbalance (OFI).

---

## 16. COST ANALYSIS

| Pathway | Upfront Cost | Continuous 30-Day Coverage | Academic Viability |
|---|---|---|---|
| **Academic Trial / Grant** | **$0.00** | Full 30 days if granted by Tardis | **Primary Target** (Requires User Application Submission) |
| **Self-Serve Evaluation Trial** | **$0.00** | 7–14 days rolling | Viable for technical verification; sub-protocol duration |
| **Commercial Purchase** | **$300.00 min** | Full 30 days guaranteed | Contingency only; requires explicit user funding authorization |

---

## 17. PAYMENT REQUIREMENT & INVARIANT STATUS

* Is payment required for commercial continuous 30-day download? **YES ($300.00 min)**.
* Can continuous 30-day data be granted without payment? **YES (subject to Tardis academic review)**.
* Have any payments been made? **NO ($0.00 spent)**.
* Have payment credentials been entered? **NO (Zero credit cards or banking info entered)**.

---

## 18. SAFETY INVARIANTS VERIFICATION

The platform continues to operate under verified safety invariants:
```python
PAPER_TRADING_ONLY = True
USE_LIVE_JEV = False
LEVERAGE = 1.0
LIVE_ORDERS = 0
WALLET_CONNECTIONS = 0
PRIVATE_KEYS = 0
```
All Phase 10B.2 work has been conducted entirely within local configuration and documentation files.

---

## 19. RESEARCH FREEZE INTEGRITY

* `RESEARCH_FREEZE.md` remains completely unmodified and intact.
* Phases 1–8 remain permanently frozen.
* Phase 9 remains formally closed and sealed.
* No predictive strategy parameters or trading logic have been modified.

---

## 20. NEXT PERMITTED ACTION & DECISION GATE

```text
STATUS:
  ACADEMIC TRIAL STATUS: QUALIFIED
  APPLICATION PACKAGE: PREPARED
  SUBMISSION: NOT SUBMITTED — USER AUTHORIZATION REQUIRED
  FINANCIAL COMMITMENTS: $0.00
  PHASE 10C READINESS: BLOCKED

NEXT PERMITTED ACTION:
  User review of application package in phase10b2/application/.
  Upon user authorization, submit academic research application to Tardis.dev.
  Do NOT proceed to Phase 10C until continuous authentic event data is acquired and validated.
```
