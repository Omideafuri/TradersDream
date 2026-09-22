# PHASE 10B.3: FIRST-PARTY PROVIDER VERIFICATION REPORT

**Document Identifier**: `phase10b3/reports/provider_verification.md`  
**Provider Investigated**: Tardis.dev  
**Authoritative Documentation Sources**:
* `https://docs.tardis.dev/faq/general.md`
* `https://docs.tardis.dev/faq/billing-and-subscriptions.md`
* `https://docs.tardis.dev/downloadable-csv-files/data-types.md`
* `https://docs.tardis.dev/legal/terms-of-service.md`
* `https://docs.tardis.dev/historical-data-details/binance-us.md`
* `https://api.tardis.dev/v1/exchanges/binance-us`

**Audit Timestamp**: `2026-09-22T04:30:00+00:00`  
**Auditor Classification**: Quantitative Research & Compliance Audit  

---

## 1. ACCESS MODEL & ACADEMIC STATUS VERIFICATION

### 1.1 Academic Subscription Tier
* **Status**: **VERIFIED (CONDITIONAL)**
* **Documented Policy**:
  - Tardis.dev offers a distinct **"Academic"** subscription type alongside Solo, Professional, and Business tiers.
  - "Academic subscriptions are available with **quarterly or yearly billing** and require confirmation of eligibility, for example using a university email address." (Monthly billing is NOT available for Academic).
  - Scope: Academic subscriptions provide access to **downloadable CSV files only** (Raw replay API and Tardis Machine are excluded).
  - Historical reach: Quarterly billing provides 12 months of historical data; yearly billing provides 4 years.
  - **Discounts**: Tardis explicitly states: *"No. We do not provide discounts, but we offer different subscription types for solo traders, academic users, professionals and businesses."*

### 1.2 Independent / Solo Researcher Access
* **Eligibility**: An independent/solo researcher can subscribe to the **Solo** tier or apply for an **Academic** subscription if they have an accredited university affiliation or institutional email. Without institutional proof, academic tier access cannot be guaranteed.

### 1.3 Free Evaluation Trial
* **Status**: **VERIFIED**
* **Documented Scope**:
  - Active for 30 days.
  - Grants access to a randomly selected **7–14-day range** of recent historical data (starts/ends at 00:00 UTC).
  - Cost: **$0.00**; requires zero payment details and does NOT convert into a paid subscription.
  - Evaluation trial provides 7–14 days, which is **insufficient** for the 30-day continuous requirement of Phase 10A.

### 1.4 Free Sample Data
* **Status**: **VERIFIED**
* **Documented Scope**:
  - Unauthenticated historical CSV datasets for the **first day of each month** across history are freely downloadable without an API key (e.g. `2019/12/01`, `2024/03/01`).
  - While valuable for schema validation, isolated single days cannot satisfy a 30-day continuous backtest.

### 1.5 Research Grant Program
* **Status**: **UNVERIFIED FROM FIRST-PARTY DOCUMENTATION**
* **Documented Finding**: First-party documentation does NOT advertise a standing formal "$0 research data grant" program. Academic access is documented as a paid subscription tier (quarterly or yearly) with eligibility verification. Any custom data grant is at provider discretion via contact inquiry.

---

## 2. HISTORICAL DATA AVAILABILITY & TECHNICAL ATTRIBUTES

### 2.1 Venue & Symbol Coverage
* **Binance.US Spot (`binance-us`)**:
  - Tracked continuously since **2019-09-25**.
  - `BTCUSDT`: Continuously available from 2019-09-25.
  - `ETHUSDT`: Continuously available from 2019-09-25.
  - `SOLUSDT`: Continuously available from 2020-09-18.
  - 30-day historical depth: **VERIFIED AVAILABLE**.

### 2.2 Channels & Event Streams
* `trades`:
  - Format: CSV (`exchange,symbol,timestamp,local_timestamp,id,side,price,amount`).
  - Aggressor side (`side`): Explicitly identified as `buy` or `sell`.
  - Resolution: Microseconds since epoch.
