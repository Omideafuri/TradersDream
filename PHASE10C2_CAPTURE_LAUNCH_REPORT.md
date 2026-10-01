# PHASE 10C.2 — 30-DAY BTCUSDT AUTHENTIC L2 CAPTURE LAUNCH REPORT

**Launch Timestamp (UTC):** `2026-09-30 03:01:36 UTC`  
**Launch Timestamp (Local):** `2026-09-30 06:31:36`  
**Host Machine:** `DESKTOP-6QLOBPQ`  
**Collector Version:** `v10c.1` | **Schema Version:** `1.0.0`  
**Git Revision:** `9e720c54bf856976e001c3d3257a20cc9514f754`  
**Collector Process ID:** `3692` (Background Daemon Task: `task-3842`)  
**Capture Target:** Binance.US Spot `BTCUSDT`  
**Capture Directory (Normalized):** `data/collected_events`  
**Capture Directory (Raw Payloads):** `data/raw_collected_events`  
**Checkpoint Directory:** `data/checkpoints`  

```text
================================================================================
CAPTURE STATUS: RUNNING — DAY 0/30
PHASE 10D: BLOCKED
================================================================================
```

---

## 1. AUTOMATED PRE-FLIGHT VERIFICATION RESULTS

Before launch, an exhaustive automated pre-flight audit was executed. All 18 safety, protocol, and architectural invariants passed:

| Pre-Flight Check | Expected Specification | Audit Result | Status |
| :--- | :--- | :--- | :--- |
| `PAPER_TRADING_ONLY` | `True` | `True` | **PASSED** |
| `USE_LIVE_JEV` | `False` | `False` | **PASSED** |
| `LEVERAGE` | `1.0` (unleveraged) | `1.0` | **PASSED** |
| `LIVE_ORDERS` | `0` (execution forbidden) | `0` | **PASSED** |
| `WALLET_CONNECTIONS` | `0` (no wallet/private key) | `0` | **PASSED** |
| `PRIVATE_KEYS` | `0` (none loaded or accessible) | `0` | **PASSED** |
| `ALLOW_SYNTHETIC_FALLBACK` | `False` (zero synthetic data) | `False` | **PASSED** |
| Target Exchange | `binance-us` | `binance-us` | **PASSED** |
| Target Symbol Universe | `["BTCUSDT"]` (strictly isolated) | `["BTCUSDT"]` | **PASSED** |
| L2 / Depth Stream | Enabled (`btcusdt@depth@100ms`) | Verified in stream URL | **PASSED** |
| Trade Stream | Enabled (`btcusdt@trade`) | Verified in stream URL | **PASSED** |
| Raw Ingest Stage | Enabled (`RawMessageWriter`) | Verified unparsed JSONL | **PASSED** |
| Normalized Stage | Enabled (`EventBufferWriter`) | Verified canonical CSV | **PASSED** |
| Automated Checkpoint Task | Enabled (`_checkpoint_loop`) | Verified UTC midnight task | **PASSED** |
| Cryptographic Integrity | Enabled (`hashlib.sha256`) | Verified on file rotation | **PASSED** |
| Disk Safety Threshold | $\ge 2.0\text{ GB}$ reserve | $2.0\text{ GB}$ enforced | **PASSED** |
| Silent Stall Watchdog | Enabled ($60\text{ s}$ timeout) | Verified with auto-recovery | **PASSED** |
| Exponential Reconnect | Enabled ($5\text{ attempts}$, backoff) | Verified in stream loop | **PASSED** |

---

## 2. HOST RUNTIME VERIFICATION

| Metric | Verification Method | Recorded Value |
| :--- | :--- | :--- |
| **Network Reachability (WS)** | `Test-NetConnection stream.binance.us:9443` | `TcpTestSucceeded : True` |
| **Network Reachability (REST)** | `Test-NetConnection api.binance.us:443` | `TcpTestSucceeded : True` |
| **AC Sleep Timeout** | `powercfg /QUERY SCHEME_CURRENT SUB_SLEEP STANDBYIDLE` | `0x00000000` (Disabled / Never Sleep) |
| **Initial Available Disk Space** | `shutil.disk_usage('.')` | `21,322,186,752` bytes (~21.32 GB free) |
| **Safety Storage Threshold** | `min_disk_free_bytes` | `2,147,483,648` bytes (2.0 GB minimum) |
| **Effective Storage Headroom** | Available - Safety Threshold | `19,174,703,104` bytes (~19.17 GB headroom) |
| **Directory Write Permissions** | File creation test on target paths | Writable (`data/collected_events`, `data/raw_collected_events`, `data/checkpoints`) |

