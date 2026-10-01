"""
Phase 13: Persistent State Manager & Event Logger for XAU/USD Paper Validation.
Ensures crash-resilience, atomic state serialization, and auditable event logging.
Includes full market-data provenance separation, heartbeat telemetry, and explicit observation identities.
"""

import json
from dataclasses import dataclass, asdict, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
PHASE13_DIR = ROOT_DIR / "phase13"
DATA_DIR = PHASE13_DIR / "data"
STATE_FILE = DATA_DIR / "forward_state.json"
EVENT_LOG_FILE = DATA_DIR / "forward_event_log.jsonl"


def generate_raw_response_id(receipt_ts: str, payload_sha256: str) -> str:
    """Deterministic identity for a raw HTTP response."""
    clean_ts = receipt_ts.replace(":", "-").replace(".", "-")
    return f"RAW_{clean_ts}_{payload_sha256[:12]}"


def generate_provider_observation_id(provider_updated_at: str, price: float, instrument: str = "XAU/USD") -> str:
    """Deterministic identity for a distinct provider market observation."""
    clean_upd = provider_updated_at.replace(":", "-").replace(".", "-")
    clean_inst = instrument.replace("/", "_")
    return f"OBS_{clean_upd}_{price:.4f}_{clean_inst}"


def generate_candle_id(utc_hour_bucket: str) -> str:
    """Deterministic identity for a finalized 1-hour candle."""
    clean_bucket = utc_hour_bucket.replace(":", "-").replace(".", "-")
    return f"CANDLE_1H_{clean_bucket}"


def generate_paper_execution_id(signal_ts: str, execution_ts: str, side: str, transition: str) -> str:
    """Deterministic identity for a paper trade execution."""
    clean_sig = signal_ts.replace(":", "-").replace(".", "-")
    clean_exec = execution_ts.replace(":", "-").replace(".", "-")
    return f"EXEC_{clean_sig}_{clean_exec}_{side}_{transition}"


@dataclass
class ForwardState:
    strategy_id: str = "XAUUSD_FROZEN_SMA50_200_1H"
    instrument: str = "XAU/USD"
    environment: str = "PAPER_TRADING_ONLY"
    live_orders_permitted: int = 0
    wallet_connections: int = 0
    private_keys: int = 0
    leverage: float = 1.0
    current_state: str = "FLAT"  # FLAT or LONG
    cash_balance: float = 10000.0
    current_equity: float = 10000.0
    position_units: float = 0.0
    position_entry_price: float = 0.0
    position_entry_time: str = ""
    latest_close: float = 0.0
    latest_sma50: float = 0.0
    latest_sma200: float = 0.0
    latest_atr14: float = 0.0
    latest_bar_time_utc: str = ""
    last_quote_time_utc: str = ""
    
    # Market Data Provenance Separation (Section 5)
    observed_reference_price: float = 0.0
    observed_bid: Optional[float] = None
    observed_ask: Optional[float] = None
    modeled_bid: float = 0.0
    modeled_ask: float = 0.0
    last_quote_bid: float = 0.0  # Legacy alias for modeled/observed bid
    last_quote_ask: float = 0.0  # Legacy alias for modeled ask
    ask_data_available: bool = False
    
    pending_order: Optional[Dict[str, Any]] = None
    total_trades_executed: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    gross_pnl_usd: float = 0.0
    net_pnl_usd: float = 0.0
    cumulative_pnl_usd: float = 0.0
    total_spread_cost_usd: float = 0.0
    total_slippage_cost_usd: float = 0.0
    total_commission_usd: float = 0.0
    total_swap_cost_usd: float = 0.0
    peak_equity_usd: float = 10000.0
    max_drawdown_pct: float = 0.0
    warmup_completed: bool = False
    warmup_bars_count: int = 0
    forward_bars_count: int = 0
    forward_start_timestamp: str = ""
    last_integrity_check_utc: str = ""
    status: str = "INITIALIZED"

    # Continuous Heartbeat & Feed Health Telemetry (Section 10 & 11)
    last_successful_quote_utc: str = ""
    last_processing_time_utc: str = ""
    last_finalized_candle_utc: str = ""
    last_state_persistence_utc: str = ""
    daemon_start_time_utc: str = ""
    restart_count: int = 0
    feed_status: str = "HEALTHY"  # RUNNING_HEALTHY, RUNNING_STALE_FEED, RUNNING_API_FAILURE, STOPPED, INTEGRITY_BREACH
    daemon_pid: Optional[int] = None
    daemon_running: bool = False

    # Data Completeness & Ingestion Telemetry Counters (Section 2)
    scheduled_polls: int = 0
    successful_polls: int = 0
    failed_polls: int = 0
    timeout_polls: int = 0
    malformed_polls: int = 0

    raw_responses_received: int = 0
    raw_responses_archived: int = 0

    unique_provider_observations: int = 0
    duplicate_provider_observations: int = 0

    new_provider_updates: int = 0
    unchanged_provider_updates: int = 0

    finalized_1h_candles: int = 0
    missing_1h_buckets: int = 0

    @property
    def poll_success_rate(self) -> float:
        """Poll Success Rate = successful_polls / scheduled_polls (Section 2)"""
        return (self.successful_polls / self.scheduled_polls) if self.scheduled_polls > 0 else 0.0

    @property
    def raw_archive_completeness(self) -> float:
        """Raw Archive Completeness = raw_responses_archived / successful_polls (Section 2)"""
        return (self.raw_responses_archived / self.successful_polls) if self.successful_polls > 0 else 0.0

    @property
    def provider_freshness_rate(self) -> float:
        """Provider Freshness = new_provider_updates / successful_polls (Section 2)"""
        return (self.new_provider_updates / self.successful_polls) if self.successful_polls > 0 else 0.0

    @property
    def hourly_coverage_status(self) -> str:
        """
        Hourly Coverage Telemetry Status (Section 4):
        - NOT_YET_APPLICABLE: When finalized_1h_candles == 0 and initial forward bucket is still IN_PROGRESS.
        - MISSING: When missing_1h_buckets > 0.
        - IN_PROGRESS: When capture is ongoing within an active bucket.
        - COMPLETE: When all expected session buckets are finalized without gaps.
        - MARKET_CLOSED: During weekend/holiday scheduled closure.
        """
        if self.finalized_1h_candles == 0:
            return "NOT_YET_APPLICABLE (INITIAL_BUCKET_IN_PROGRESS)"
        if self.missing_1h_buckets > 0:
            return "MISSING"
        return "COMPLETE"


class StateManager:
    def __init__(self, state_file: Optional[Path] = None, event_log_file: Optional[Path] = None):
        self.state_file = state_file or STATE_FILE
        self.event_log_file = event_log_file or EVENT_LOG_FILE
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state = self.load_state()

    def load_state(self) -> ForwardState:
        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                # Filter out unknown keys for schema safety
                valid_fields = {f.name for f in fields(ForwardState)}
                filtered_data = {k: v for k, v in data.items() if k in valid_fields}
                return ForwardState(**filtered_data)
            except Exception as e:
                self.log_event("STATE_LOAD_ERROR", "ERROR", f"Failed to load state: {e}. Reinitializing default.")
        return ForwardState()

    def save_state(self):
        self.state.last_state_persistence_utc = datetime.now(timezone.utc).isoformat()
        temp_file = self.state_file.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(asdict(self.state), f, indent=2)
        temp_file.replace(self.state_file)

    def log_event(self, event_type: str, severity: str, message: str):
        record = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "severity": severity,
            "message": message,
            "strategy_id": self.state.strategy_id,
            "state": self.state.current_state,
        }
        with open(self.event_log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