* `incremental_book_L2`:
  - Format: CSV (`exchange,symbol,timestamp,local_timestamp,is_snapshot,side,price,amount`).
  - Snapshots: Periodic / initial snapshots marked with `is_snapshot=true` (top 1000 levels sourced from `@depthSnapshot`).
  - Updates: Price level deltas marked with `is_snapshot=false`; `amount=0.0` represents price-level deletion.

---

## 3. TIMESTAMP SEMANTICS AUDIT

A rigorous examination of documented timestamps establishes the following taxonomy:

| Timestamp Category | Tardis Field / Attribute | Documented Resolution | Physical Meaning | Availability |
|---|---|---|---|---|
| **Exchange Event Timestamp** | `timestamp` | Microsecond ($\mu\text{s}$) | Matching engine event timestamp provided by Binance.US WebSocket | **VERIFIED AVAILABLE** |
| **Local Receive Timestamp** | `local_timestamp` | Microsecond ($\mu\text{s}$) | Arrival timestamp at Tardis London GCP capture interface | **VERIFIED AVAILABLE** |
| **Atomic Batch Identifier** | `local_timestamp` grouping | Microsecond ($\mu\text{s}$) | Identifies updates delivered within a single WebSocket message | **VERIFIED AVAILABLE** |
| **Internal Order Match Sequence** | N/A | N/A | Sub-event sequence within exchange matching engine | **NOT AVAILABLE** |
| **Order-Level Cancellation Time** | N/A | N/A | Timestamp of specific resting order cancellations | **NOT AVAILABLE** (L2 only) |
| **Network Client Transit Latency** | N/A | N/A | One-way latency from local workstation to exchange engine | **NOT AVAILABLE** (Must be modeled) |
| **Simulation Order Fill Timestamp** | N/A | N/A | Time of hypothetical simulated limit order execution | **NOT AVAILABLE** (Must be modeled) |

---

## 4. DATA GRANULARITY AUDIT: L2 (MBP) VS. L3 (MBO)

* **Binance.US Spot Feed**: Strictly **Market-By-Price (Level 2 / MBP)**.
* **Order ID Availability**: Spot Binance.US does NOT publish individual order IDs.
* **Queue Modeling Constraint**:
  - The research cannot use exact order-level FIFO priority.
  - The research **must strictly use queue-ahead estimation ($Q_{\text{ahead}}$)** under Level-2 market-by-price aggregated depth.

---

## 5. PRICING & COMMERCIAL TERMS VERIFICATION

* **Previous "$300 Minimum Order" Claim**:
  - Status: **UNVERIFIED FROM FIRST-PARTY DOCUMENTATION**.
  - Documented Finding: Tardis documentation explicitly states: *"Historical data is available through subscriptions; we do not sell fixed date ranges or prepare custom data exports."*
  - Billing intervals: Academic tier is available on **quarterly or yearly billing** via Paddle.
  - Any fixed one-off commercial export claim cannot be confirmed from current documentation and is classified as `UNVERIFIED`.
* **Current Financial Commitment**: **$0.00 spent; zero payment methods entered**.

---

## 6. LICENSING & TERMS OF SERVICE VERIFICATION

Documented in `https://docs.tardis.dev/legal/terms-of-service.md`:
* **Clause 9.1 (Permitted Use)**: Internal non-commercial academic research, market microstructure simulation, backtesting.
* **Clause 9.2 (Redistribution)**: Prohibition on redistributing raw data or files. Permitted redistribution of Derived Data at $\ge 10$-minute resolution or aggregated statistics where raw data cannot be reconstructed.
* **Clause 9.4 (Perpetual Internal License)**: Data downloaded during authorized access retains a perpetual license for internal research.
* **Clause 9.5 (AI & Machine Learning)**: Permits task-specific quantitative and statistical trading models for internal use; strictly prohibits using data to train, fine-tune, or benchmark general-purpose foundation AI models or LLMs.
