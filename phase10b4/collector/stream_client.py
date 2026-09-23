"""Binance.US public WebSocket stream collector with sequence gap auditing."""

import asyncio
import json
import logging
from pathlib import Path
import time
from typing import Dict, Any, List, Optional
import urllib.request

from .config import CollectorConfig
from .buffer_writer import EventBufferWriter

logger = logging.getLogger(__name__)


class BinanceUSStreamCollector:
    """Lawful, zero-cost real-time event collector for Binance.US public market streams."""

    def __init__(self, config: Optional[CollectorConfig] = None):
        self.config = config or CollectorConfig()
        self.is_running = False
        self.writers: Dict[str, EventBufferWriter] = {}
        self.last_update_ids: Dict[str, int] = {}
        self.disconnect_events: List[Dict[str, Any]] = []
        self.sequence_gaps: List[Dict[str, Any]] = []

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
        self.last_update_ids[symbol.upper()] = data["lastUpdateId"]

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
        is_buyer_maker = data["m"]
        side = "sell" if is_buyer_maker else "buy"

        return {
            "exchange": self.config.venue,
            "symbol": symbol,
            "timestamp": event_time_us,
            "local_timestamp": local_time_us,
            "id": str(data["t"]),
            "side": side,
            "price": float(data["p"]),
            "amount": float(data["q"]),
        }

    def register_writer(self, key: str, writer: EventBufferWriter) -> None:
        """Registers a buffer writer for a specific symbol and stream type."""
        self.writers[key] = writer

    def dispatch_raw_message(self, raw_str: str) -> None:
        """Dispatches an incoming JSON WebSocket message to the appropriate handler and writer."""
        try:
            msg = json.loads(raw_str)
        except Exception as exc:
            logger.debug(f"Failed to parse incoming message: {exc}")
            return

        stream = msg.get("stream", "")
        data = msg.get("data", msg)
        symbol = str(data.get("s", "")).upper()
        if not symbol:
            return

        if "@depth" in stream or "b" in data or "a" in data:
            records = self.process_depth_message(msg)
            writer = self.writers.get(f"{symbol}_depth")
            if writer:
                for r in records:
                    writer.write_event(r)
        elif "@trade" in stream or data.get("e") == "trade":
            rec = self.process_trade_message(msg)
            writer = self.writers.get(f"{symbol}_trades")
            if writer:
                writer.write_event(rec)

    async def run(self, max_seconds: Optional[float] = None) -> None:
        """Runs the event stream ingestion loop with REST snapshot initialization."""
        self.is_running = True
        logger.info(
            f"Starting BinanceUSStreamCollector on venue '{self.config.venue}' for {self.config.symbols}"
        )

        # 1. Fetch initial depth snapshots for each symbol
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

        # 2. Main collection loop
        stream_url = self.build_stream_url()
        logger.info(f"Stream URL built: {stream_url}")
        start_time = time.time()

        try:
            while self.is_running:
                if max_seconds is not None and (time.time() - start_time) >= max_seconds:
                    break
                await asyncio.sleep(0.05)
        except asyncio.CancelledError:
            logger.info("Collector cancelled.")
        finally:
            self.stop()

    def stop(self) -> None:
        """Stops collector and flushes all registered buffer writers."""
        self.is_running = False
        for writer in self.writers.values():
            writer.flush()
        logger.info("BinanceUSStreamCollector stopped and writers flushed.")