---

## 3. CAPTURE DATA ARCHITECTURE (3-STAGE PIPELINE)

The capture adheres strictly to the three-stage immutable data flow:

```text
       STAGE 1: RAW
 [binance-us_raw_YYYY-MM-DD_BTCUSDT.jsonl.gz]
  - Untouched raw WebSocket frame strings
  - Serialized with microsecond local timestamps
  - Write-once, read-only
                   │
                   ▼
    STAGE 2: CANONICAL NORMALIZED
 [binance-us_incremental_book_l2_YYYY-MM-DD_BTCUSDT.csv.gz]
 [binance-us_trades_YYYY-MM-DD_BTCUSDT.csv.gz]
  - Explicit protocol routing (e=depthUpdate vs e=trade)
  - Top-1000 REST book snapshot initialized as base
  - Periodic fsync flushing (every 5 seconds)
  - Header re-injection protection on resume
                   │
                   ▼
     STAGE 3: DAILY QUALIFICATION
 [checkpoint_YYYY-MM-DD_BTCUSDT.json]
  - Machine-readable JSON output at 00:00:00 UTC
  - Continuous sequence tracking ($U_{k+1} \le u_k + 1$)
  - Cryptographic checksums (SHA-256 for all daily files)
  - Strict classification: CONTINUOUS vs INTERRUPTED
```

---

## 4. INITIAL LIVE INGESTION VERIFICATION

Immediately following WebSocket connection establishment, initial live event ingestion was confirmed on disk:

### Active Files On Disk
1. **Normalized L2 Depth:** `data/collected_events/binance-us_incremental_book_l2_2026-09-30_BTCUSDT.csv.gz`
2. **Normalized Trades:** `data/collected_events/binance-us_trades_2026-09-30_BTCUSDT.csv.gz`
3. **Raw Payloads:** `data/raw_collected_events/binance-us_raw_2026-09-30_BTCUSDT.jsonl.gz`

### Initial Event Verification
* **First Order Book Snapshot:** Initialized via REST snapshot (`lastUpdateId=3348808565`).
* **First Normalized Depth Record:**
  ```csv
  exchange,symbol,timestamp,local_timestamp,is_snapshot,side,price,amount
  binance-us,BTCUSDT,1790737310553922,1790737310553922,true,bid,83347.76,0.0033
  ```
* **First Normalized Trade Record:**
  ```csv
  exchange,symbol,timestamp,local_timestamp,id,side,price,amount
  binance-us,BTCUSDT,1790737320928000,1790737321945174,31843071,buy,83333.23,0.00096
  ```
* **First Raw Message Payload:**
  ```json
  {"local_timestamp": 1790737312193501, "raw": "{\"stream\":\"btcusdt@depth@100ms\",\"data\":{\"e\":\"depthUpdate\",\"E\":1790737312193,...}}"}
  ```

### Live Sample Metrics (at Launch + 1 Minute)
* **Depth records written:** `1,989+` records
* **Trade events written:** `6+` records
* **Raw WebSocket messages logged:** `102+` messages
* **Sequence gaps detected:** `0`
* **Malformed / Corrupted packets:** `0`
* **Duplicate trade packets:** `0`
* **Reconnections:** `0`

---

## 5. MONITORING & OPERATIONAL HEALTH

* **Process State:** Running (`PID 3692`, `task-3842`).
* **Health Status:** `HEALTHY`.
* **Watchdog Status:** Active (polls every 5s; triggers socket recovery if zero messages for >60s).
* **Buffer Flush:** Active (auto-flushed every 5s via watchdog loop with `os.fsync`).
* **Disk Monitoring:** Active (aborts with `DiskCapacityExceededError` if free disk < 2.0 GB).
* **Automated Midnight Checkpointing:** Active (`_checkpoint_loop` running concurrently).

---

## 6. STRICT INVARIANT RE-AFFIRMATION

The collector operates exclusively as passive, lawful market-data infrastructure:
* `PAPER_TRADING_ONLY = True`
* `USE_LIVE_JEV = False`
* `LEVERAGE = 1.0`
* `LIVE_ORDERS = 0`
* `WALLET_CONNECTIONS = 0`
* `PRIVATE_KEYS = 0`
* `ALLOW_SYNTHETIC_FALLBACK = False`

**Phase 10D Gate:** Strictly **`BLOCKED`** until 30 consecutive qualified daily datasets and checkpoints are verified without synthetic contamination or sequence breaks.
