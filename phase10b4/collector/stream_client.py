"""Binance.US public WebSocket stream collector with sequence gap auditing, watchdog, and crash safety."""

import asyncio
import datetime
import hashlib
import json
import logging
from pathlib import Path
import shutil
import time
from typing import Dict, Any, List, Optional
import urllib.request
import websockets

from .config import CollectorConfig
from .buffer_writer import EventBufferWriter, RawMessageWriter

logger = logging.getLogger(__name__)


class CollectorWatchdogTimeoutError(Exception):
    """Raised when the stream client experiences silent message starvation."""
    pass


class BinanceUSStreamCollector:
    """Lawful, zero-cost real-time event collector for Binance.US public market streams."""

    def __init__(self, config: Optional[CollectorConfig] = None):
        self.config = config or CollectorConfig()
        self.is_running = False
        self.writers: Dict[str, EventBufferWriter] = {}
        self.raw_writers: Dict[str, RawMessageWriter] = {}
        self.last_update_ids: Dict[str, int] = {}
        self.snapshot_last_update_ids: Dict[str, int] = {}
        self.disconnect_events: List[Dict[str, Any]] = []
        self.sequence_gaps: List[Dict[str, Any]] = []
        self.malformed_packets_count: int = 0
        self.duplicate_packets_count: int = 0
        self.last_message_time: float = 0.0
        self.reconnect_count: int = 0
        self.total_downtime_seconds: float = 0.0
        self.watchdog_task: Optional[asyncio.Task] = None
        self.checkpoint_task: Optional[asyncio.Task] = None
        self.seen_trade_ids: set = set()
        self.first_packet_timestamp: Dict[str, int] = {}
        self.last_packet_timestamp: Dict[str, int] = {}
        self._current_ws = None

    def build_stream_url(self) -> str:
        """Construct combined WebSocket stream URL for configured symbols."""
        streams = []
        for symbol in self.config.symbols:
            s_lower = symbol.lower()
            streams.append(f"{s_lower}@depth@{self.config.depth_frequency}")
            streams.append(f"{s_lower}@trade")
        stream_param = "/".join(streams)
        return f"{self.config.ws_endpoint}?streams={stream_param}"

    def fetch_rest_snapshot(self, symbol: str) -> Dict[str, Any]:
        """Fetch REST top-1000 order book depth snapshot to initialize order-book state."""
        url = f"{self.config.rest_depth_endpoint}?symbol={symbol.upper()}&limit={self.config.depth_limit}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        now_us = int(time.time() * 1000000)
        self.snapshot_last_update_ids[symbol.upper()] = data["lastUpdateId"]

        return {
            "symbol": symbol.upper(),
            "exchange": self.config.venue,
            "lastUpdateId": data["lastUpdateId"],
            "timestamp": now_us,
            "local_timestamp": now_us,
            "bids": [[float(p), float(q)] for p, q in data["bids"]],
            "asks": [[float(p), float(q)] for p, q in data["asks"]],
        }

    def process_depth_message(self, raw_msg: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Normalize Binance.US @depth message into incremental_book_L2 records."""
        data = raw_msg.get("data", raw_msg)
        symbol = data["s"].upper()
        event_time_us = data["E"] * 1000  # ms to us
        local_time_us = int(time.time() * 1000000)
        first_update_id = data["U"]
        last_update_id = data["u"]

        # Check against snapshot to drop stale pre-snapshot events per Binance sync rules
        snap_id = self.snapshot_last_update_ids.get(symbol)
        if snap_id is not None and last_update_id <= snap_id:
            return []

        # Sequence gap check
        prev_id = self.last_update_ids.get(symbol)
        if prev_id is not None:
            if first_update_id > prev_id + 1:
                gap_rec = {
                    "symbol": symbol,
                    "expected": prev_id + 1,
                    "received": first_update_id,
                    "gap_size": first_update_id - (prev_id + 1),
                    "timestamp": local_time_us,
                }
                self.sequence_gaps.append(gap_rec)
                logger.warning(f"Sequence gap detected on {symbol}: {gap_rec}")

        self.last_update_ids[symbol] = last_update_id

        records = []
        for p, q in data.get("b", []):
            records.append({
                "exchange": self.config.venue,
                "symbol": symbol,
                "timestamp": event_time_us,
                "local_timestamp": local_time_us,
                "is_snapshot": "false",
                "side": "bid",
                "price": float(p),
                "amount": float(q),
            })
        for p, q in data.get("a", []):
            records.append({
                "exchange": self.config.venue,
                "symbol": symbol,
                "timestamp": event_time_us,
                "local_timestamp": local_time_us,
                "is_snapshot": "false",
                "side": "ask",
                "price": float(p),
                "amount": float(q),
            })
        return records

    def process_trade_message(self, raw_msg: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize Binance.US @trade message into trades canonical record."""
        data = raw_msg.get("data", raw_msg)
        symbol = data["s"].upper()
        event_time_us = data["E"] * 1000  # ms to us
        local_time_us = int(time.time() * 1000000)
        trade_id = str(data["t"])
        is_buyer_maker = data["m"]
        side = "sell" if is_buyer_maker else "buy"

        # Duplicate trade check
        if trade_id in self.seen_trade_ids:
            self.duplicate_packets_count += 1
            logger.debug(f"Duplicate trade detected: {trade_id} on {symbol}")
        else:
            self.seen_trade_ids.add(trade_id)
            if len(self.seen_trade_ids) > 100000:
                self.seen_trade_ids.clear()

        return {
            "exchange": self.config.venue,
            "symbol": symbol,
            "timestamp": event_time_us,
            "local_timestamp": local_time_us,
            "id": trade_id,
            "side": side,
            "price": float(data["p"]),
            "amount": float(data["q"]),
        }

    def register_writer(self, key: str, writer: EventBufferWriter) -> None:
        """Registers a normalized buffer writer for a specific symbol and stream type."""
        self.writers[key] = writer

    def register_raw_writer(self, symbol: str, raw_writer: RawMessageWriter) -> None:
        """Registers a raw message writer for raw payload preservation (RAW stage)."""
        self.raw_writers[symbol.upper()] = raw_writer

    def dispatch_raw_message(self, raw_str: str) -> None:
        """Dispatches an incoming JSON WebSocket message to the appropriate handler and writer."""
        self.last_message_time = time.time()

        try:
            msg = json.loads(raw_str)
        except Exception as exc:
            self.malformed_packets_count += 1
            logger.warning(f"Malformed external packet: failed to parse JSON: {exc}")
            return

        if not isinstance(msg, dict):
            self.malformed_packets_count += 1
            logger.warning(f"Malformed external packet: root payload is not a JSON object: {type(msg)}")
            return

        stream = msg.get("stream", "")
        data = msg.get("data", msg)
        if not isinstance(data, dict):
            self.malformed_packets_count += 1
            logger.warning(f"Malformed external packet: inner data payload is not a JSON object: {type(data)}")
            return

        event_type = data.get("e", "")
        symbol = str(data.get("s", "")).upper()

        # Protocol-level event classification
        is_depth = (event_type == "depthUpdate") or ("@depth" in stream and event_type != "trade")
        is_trade = (event_type == "trade") or ("@trade" in stream and event_type != "depthUpdate")

        if not is_depth and not is_trade:
            logger.info(f"Ignored unknown or unhandled event: event_type='{event_type}', stream='{stream}'")
            return

        if not symbol:
            self.malformed_packets_count += 1
            logger.warning(f"Malformed external packet: missing symbol in event '{event_type}', stream='{stream}'")
            return

        # Timestamp tracking
        ts = int(time.time() * 1000000)
        if isinstance(data, dict) and "E" in data:
            ts = int(data["E"]) * 1000
        if symbol not in self.first_packet_timestamp:
            self.first_packet_timestamp[symbol] = ts
        self.last_packet_timestamp[symbol] = ts

        # 1. RAW STAGE: Preserve unaltered raw message before normalization
        raw_writer = self.raw_writers.get(symbol)
        if raw_writer:
            raw_writer.write_raw(raw_str)

        # 2. NORMALIZED STAGE: Normalize and route to respective stream writer
        try:
            if is_depth:
                records = self.process_depth_message(msg)
                writer = self.writers.get(f"{symbol}_depth")
                if writer:
                    for r in records:
                        writer.write_event(r)
                else:
                    logger.debug(f"No writer registered for depth stream on {symbol}")
            elif is_trade:
                rec = self.process_trade_message(msg)
                writer = self.writers.get(f"{symbol}_trades")
                if writer:
                    writer.write_event(rec)
                else:
                    logger.debug(f"No writer registered for trades stream on {symbol}")
        except (KeyError, ValueError, TypeError) as exc:
            self.malformed_packets_count += 1
            logger.warning(
                f"Validation failure processing {symbol} {event_type} packet: {type(exc).__name__}: {exc}"
            )
        except Exception as exc:
            logger.error(
                f"Unexpected internal defect processing {symbol} {event_type} packet: {type(exc).__name__}: {exc}",
                exc_info=True,
            )

    async def _watchdog_loop(self) -> None:
        """Monitors for silent stall: process alive but zero received messages, and triggers periodic buffer flushes."""
        while self.is_running:
            await asyncio.sleep(5.0)
            # Periodic buffer flush for all active writers
            for writer in self.writers.values():
                try:
                    writer.flush()
                except Exception as exc:
                    logger.error(f"Error flushing normalized writer: {exc}")
            for raw_writer in self.raw_writers.values():
                try:
                    raw_writer.flush()
                except Exception as exc:
                    logger.error(f"Error flushing raw writer: {exc}")

            if self.last_message_time > 0:
                elapsed = time.time() - self.last_message_time
                if elapsed > self.config.watchdog_timeout_seconds:
                    logger.critical(
                        f"Watchdog alert: zero messages received for {elapsed:.1f}s "
                        f"(threshold: {self.config.watchdog_timeout_seconds}s)! Triggering socket recovery..."
                    )
                    if self._current_ws is not None and not getattr(self._current_ws, "closed", False):
                        try:
                            await self._current_ws.close()
                        except Exception as exc:
                            logger.error(f"Watchdog socket recovery error: {exc}")

    def check_health(self) -> Dict[str, Any]:
        """Returns health diagnostics, including silent failure watchdog status."""
        now = time.time()
        time_since_last_msg = (now - self.last_message_time) if self.last_message_time > 0 else 0.0
        is_silent_failure = (
            self.is_running
            and self.last_message_time > 0
            and time_since_last_msg > self.config.watchdog_timeout_seconds
        )

        return {
            "is_running": self.is_running,
            "reconnect_count": self.reconnect_count,
            "total_downtime_seconds": self.total_downtime_seconds,
            "sequence_gaps_count": len(self.sequence_gaps),
            "malformed_packets_count": self.malformed_packets_count,
            "duplicate_packets_count": self.duplicate_packets_count,
            "time_since_last_message_seconds": time_since_last_msg,
            "silent_stall_detected": is_silent_failure,
            "health_status": "CRITICAL_SILENT_FAILURE" if is_silent_failure else ("HEALTHY" if self.is_running else "STOPPED"),
        }

    async def run(self, max_seconds: Optional[float] = None) -> None:
        """Runs the event stream ingestion loop with WebSocket streaming and reconnect backoff."""
        self.is_running = True
        self.last_message_time = time.time()
        logger.info(
            f"Starting BinanceUSStreamCollector on venue '{self.config.venue}' for {self.config.symbols}"
        )

        # 1. Fetch initial depth snapshots
        for symbol in self.config.symbols:
            try:
                snap = self.fetch_rest_snapshot(symbol)
                writer = self.writers.get(f"{symbol.upper()}_depth")
                if writer:
                    now_us = snap["local_timestamp"]
                    for p, q in snap["bids"]:
                        writer.write_event({
                            "exchange": self.config.venue,
                            "symbol": symbol.upper(),
                            "timestamp": snap["timestamp"],
                            "local_timestamp": now_us,
                            "is_snapshot": "true",
                            "side": "bid",
                            "price": p,
                            "amount": q,
                        })
                    for p, q in snap["asks"]:
                        writer.write_event({
                            "exchange": self.config.venue,
                            "symbol": symbol.upper(),
                            "timestamp": snap["timestamp"],
                            "local_timestamp": now_us,
                            "is_snapshot": "true",
                            "side": "ask",
                            "price": p,
                            "amount": q,
                        })
                    logger.info(f"Initialized order book snapshot for {symbol} (lastUpdateId={snap['lastUpdateId']})")
            except Exception as exc:
                logger.warning(f"Could not fetch REST snapshot for {symbol}: {exc}")

        # Start background watchdog and automated checkpoint tasks
        self.watchdog_task = asyncio.create_task(self._watchdog_loop())
        self.checkpoint_task = asyncio.create_task(self._checkpoint_loop())

        # 2. Main collection loop with reconnection handling
        stream_url = self.build_stream_url()
        start_time = time.time()
        attempt = 0

        try:
            while self.is_running:
                if max_seconds is not None and (time.time() - start_time) >= max_seconds:
                    break

                try:
                    async with websockets.connect(
                        stream_url,
                        ping_interval=self.config.ws_ping_interval,
                        ping_timeout=self.config.ws_ping_timeout,
                    ) as ws:
                        self._current_ws = ws
                        logger.info("Connected to Binance.US WebSocket stream.")
                        attempt = 0  # reset attempt count on successful connect
                        while self.is_running:
                            if max_seconds is not None and (time.time() - start_time) >= max_seconds:
                                break
                            try:
                                msg_str = await asyncio.wait_for(ws.recv(), timeout=30.0)
                                self.dispatch_raw_message(msg_str)
                            except asyncio.TimeoutError:
                                # Send ping on idle
                                await ws.ping()
                except (websockets.ConnectionClosed, OSError, asyncio.TimeoutError) as exc:
                    if not self.is_running:
                        break
                    disconnect_time = time.time()
                    self.reconnect_count += 1
                    attempt += 1
                    backoff = min(60.0, self.config.reconnect_backoff_seconds * (2 ** (attempt - 1)))
                    logger.warning(f"Stream disconnected ({exc}). Reconnecting in {backoff:.1f}s (attempt {attempt})...")
                    await asyncio.sleep(backoff)
                    reconnect_time = time.time()
                    downtime = reconnect_time - disconnect_time
                    self.total_downtime_seconds += downtime
                    self.disconnect_events.append({
                        "disconnect_timestamp": disconnect_time,
                        "reconnect_timestamp": reconnect_time,
                        "downtime_seconds": downtime,
                        "reason": str(exc),
                    })
                    if attempt >= self.config.max_reconnect_attempts:
                        logger.error(f"Exceeded max reconnect attempts ({self.config.max_reconnect_attempts}). Stopping.")
                        break
        except asyncio.CancelledError:
            logger.info("Collector task cancelled.")
        finally:
            self.stop()

    async def _checkpoint_loop(self) -> None:
        """Schedules automated UTC midnight checkpoints."""
        last_date = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
        while self.is_running:
            await asyncio.sleep(30.0)
            current_date = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
            if current_date != last_date:
                for sym in self.config.symbols:
                    try:
                        ckpt = self.generate_daily_checkpoint(last_date, sym)
                        logger.info(
                            f"Generated automated UTC daily checkpoint for {last_date} {sym}: "
                            f"status={ckpt.get('continuity_status')}"
                        )
                    except Exception as exc:
                        logger.error(f"Failed to generate automated daily checkpoint for {last_date} {sym}: {exc}")
                last_date = current_date

    def generate_daily_checkpoint(self, date_str: str, symbol: str) -> Dict[str, Any]:
        """Generates a machine-readable qualification checkpoint for a completed UTC day."""
        symbol = symbol.upper()
        depth_writer = self.writers.get(f"{symbol}_depth")
        trades_writer = self.writers.get(f"{symbol}_trades")
        raw_writer = self.raw_writers.get(symbol)

        depth_events = depth_writer.events_written if depth_writer else 0
        trade_events = trades_writer.events_written if trades_writer else 0
        raw_messages = raw_writer.messages_written if raw_writer else 0
        total_events = depth_events + trade_events

        # Determine continuity
        if self.reconnect_count == 0 and len(self.sequence_gaps) == 0 and total_events > 0:
            continuity_status = "CONTINUOUS"
        elif self.reconnect_count > 0 or len(self.sequence_gaps) > 0:
            continuity_status = "INTERRUPTED"
        else:
            continuity_status = "EMPTY"

        # Checksums and disk free
        disk_free_bytes = 0
        try:
            _, _, disk_free_bytes = shutil.disk_usage(self.config.output_dir)
        except OSError:
            pass

        def _calc_sha(writer) -> str:
            if writer and getattr(writer, "current_file_path", None):
                p = writer.current_file_path
                if p.is_file():
                    try:
                        return hashlib.sha256(p.read_bytes()).hexdigest()
                    except Exception:
                        pass
            return ""

        raw_sha = _calc_sha(raw_writer)
        depth_sha = _calc_sha(depth_writer)
        trades_sha = _calc_sha(trades_writer)

        checkpoint = {
            "checkpoint_date": date_str,
            "symbol": symbol,
            "schema_version": self.config.schema_version,
            "collector_version": self.config.collector_version,
            "total_events_captured": total_events,
            "depth_updates_count": depth_events,
            "trades_count": trade_events,
            "corrupted_packets_count": self.malformed_packets_count,
            "duplicate_packets_count": self.duplicate_packets_count,
            "downtime_seconds": self.total_downtime_seconds,
            "sequence_gaps_detected": len(self.sequence_gaps),
            "first_packet_timestamp": self.first_packet_timestamp.get(symbol, 0),
            "last_packet_timestamp": self.last_packet_timestamp.get(symbol, 0),
            "continuity_status": continuity_status,
            "raw_file_sha256": raw_sha,
            "normalized_depth_sha256": depth_sha,
            "normalized_trades_sha256": trades_sha,
            "synthetic_data_used": self.config.allow_synthetic_fallback,
            "disk_free_bytes": disk_free_bytes,
            "reconnect_count": self.reconnect_count,

            # Backward-compatible fields
            "date": date_str,
            "event_count": total_events,
            "trade_count": trade_events,
            "depth_event_count": depth_events,
            "raw_messages_count": raw_messages,
            "sequence_statistics": {
                "sequence_gaps_count": len(self.sequence_gaps),
                "last_update_id": self.last_update_ids.get(symbol, 0),
            },
            "duplicate_count": self.duplicate_packets_count,
            "malformed_count": self.malformed_packets_count,
            "allow_synthetic_fallback": self.config.allow_synthetic_fallback,
            "generated_at": time.time(),
        }

        # Save checkpoint to disk
        checkpoint_dir = Path(self.config.checkpoint_dir)
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        ckpt_path = checkpoint_dir / f"checkpoint_{date_str}_{symbol}.json"
        ckpt_path.write_text(json.dumps(checkpoint, indent=2), encoding="utf-8")

        return checkpoint

    def stop(self) -> None:
        """Stops collector and flushes all registered buffer writers and raw message writers."""
        self.is_running = False
        if self.watchdog_task and not self.watchdog_task.done():
            self.watchdog_task.cancel()
        if self.checkpoint_task and not self.checkpoint_task.done():
            self.checkpoint_task.cancel()

        for writer in self.writers.values():
            writer.flush()
        for raw_writer in self.raw_writers.values():
            raw_writer.flush()
        logger.info("BinanceUSStreamCollector stopped, all normalized and raw writers flushed.")
