"""
Phase 13: Forward Prospective Paper Capture Monitor for XAU/USD.
Orchestrates live quote ingestion, completed 1-hour candle aggregation,
causal next-bar execution, append-only ledger logging, and crash-resilient state management.
Features market-data provenance separation, complete raw-layer evidence preservation,
processing-layer deduplication, hourly data-coverage registry, and heartbeat telemetry.
"""

import sys
import hashlib
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import time
from typing import Dict, List, Optional, Tuple, Any
import urllib.request

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import numpy as np
import pandas as pd

from phase13.engine.state_manager import (
    ForwardState,
    StateManager,
    generate_raw_response_id,
    generate_provider_observation_id,
    generate_candle_id,
    generate_paper_execution_id,
)
from phase13.engine.execution_simulator import ExecutionSimulator
from phase13.engine.integrity_monitor import IntegrityMonitor

PHASE13_DIR = ROOT_DIR / "phase13"
CONFIG_FILE = PHASE13_DIR / "config" / "phase13_forward_config.json"
DATA_DIR = PHASE13_DIR / "data"
RAW_QUOTES_DIR = DATA_DIR / "raw_forward_quotes"
LEDGER_FILE = DATA_DIR / "forward_paper_ledger.csv"
COVERAGE_FILE = DATA_DIR / "hourly_coverage_registry.json"


