# PHASE 10B.2 — TRIAL ELIGIBILITY & COVERAGE GAP ASSESSMENT

**Document Identifier**: `phase10b2/reports/trial_eligibility_and_coverage_assessment.md`  
**Provider**: Tardis.dev  
**Platform**: Jev Crypto-Trading Research System  
**Date**: `2026-09-22`  
**Safety Invariants**: `PAPER_TRADING_ONLY = true`, `USE_LIVE_JEV = false`, `LEVERAGE = 1.0`  

---

## 1. PURPOSE OF THIS ASSESSMENT

Phase 10B.1 established that Tardis.dev is the only technically qualified vendor capable of supplying historical Level-2 order-book deltas (`incremental_book_L2`) and tick trades (`trades`) for spot `BTCUSDT`, `ETHUSDT`, and `SOLUSDT` on Binance.US.

Phase 10B.2 evaluates whether this required historical event data can be legitimately obtained through an **Academic / Research Trial** before any paid procurement is contemplated.

---

## 2. TARDIS ACCESS TIERS & EVALUATION MECHANISMS

Our investigation of first-party Tardis documentation and endpoint metadata identified three distinct data access pathways:

| Pathway | Cost | Coverage Window | Requirements | Feasibility for Phase 10A |
|---|---|---|---|---|
| **Free 1st-of-Month Archive** | $0.00 | Single days (1st of each month across history) | None (Public HTTP downloads) | **Insufficient**: Provides isolated 24h slices, cannot provide continuous 30-day queue dynamics. |
| **30-Day Evaluation Trial Key** | $0.00 | Rolling 7 to 14 days of recent event data | Email registration (No payment details required) | **Partially Sufficient**: Excellent for schema verification and preliminary testing, but falls short of 30-day continuous protocol. |
| **Academic Research Grant / Tier** | $0.00 / Discounted | Extended custom historical window (e.g., 30+ days) | Academic affiliation (.edu), research project description, formal application | **Fully Sufficient if approved**: Requires user review and formal application submission. |
| **Commercial Custom Order** | $300.00 min | 30+ consecutive days historical archive | Payment method / commercial order | **Prohibited without user authorization**: No payments made. |

---

## 3. THE 30-DAY CONTINUOUS REQUIREMENT VS. TRIAL SCOPE

The preregistered Phase 10A research protocol specifies a minimum of **30 consecutive calendar days** across multiple market regimes (trending, mean-reverting, volatile) to evaluate passive fill probability, queue depletion, and adverse selection.

1. **Evaluation Trial Capability**:
   - The free evaluation API key allows downloading up to 14 days of continuous tick/L2 data.
   - This provides $\approx 10{,}000{,}000\text{ to }20{,}000{,}000$ events per symbol, sufficient for technical integration and short-window queue simulation, but does not meet the full 30-day requirement.
2. **Academic Access Pathway**:
   - Tardis.dev offers customized academic access for researchers affiliated with universities or recognized research labs upon submission of a research statement.
   - We have fully prepared the required application package in `phase10b2/application/`.
3. **Application Review Gate**:
   - Submitting this application externally requires institutional contact info and applicant sign-off.
   - The application is currently held locally in state `APPLICATION: USER AUTHORIZATION REQUIRED`.

---

## 4. QUEUE GRANULARITY & MICROSTRUCTURE REALITY

An essential finding of Phase 10B.1 and 10B.2 is that Binance.US provides **Market-By-Price (Level 2)** data:
* Individual order IDs are not broadcast on spot WebSocket streams.
* The matching engine broadcasts aggregated volume changes at price levels.
* Queue dynamics must be modeled via **estimated queue position ahead ($Q_{\text{ahead}}$)**:
  - Initial position = total visible depth at target limit price upon order insertion.
  - Position degrades strictly by aggressive fills at that price.
  - Cancellations occurring ahead vs. behind the order must be bounded parametrically (conservative worst-case FIFO assumes cancellations occur behind).
* This provides a scientifically valid, conservative lower bound on fill probability without manufacturing optimistic fills.

---

## 5. ZERO FINANCIAL COMMITMENT INVARIANT

In strict compliance with project directives:
* Financial commitments incurred: **$0.00**
* Subscriptions entered: **0**
* Payment credentials provided: **NONE**
* Live orders placed: **0**
* Live wallets connected: **0**

Phase 10C remains **strictly BLOCKED** until authentic data covering the required continuous period is formally obtained, registered, and validated.
