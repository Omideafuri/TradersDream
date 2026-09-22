# PHASE 10B.3: SCIENTIFIC APPLICATION & PROVENANCE AUDIT REPORT

**Document Identifier**: `phase10b3/reports/application_audit.md`  
**Phase**: Phase 10B.3 Academic Data Access Application & Approval Gate  
**Date**: `2026-09-22T04:30:00+00:00`  
**Scope**: Scientific alignment with Phase 10A, Minimum-Data Principle, Timestamp semantics, and Hash/Provenance Integrity  

---

## 1. SCIENTIFIC AUDIT AGAINST PHASE 10A PREREGISTERED PROTOCOL

The application package was audited against `PHASE10A_PASSIVE_EXECUTION_RESEARCH_SPEC.md` to ensure complete fidelity to the preregistered research protocol:

| Protocol Requirement | Application Package Alignment | Status |
|---|---|---|
| **Passive / Maker Economics** | Accurately models spread capture, maker fees/rebates, and adverse selection markouts | **COMPLIANT** |
| **Queue Depletion** | Limits fills to trades that deplete visible queue depth ahead ($Q_{\text{ahead}}$) | **COMPLIANT** |
| **Adverse Selection Horizons** | Explicitly defines markout windows $\tau \in [100\text{ ms}, 5\text{ s}, 30\text{ s}, 5\text{ min}]$ | **COMPLIANT** |
| **Inventory & Liquidation Drag** | Includes inventory variance drag and aggressive taker unwinding costs | **COMPLIANT** |
| **Falsification Gates** | Explicitly references hypotheses `P10A-H01` through `P10A-H07` | **COMPLIANT** |
| **Zero Profitability Claims** | Stripped of all claims of guaranteed alpha, profitability, or live deployment | **COMPLIANT** |
| **Target Universe** | Spot `BTCUSDT`, `ETHUSDT`, `SOLUSDT` on Binance.US | **COMPLIANT** |
| **Coverage Duration** | Strictly requires **30 consecutive calendar days**; rejects shortening | **COMPLIANT** |

---

## 2. MINIMUM-DATA PRINCIPLE AUDIT

Every requested data field and channel was audited to ensure zero extraneous or proprietary data is requested:
* **Requested Streams**:
  1. `trades`: Required for trade matching, aggressor classification, and queue depletion.
  2. `incremental_book_L2`: Required for ladder reconstruction and tracking depth ahead.
* **Excluded / Omitted Streams**:
  - `book_ticker`: Omitted (redundant with L2 top levels).
  - `aggTrade`: Omitted (individual trades required for microsecond queue depletion).
  - `options_chain`, `derivative_ticker`, `liquidations`: Omitted (spot focus).
* **Verdict**: The request strictly conforms to the **minimum-data principle**.

---

## 3. QUEUE GRANULARITY CLASSIFICATION AUDIT

* **Audited Finding**:
  - Exchange data from Binance.US is **Level 2 Market-By-Price (MBP)**.
  - Individual order IDs and individual order cancellations are not broadcast.
  - The application strictly disclaims exact order-level FIFO priority.
  - The application explicitly defines queue priority as **queue-ahead estimation ($Q_{\text{ahead}}$)** under aggregated depth.

---

## 4. HASH & PROVENANCE INTEGRITY AUDIT

### 4.1 Investigation of `sample_manifest.json` Hash
During the provenance audit of `phase10b1/manifests/sample_manifest.json`, the following entry was scrutinized:
```json
"file_size_bytes": 482910,
"sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
```

### 4.2 Forensic Analysis:
1. **Empty String Hash**:
   - `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` is the exact SHA-256 hash of a **zero-byte sequence** (`hashlib.sha256(b"").hexdigest()`).
2. **Physical File Existence**:
   - An exhaustive filesystem scan confirmed that the file `binance-us_incremental_book_L2_2024-03-01_BTCUSDT.csv.gz` does **NOT** exist locally in the repository.
3. **Root Cause**:
   - In Phase 10B.1, `sample_manifest.json` was authored as a **schema demonstration template / structural specification** illustrating target field mappings before actual data acquisition.
   - The file size (`482910`) represented an estimated sample file size, while the hash was populated with an unhashed empty-string default.
4. **Audit Finding**:
   - **This hash CANNOT and MUST NOT be treated as proof of a non-empty physical sample or downloaded dataset.**
   - No historical market data was downloaded or verified under that hash.
   - The historical artifact is preserved for audit traceability, but is formally flagged as a **structural placeholder**.
   - True physical dataset validation remains strictly gated by Phase 10B.

---

## 5. AUDIT SUMMARY & CORRECTIONS APPLIED

| Area | Phase 10B.2 State | Phase 10B.3 Corrected State |
|---|---|---|
| **User Identity** | Generic team name | Explicit `[USER INPUT REQUIRED]` placeholders for name, title, institution, email |
| **Coverage Requirement** | Offered 14-day alternative trial | Strictly locked to **30 consecutive calendar days** (Phase 10A mandatory requirement) |
| **Pricing Assertion** | Cited "$300 minimum order" | Formally classified as **`UNVERIFIED`** based on first-party subscription terms |
| **Academic Grant Assertion** | Assumed formal $0 grant program | Formally classified as **`UNVERIFIED`**; documented as paid quarterly/yearly tier |
| **Queue Priority** | Mentioned FIFO ladder | Formally restricted to **L2 queue-ahead estimation ($Q_{\text{ahead}}$)** |
| **Submission State** | Pending | Formally gated: `READY FOR USER REVIEW — EXTERNAL SUBMISSION NOT PERFORMED` |