class ForwardMonitor:
    def __init__(
        self,
        config_path: Optional[Path] = None,
        state_mgr: Optional[StateManager] = None,
        ledger_file: Optional[Path] = None,
        coverage_file: Optional[Path] = None,
        raw_quotes_dir: Optional[Path] = None,
    ):
        self.config_path = config_path or CONFIG_FILE
        self.config = self._load_config()

        self.sm = state_mgr or StateManager()
        self.ledger_file = ledger_file or LEDGER_FILE
        self.coverage_file = coverage_file or COVERAGE_FILE
        self.raw_quotes_dir = raw_quotes_dir or RAW_QUOTES_DIR
        self.raw_quotes_dir.mkdir(parents=True, exist_ok=True)

        self.exec_sim = ExecutionSimulator(
            self.sm,
            modeled_spread_bps=self.config["execution_costs"]["modeled_spread_bps"],
            modeled_slippage_bps=self.config["execution_costs"]["modeled_slippage_bps"],
            commission_per_oz=self.config["execution_costs"]["commission_usd_per_oz"],
            annual_swap_rate=self.config["execution_costs"]["annual_swap_rate"],
            swap_cut_hour_utc=self.config["execution_costs"]["swap_cut_hour_utc"],
        )
        self.integrity_mon = IntegrityMonitor(self.sm)

        self.active_hour_quotes: List[Dict[str, Any]] = []
        self.current_bucket_hour: Optional[datetime] = None
        self.history_df: Optional[pd.DataFrame] = None
        self.last_obs_id: Optional[str] = None
        self.coverage_registry: Dict[str, Dict[str, Any]] = self._load_coverage_registry()

        self._initialize_warmup()

    def _load_config(self) -> Dict:
        assert self.config_path.exists(), f"Config not found: {self.config_path}"
        with open(self.config_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _load_coverage_registry(self) -> Dict[str, Dict[str, Any]]:
        if self.coverage_file.exists():
            try:
                with open(self.coverage_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_coverage_registry(self):
        try:
            temp_f = self.coverage_file.with_suffix(".tmp")
            with open(temp_f, "w", encoding="utf-8") as f:
                json.dump(self.coverage_registry, f, indent=2)
            temp_f.replace(self.coverage_file)
        except Exception as e:
            self.sm.log_event("COVERAGE_REGISTRY_ERROR", "ERROR", f"Failed saving coverage registry: {e}")

    def _initialize_warmup(self):
        """
        Loads the final 250 historical 1-hour bars from 2021-2025 to seed SMA50 and SMA200.
        Marks these strictly as WARMUP data. Cutoff timestamp: 2025-12-31 21:00 UTC.
        """
        warmup_rel = self.config.get("historical_warmup_file", "phase11/data/processed/XAUUSD_1H_2021_2025.csv")
        warmup_path = ROOT_DIR / warmup_rel
        if not warmup_path.exists():
            self.sm.log_event("WARMUP_WARNING", "WARNING", f"Warmup file not found: {warmup_path}")
            return

        df = pd.read_csv(warmup_path)
        # Retain last 250 bars to compute rolling SMA50/SMA200 cleanly without NaN
        warmup_subset = df.iloc[-250:].copy().reset_index(drop=True)
        warmup_subset["dt_utc"] = pd.to_datetime(warmup_subset["dt_utc"])
        warmup_subset["sma50"] = warmup_subset["close"].rolling(50).mean()
        warmup_subset["sma200"] = warmup_subset["close"].rolling(200).mean()

        # ATR 14 diagnostic
        prev_c = warmup_subset["close"].shift(1)
        tr = pd.concat([
            warmup_subset["high"] - warmup_subset["low"],
            (warmup_subset["high"] - prev_c).abs(),
            (warmup_subset["low"] - prev_c).abs(),
        ], axis=1).max(axis=1)
        warmup_subset["atr14"] = tr.rolling(14).mean()

        self.history_df = warmup_subset

        last_row = warmup_subset.iloc[-1]
        self.sm.state.latest_close = float(last_row["close"])
        self.sm.state.latest_sma50 = float(last_row["sma50"])
        self.sm.state.latest_sma200 = float(last_row["sma200"])
        self.sm.state.latest_atr14 = float(last_row["atr14"])
        self.sm.state.latest_bar_time_utc = str(last_row["dt_utc"])
        self.sm.state.warmup_completed = True
        self.sm.state.warmup_bars_count = len(warmup_subset)
        if not self.sm.state.forward_start_timestamp:
            self.sm.state.forward_start_timestamp = datetime.now(timezone.utc).isoformat()

        self.sm.log_event(
            "WARMUP_INITIALIZED",
            "INFO",
            f"Initialized warmup with {len(warmup_subset)} historical bars through {last_row['dt_utc']}. "
            f"SMA50: ${last_row['sma50']:.2f}, SMA200: ${last_row['sma200']:.2f}"
        )
        self.sm.save_state()

    def fetch_live_quote(self) -> Optional[Dict[str, Any]]:
        """
        Fetches authentic spot XAU/USD reference price from public Gold-API endpoint.
        RAW LAYER: Preserves every vendor HTTP 200 response as immutable raw evidence.
        PROCESSING LAYER: Tags quote with observation ID and duplicate classification.
        """
        endpoint = self.config["data_feed"]["primary_endpoint"]
        self.sm.state.scheduled_polls += 1
        ts_now = datetime.now(timezone.utc).isoformat()

        try:
            req = urllib.request.Request(endpoint, headers={"User-Agent": "Phase13ForwardMonitor/1.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                raw_bytes = resp.read()
                data = json.loads(raw_bytes.decode())

            self.sm.state.successful_polls += 1
            self.sm.state.raw_responses_received += 1

            # Validate response schema
            if data.get("symbol") == "XAU" and "price" in data and float(data["price"]) > 0:
                payload_sha256 = hashlib.sha256(raw_bytes).hexdigest()
                raw_id = generate_raw_response_id(ts_now, payload_sha256)
                provider_upd = str(data.get("updatedAt", ts_now))
                obs_price = float(data["price"])
                obs_id = generate_provider_observation_id(provider_upd, obs_price)

                # RAW LAYER ARCHIVAL: Every valid vendor response is preserved
                raw_record = {
                    "raw_response_id": raw_id,
                    "provider_observation_id": obs_id,
                    "local_receipt_timestamp_utc": ts_now,
                    "vendor_updated_at": provider_upd,
                    "http_status": 200,
                    "endpoint": endpoint,
                    "response_payload": data,
                    "response_sha256": payload_sha256,
                    "instrument": "XAU/USD",
                    "observed_price": obs_price,
                }
                clean_ts = ts_now.replace(":", "-").replace(".", "-")
                quote_file = self.raw_quotes_dir / f"raw_response_{clean_ts}.json"
                with open(quote_file, "w", encoding="utf-8") as f:
                    json.dump(raw_record, f, indent=2)

                self.sm.state.raw_responses_archived += 1
                self.sm.state.last_successful_quote_utc = ts_now

                # PROCESSING LAYER: Classify new vs duplicate provider observation
                is_duplicate = (obs_id == self.last_obs_id)
                if is_duplicate:
                    self.sm.state.duplicate_provider_observations += 1
                    self.sm.state.unchanged_provider_updates += 1
                    data["is_duplicate"] = True
                else:
                    self.sm.state.unique_provider_observations += 1
                    self.sm.state.new_provider_updates += 1
                    self.last_obs_id = obs_id
                    data["is_duplicate"] = False

                data["raw_response_id"] = raw_id
                data["provider_observation_id"] = obs_id
                data["received_at_utc"] = ts_now
                self.sm.save_state()
                return data
            else:
                self.sm.state.malformed_polls += 1
                self.sm.log_event("QUOTE_MALFORMED", "WARNING", f"Malformed payload from {endpoint}: {data}")
        except urllib.error.URLError as e:
            self.sm.state.failed_polls += 1
            if "timed out" in str(e).lower():
                self.sm.state.timeout_polls += 1
            self.sm.state.feed_status = "RUNNING_API_FAILURE"
            self.sm.log_event("QUOTE_FETCH_FAILED", "ERROR", f"URLError from {endpoint}: {e}")
        except Exception as e:
            self.sm.state.failed_polls += 1
            self.sm.state.feed_status = "RUNNING_API_FAILURE"
            self.sm.log_event("QUOTE_FETCH_FAILED", "ERROR", f"Error fetching quote from {endpoint}: {e}")

        self.sm.save_state()
        return None

    def process_quote(self, quote: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Processes an arriving quote.
        Separates OBSERVED REFERENCE PRICE from MODELED BID/ASK.
        Deduplicates at processing layer (duplicate quotes update heartbeat and coverage but do not distort OHLC).
        Aggregates into active hourly bucket. Finalizes previous candle upon hour rollover.
        Returns: (candle_completed_flag, completed_candle_time_str)
        """
        ref_price = float(quote["price"])
        if "updatedAt" in quote:
            try:
                dt_p = pd.to_datetime(quote["updatedAt"])
                quote_time = dt_p.to_pydatetime() if hasattr(dt_p, 'to_pydatetime') else dt_p
                if getattr(quote_time, "tzinfo", None) is None:
                    quote_time = quote_time.replace(tzinfo=timezone.utc)
                else:
                    quote_time = quote_time.astimezone(timezone.utc)
            except Exception:
                quote_time = datetime.now(timezone.utc)
        elif "time" in quote:
            if isinstance(quote["time"], datetime):
                quote_time = quote["time"]
                if quote_time.tzinfo is None:
                    quote_time = quote_time.replace(tzinfo=timezone.utc)
            else:
                try:
                    dt_p = pd.to_datetime(quote["time"])
                    quote_time = dt_p.to_pydatetime() if hasattr(dt_p, 'to_pydatetime') else dt_p
                    if getattr(quote_time, "tzinfo", None) is None:
                        quote_time = quote_time.replace(tzinfo=timezone.utc)
                    else:
                        quote_time = quote_time.astimezone(timezone.utc)
                except Exception:
                    quote_time = datetime.now(timezone.utc)
        else:
            quote_time = datetime.now(timezone.utc)

        bucket_hour = quote_time.replace(minute=0, second=0, microsecond=0)
        bucket_hour_str = bucket_hour.isoformat()

        half_spread = ref_price * (self.config["execution_costs"]["modeled_spread_bps"] / 2.0 / 10000.0)
        modeled_bid = ref_price - half_spread
        modeled_ask = ref_price + half_spread

        # Provenance separation (Section 5)
        st = self.sm.state
        st.last_quote_time_utc = quote_time.isoformat()
        st.last_processing_time_utc = datetime.now(timezone.utc).isoformat()
        st.observed_reference_price = ref_price
        st.observed_bid = None  # Provider supplies generic reference price
        st.observed_ask = None
        st.modeled_bid = modeled_bid
        st.modeled_ask = modeled_ask
        st.last_quote_bid = modeled_bid
        st.last_quote_ask = modeled_ask
        st.ask_data_available = False

        # Update unrealized mark-to-market if LONG
        if st.current_state == "LONG":
            st.current_equity = st.position_units * modeled_bid

        # Update Hourly Coverage Registry (Section 8)
        is_dup = quote.get("is_duplicate", False)
        if bucket_hour_str not in self.coverage_registry:
            self.coverage_registry[bucket_hour_str] = {
                "hour_bucket": bucket_hour_str,
                "expected_capture": True,
                "quotes_received": 1,
                "unique_provider_updates": 0 if is_dup else 1,
                "first_receipt": quote_time.isoformat(),
                "last_receipt": quote_time.isoformat(),
                "candle_finalized": False,
                "candle_status": "IN_PROGRESS",
            }
        else:
            cov = self.coverage_registry[bucket_hour_str]
            cov["quotes_received"] += 1
            if not is_dup:
                cov["unique_provider_updates"] += 1
            cov["last_receipt"] = quote_time.isoformat()

        self._save_coverage_registry()

        candle_finalized = False
        completed_candle_str = None

        if self.current_bucket_hour is None:
            self.current_bucket_hour = bucket_hour
            self.active_hour_quotes.append({"time": quote_time, "price": ref_price})
        elif bucket_hour > self.current_bucket_hour:
            # Check for session gap (> 1 hour delta)
            hour_diff = int((bucket_hour - self.current_bucket_hour).total_seconds() / 3600)
            if hour_diff > 1:
                st.missing_1h_buckets += (hour_diff - 1)
                self.sm.log_event(
                    "SESSION_GAP_DETECTED",
                    "WARNING",
                    f"Session gap of {hour_diff - 1} hours detected between {self.current_bucket_hour} and {bucket_hour}."
                )

            # Hour rolled over! Finalize previous hour's candle
            completed_candle_str = self._finalize_hourly_candle(self.current_bucket_hour, ref_price)
            candle_finalized = True

            # Start new bucket
            self.current_bucket_hour = bucket_hour
            self.active_hour_quotes = [{"time": quote_time, "price": ref_price}]
        else:
            # Inside current hour bucket: append only if not a duplicate price/timestamp
            if not is_dup:
                self.active_hour_quotes.append({"time": quote_time, "price": ref_price})

        st.feed_status = "RUNNING_HEALTHY"
        self.sm.save_state()
        return candle_finalized, completed_candle_str

    def _finalize_hourly_candle(self, bucket_dt: datetime, next_open_price: float) -> str:
        """
        Constructs and finalizes completed 1-hour candle.
        Evaluates signals, executes any queued next-bar orders, and logs to ledger.
        """
        prices = [q["price"] for q in self.active_hour_quotes]
        c_open = prices[0]
        c_high = max(prices)
        c_low = min(prices)
        c_close = prices[-1]
        candle_ts_str = bucket_dt.isoformat()

        # Update coverage registry status
        if candle_ts_str in self.coverage_registry:
            self.coverage_registry[candle_ts_str]["candle_finalized"] = True
            self.coverage_registry[candle_ts_str]["candle_status"] = "COMPLETE"
            self._save_coverage_registry()

        # Execute any pending order queued from prior bar close
        exec_details = self.exec_sim.execute_pending_order(
            bar_open_time=candle_ts_str,
            bar_open_price=c_open,
            observed_bid=None,
            observed_ask=None,
        )

        # Append candle to history dataframe for indicator continuity
        new_row = pd.DataFrame([{
            "dt_utc": bucket_dt,
            "open": c_open,
            "high": c_high,
            "low": c_low,
            "close": c_close,
            "volume": len(prices),
        }])
        self.history_df = pd.concat([self.history_df, new_row], ignore_index=True)

        # Compute updated rolling indicators
        self.history_df["sma50"] = self.history_df["close"].rolling(50).mean()
        self.history_df["sma200"] = self.history_df["close"].rolling(200).mean()
        prev_c = self.history_df["close"].shift(1)
        tr = pd.concat([
            self.history_df["high"] - self.history_df["low"],
            (self.history_df["high"] - prev_c).abs(),
            (self.history_df["low"] - prev_c).abs(),
        ], axis=1).max(axis=1)
        self.history_df["atr14"] = tr.rolling(14).mean()

        cur_sma50 = float(self.history_df["sma50"].iloc[-1])
        cur_sma200 = float(self.history_df["sma200"].iloc[-1])
        cur_atr14 = float(self.history_df["atr14"].iloc[-1])

        self.sm.state.latest_close = c_close
        self.sm.state.latest_sma50 = cur_sma50
        self.sm.state.latest_sma200 = cur_sma200
        self.sm.state.latest_atr14 = cur_atr14
        self.sm.state.latest_bar_time_utc = candle_ts_str
        self.sm.state.last_finalized_candle_utc = candle_ts_str
        self.sm.state.forward_bars_count += 1
        self.sm.state.finalized_1h_candles += 1

        state_before = self.sm.state.current_state
        generated_signal = 0

        # Causal signal evaluation at close of bar t
        if state_before == "FLAT" and cur_sma50 > cur_sma200:
            generated_signal = 1
            self.exec_sim.queue_order("BUY", candle_ts_str, c_close)
        elif state_before == "LONG" and cur_sma50 <= cur_sma200:
            generated_signal = -1
            self.exec_sim.queue_order("SELL", candle_ts_str, c_close)

        # Append-only entry to forward_paper_ledger.csv
        self._append_to_ledger(
            candle_ts=candle_ts_str,
            c_open=c_open,
            c_high=c_high,
            c_low=c_low,
            c_close=c_close,
            sma50=cur_sma50,
            sma200=cur_sma200,
            atr14=cur_atr14,
            state_before=state_before,
            signal=generated_signal,
            exec_details=exec_details,
        )

        self.sm.log_event(
            "CANDLE_COMPLETED",
            "INFO",
            f"Finalized 1H candle {candle_ts_str}: Open=${c_open:.2f}, High=${c_high:.2f}, "
            f"Low=${c_low:.2f}, Close=${c_close:.2f} | SMA50=${cur_sma50:.2f}, SMA200=${cur_sma200:.2f} | Signal: {generated_signal}"
        )
        return candle_ts_str

    def _append_to_ledger(
        self,
        candle_ts: str,
        c_open: float,
        c_high: float,
        c_low: float,
        c_close: float,
        sma50: float,
        sma200: float,
        atr14: float,
        state_before: str,
        signal: int,
        exec_details: Optional[Dict[str, Any]],
    ):
        """Appends a 32-column row to forward_paper_ledger.csv with full provenance tags."""
        ed = exec_details or {}
        row = {
            "timestamp_utc": candle_ts,
            "instrument": "XAU/USD",
            "strategy_id": "XAUUSD_FROZEN_SMA50_200_1H",
            "candle_open": round(c_open, 4),
            "candle_high": round(c_high, 4),
            "candle_low": round(c_low, 4),
            "candle_close": round(c_close, 4),
            "bid": round(c_close, 4),
            "ask": "UNAVAILABLE",
            "spread": f"{self.config['execution_costs']['modeled_spread_bps']:.1f} bps (MODELED)",
            "sma50": round(sma50, 4),
            "sma200": round(sma200, 4),
            "atr14": round(atr14, 4),
            "state_before": state_before,
            "signal": signal,
            "signal_timestamp": candle_ts if signal != 0 else "",
            "execution_timestamp": ed.get("execution_timestamp", ""),
            "execution_reference_price": ed.get("execution_reference_price", ""),
            "execution_side": ed.get("action", ""),
            "execution_price": ed.get("execution_price", ""),
            "execution_price_source": ed.get("execution_price_source", ""),
            "position_units": round(self.sm.state.position_units, 6),
            "cash_balance": round(self.sm.state.cash_balance, 2),
            "gross_equity": round(self.sm.state.current_equity, 2),
            "financing_cost": ed.get("financing_cost", 0.0),
            "spread_cost": ed.get("spread_cost", 0.0),
            "slippage_cost": ed.get("slippage_cost", 0.0),
            "net_equity": round(self.sm.state.current_equity, 2),
            "net_pnl": ed.get("net_pnl", 0.0),
            "cumulative_pnl": round(self.sm.state.cumulative_pnl_usd, 2),
            "data_source": "Gold-API Spot XAU/USD (api.gold-api.com)",
            "data_quality_status": "OBSERVED_REFERENCE_PRICE",
        }
        df_row = pd.DataFrame([row])
        df_row.to_csv(self.ledger_file, mode="a", header=False, index=False)

    def run_single_poll(self) -> Dict[str, Any]:
        """Runs a single live quote fetch and processing step."""
        quote = self.fetch_live_quote()
        if not quote:
            return {"status": "SKIPPED_OR_FAILED", "reason": "No quote returned or fetch failed"}

        finalized, candle_time = self.process_quote(quote)
        return {
            "status": "SUCCESS",
            "price": quote.get("price"),
            "is_duplicate": quote.get("is_duplicate", False),
            "candle_finalized": finalized,
            "completed_candle_time": candle_time,
            "current_state": self.sm.state.current_state,
            "equity": self.sm.state.current_equity,
        }
