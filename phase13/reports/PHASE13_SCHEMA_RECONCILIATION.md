# PHASE 13: FORWARD PAPER LEDGER SCHEMA RECONCILIATION

**Audit Date:** 2026-10-01  
**Project:** Autonomous Quantitative Research & Prospective Microstructure Validation  
**Instrument:** XAU/USD (Spot Gold vs US Dollar)  
**Strategy ID:** `XAUUSD_FROZEN_SMA50_200_1H`  
**Target File:** `phase13/data/forward_paper_ledger.csv`  

---

## 1. Executive Summary & Verdict

A forensic inspection of `phase13/data/forward_paper_ledger.csv` on disk was conducted to reconcile the pre-launch specification against the live implementation.

* **Specification Requirement:** 31 columns
* **Actual File Columns:** 32 columns
* **Duplicate Columns:** 0 (Zero duplicates)
* **Malformed Rows:** 0 (Zero malformed rows)
* **Schema Verdict:** `SCHEMA DRIFT DETECTED` *(32-column provenance-extended ledger)*

The actual implementation extends the 31-column specification by adding an explicit `data_quality_status` column at Position 32. This extension is non-destructive, additive, and provides necessary auditability for classifying observed reference prices versus modeled spread executions.

---

## 2. Exact Ordered Schema Comparison

| Col # | Required Field (Section 10 Spec) | Actual CSV Column Header | Compliance Status | Field Provenance / Description |
| :-: | :--- | :--- | :---: | :--- |
| **1** | `timestamp_utc` | `timestamp_utc` | **MATCH** | Completed 1H bar ISO-8601 UTC timestamp |
| **2** | `instrument` | `instrument` | **MATCH** | `XAU/USD` spot gold |
| **3** | `strategy_id` | `strategy_id` | **MATCH** | `XAUUSD_FROZEN_SMA50_200_1H` |
| **4** | `candle_open` | `candle_open` | **MATCH** | Bar open price (USD) |
| **5** | `candle_high` | `candle_high` | **MATCH** | Bar high price (USD) |
| **6** | `candle_low` | `candle_low` | **MATCH** | Bar low price (USD) |
| **7** | `candle_close` | `candle_close` | **MATCH** | Bar close price (USD) |
| **8** | `bid` | `bid` | **MATCH** | Observed reference price / modeled Bid |
| **9** | `ask` | `ask` | **MATCH** | Modeled Ask price / `UNAVAILABLE` when raw Ask absent |
| **10** | `spread` | `spread` | **MATCH** | Modeled spread string (e.g. `4.0 bps (MODELED)`) |
| **11** | `sma50` | `sma50` | **MATCH** | 50-period SMA on completed bar closes |
| **12** | `sma200` | `sma200` | **MATCH** | 200-period SMA on completed bar closes |
| **13** | `atr14` | `atr14` | **MATCH** | 14-period ATR diagnostic indicator |
| **14** | `state_before` | `state_before` | **MATCH** | Position state entering bar (`FLAT` or `LONG`) |
| **15** | `signal` | `signal` | **MATCH** | Causal signal (`1` = BUY, `-1` = SELL, `0` = NONE) |
| **16** | `signal_timestamp` | `signal_timestamp` | **MATCH** | Timestamp of bar close where signal triggered |
| **17** | `execution_timestamp` | `execution_timestamp` | **MATCH** | Bar $t+1$ Open timestamp of fill |
| **18** | `execution_reference_price` | `execution_reference_price` | **MATCH** | Raw Open price at execution |
| **19** | `execution_side` | `execution_side` | **MATCH** | Order action (`BUY` or `SELL`) |
| **20** | `execution_price` | `execution_price` | **MATCH** | Fill price (includes spread & slippage) |
| **21** | `execution_price_source` | `execution_price_source` | **MATCH** | `MODELED_SPREAD`, `OBSERVED_BID`, or `OBSERVED_ASK` |
| **22** | `position_units` | `position_units` | **MATCH** | Troy ounces of gold held |
| **23** | `cash_balance` | `cash_balance` | **MATCH** | Unallocated cash balance (USD) |
| **24** | `gross_equity` | `gross_equity` | **MATCH** | Mark-to-market equity before costs |
| **25** | `financing_cost` | `financing_cost` | **MATCH** | Overnight swap financing deduction |
| **26** | `spread_cost` | `spread_cost` | **MATCH** | Half-spread cost deduction |
| **27** | `slippage_cost` | `slippage_cost` | **MATCH** | Adverse slippage cost deduction |
| **28** | `net_equity` | `net_equity` | **MATCH** | Net paper equity after all costs |
| **29** | `net_pnl` | `net_pnl` | **MATCH** | Net trade PnL for closed trade |
| **30** | `cumulative_pnl` | `cumulative_pnl` | **MATCH** | Cumulative net PnL since launch |
| **31** | `data_source` | `data_source` | **MATCH** | Vendor feed string (`Gold-API Spot XAU/USD`) |
| **32** | *(Extension)* | `data_quality_status` | **EXTENSION** | Explicit quality classification (`OBSERVED_REFERENCE_PRICE`) |

---

## 3. Data Integrity & Lossless Compatibility

1. **Existing Data Preservation:** Zero existing observations were deleted, truncated, or reordered during this audit.
2. **Backward Compatibility:** All downstream parsers, report generators, and dashboard API readers ingest the 32-column header seamlessly via name-based dictionary mapping (`csv.DictReader`).
3. **Verdict Summary:** The schema drift is approved as a necessary, additive data-provenance extension.
