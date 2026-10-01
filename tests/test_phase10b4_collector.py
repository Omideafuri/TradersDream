"""Automated unit and integration tests for Phase 10B.4 Binance.US Collector.

Comprehensive behavioral test coverage addressing all 12 release audit requirements:
1. Realistic trade dispatch (e, E, s, t, p, q, b, a, T, m)
2. Realistic depth dispatch (e="depthUpdate", E, s, U, u, b, a)
3. Combined-stream envelope handling (@trade, @depth)
4. Malformed JSON handling (no crash, structured warning)
5. Unknown event handling (gracefully ignored, no crash)
6. Dedicated writer routing per symbol and stream
7. Depth event serialization (exact normalized schema)
8. Trade event serialization (exact normalized schema)
9. Multiple sequential alternating messages (depth and trade)
10. Collector stop behavior (flushes writers, sets is_running=False)
11. Per-message exception isolation (packet N failure does not terminate packet N+1)
12. No cross-routing between depth and trades (no trade to depth, no depth to trade)
"""

import json
from pathlib import Path
import pytest
from typing import List, Dict, Any

from phase10b4.collector.config import CollectorConfig
from phase10b4.collector.stream_client import BinanceUSStreamCollector


class MockBufferWriter:
    """Mock writer collecting written events in-memory with flush tracking."""
    def __init__(self):
        self.events: List[Dict[str, Any]] = []
        self.flushed: bool = False

    def write_event(self, event: Dict[str, Any]) -> None:
        self.events.append(event)

    def flush(self) -> None:
        self.flushed = True


@pytest.fixture
def collector(tmp_path: Path):
    cfg = CollectorConfig(
        venue="binance-us",
        symbols=["BTCUSDT", "ETHUSDT"],
        output_dir=tmp_path,
        enable_gzip_compression=False,
    )
    c = BinanceUSStreamCollector(config=cfg)
    return c


def test_1_realistic_trade_dispatch(collector: BinanceUSStreamCollector):
    """Requirement 1: Realistic trade payload with buyer/seller order IDs routes to trade processor."""
    trade_writer = MockBufferWriter()
    depth_writer = MockBufferWriter()
    collector.register_writer("BTCUSDT_trades", trade_writer)
    collector.register_writer("BTCUSDT_depth", depth_writer)

    raw_trade = json.dumps({
        "e": "trade",
        "E": 1700000000100,
        "s": "BTCUSDT",
        "t": 987654321,
        "p": "65432.10",
        "q": "0.1500",
        "b": 111111,
        "a": 222222,
        "T": 1700000000099,
        "m": True,
        "M": True,
    })

    collector.dispatch_raw_message(raw_trade)

    assert len(depth_writer.events) == 0, "Depth writer was incorrectly invoked for trade payload!"
    assert len(trade_writer.events) == 1
    rec = trade_writer.events[0]
    assert rec["symbol"] == "BTCUSDT"
    assert rec["id"] == "987654321"
    assert rec["price"] == 65432.10
    assert rec["amount"] == 0.1500
    assert rec["side"] == "sell"  # is_buyer_maker True -> sell


def test_2_realistic_depth_dispatch(collector: BinanceUSStreamCollector):
    """Requirement 2: Realistic depth update routes to depth processor and updates sequence state."""
    trade_writer = MockBufferWriter()
    depth_writer = MockBufferWriter()
    collector.register_writer("BTCUSDT_trades", trade_writer)
    collector.register_writer("BTCUSDT_depth", depth_writer)

    raw_depth = json.dumps({
        "e": "depthUpdate",
        "E": 1700000000200,
        "s": "BTCUSDT",
        "U": 5001,
        "u": 5005,
        "b": [["65430.00", "1.25"], ["65429.00", "0.00"]],
        "a": [["65435.00", "2.50"]],
    })

    collector.dispatch_raw_message(raw_depth)

    assert len(trade_writer.events) == 0, "Trade writer was incorrectly invoked for depth payload!"
    assert len(depth_writer.events) == 3  # 2 bids + 1 ask
    assert collector.last_update_ids.get("BTCUSDT") == 5005


def test_3_combined_stream_envelope(collector: BinanceUSStreamCollector):
    """Requirement 3: Combined stream envelope with 'stream' and 'data' routes correctly."""
    trade_writer = MockBufferWriter()
    depth_writer = MockBufferWriter()
    collector.register_writer("BTCUSDT_trades", trade_writer)
    collector.register_writer("BTCUSDT_depth", depth_writer)

    combined_trade = json.dumps({
        "stream": "btcusdt@trade",
        "data": {
            "e": "trade",
            "E": 1700000000300,
            "s": "BTCUSDT",
            "t": 987654322,
            "p": "65433.00",
            "q": "0.0500",
            "b": 333333,
            "a": 444444,
            "T": 1700000000299,
            "m": False,
        }
    })
    collector.dispatch_raw_message(combined_trade)
    assert len(trade_writer.events) == 1
    assert len(depth_writer.events) == 0

    combined_depth = json.dumps({
        "stream": "btcusdt@depth@100ms",
        "data": {
            "e": "depthUpdate",
            "E": 1700000000400,
            "s": "BTCUSDT",
            "U": 5006,
            "u": 5010,
            "b": [["65431.00", "0.80"]],
            "a": [["65436.00", "1.10"]],
        }
    })
    collector.dispatch_raw_message(combined_depth)
    assert len(trade_writer.events) == 1
    assert len(depth_writer.events) == 2


def test_4_malformed_json_handling(collector: BinanceUSStreamCollector):
    """Requirement 4: Malformed or unparseable JSON strings do not crash collector."""
    trade_writer = MockBufferWriter()
    collector.register_writer("BTCUSDT_trades", trade_writer)

    # Must not raise
    collector.dispatch_raw_message("{invalid_json_missing_quotes: 123,")
    collector.dispatch_raw_message("")
    collector.dispatch_raw_message("not even json")
    assert len(trade_writer.events) == 0


def test_5_unknown_event_handling(collector: BinanceUSStreamCollector):
    """Requirement 5: Unknown or unhandled events are logged and discarded without crashing."""
    trade_writer = MockBufferWriter()
    depth_writer = MockBufferWriter()
    collector.register_writer("BTCUSDT_trades", trade_writer)
    collector.register_writer("BTCUSDT_depth", depth_writer)

    unknown_event = json.dumps({
        "e": "24hrTicker",
        "s": "BTCUSDT",
        "c": "65000.00",
        "h": "66000.00",
    })
    collector.dispatch_raw_message(unknown_event)

    assert len(trade_writer.events) == 0
    assert len(depth_writer.events) == 0


def test_6_writer_routing_isolation(collector: BinanceUSStreamCollector):
    """Requirement 6: Events for BTCUSDT do not leak to ETHUSDT writers."""
    btc_trades = MockBufferWriter()
    eth_trades = MockBufferWriter()
    collector.register_writer("BTCUSDT_trades", btc_trades)
    collector.register_writer("ETHUSDT_trades", eth_trades)

    btc_trade_msg = json.dumps({
        "e": "trade",
        "E": 1700000000500,
        "s": "BTCUSDT",
        "t": 111,
        "p": "65000.0",
        "q": "1.0",
        "b": 1,
        "a": 2,
        "m": True,
    })
    collector.dispatch_raw_message(btc_trade_msg)

    assert len(btc_trades.events) == 1
    assert len(eth_trades.events) == 0


def test_7_depth_event_serialization(collector: BinanceUSStreamCollector):
    """Requirement 7: Depth event records adhere strictly to canonical schema types and fields."""
    depth_writer = MockBufferWriter()
    collector.register_writer("BTCUSDT_depth", depth_writer)

    depth_msg = json.dumps({
        "e": "depthUpdate",
        "E": 1700000000600,
        "s": "BTCUSDT",
        "U": 100,
        "u": 101,
        "b": [["65100.50", "3.20"]],
        "a": [],
    })
    collector.dispatch_raw_message(depth_msg)

    rec = depth_writer.events[0]
    expected_fields = {"exchange", "symbol", "timestamp", "local_timestamp", "is_snapshot", "side", "price", "amount"}
    assert set(rec.keys()) == expected_fields
    assert rec["exchange"] == "binance-us"
    assert rec["symbol"] == "BTCUSDT"
    assert rec["timestamp"] == 1700000000600000
    assert rec["is_snapshot"] == "false"
    assert rec["side"] == "bid"
    assert isinstance(rec["price"], float) and rec["price"] == 65100.50
    assert isinstance(rec["amount"], float) and rec["amount"] == 3.20


def test_8_trade_event_serialization(collector: BinanceUSStreamCollector):
    """Requirement 8: Trade event records adhere strictly to canonical schema types and fields."""
    trade_writer = MockBufferWriter()
    collector.register_writer("BTCUSDT_trades", trade_writer)

    trade_msg = json.dumps({
        "e": "trade",
        "E": 1700000000700,
        "s": "BTCUSDT",
        "t": 888999,
        "p": "65200.75",
        "q": "0.450",
        "b": 12,
        "a": 34,
        "m": False,
    })
    collector.dispatch_raw_message(trade_msg)

    rec = trade_writer.events[0]
    expected_fields = {"exchange", "symbol", "timestamp", "local_timestamp", "id", "side", "price", "amount"}
    assert set(rec.keys()) == expected_fields
    assert rec["exchange"] == "binance-us"
    assert rec["symbol"] == "BTCUSDT"
    assert rec["timestamp"] == 1700000000700000
    assert rec["id"] == "888999"
    assert rec["side"] == "buy"
    assert isinstance(rec["price"], float) and rec["price"] == 65200.75
    assert isinstance(rec["amount"], float) and rec["amount"] == 0.450


def test_9_multiple_sequential_messages(collector: BinanceUSStreamCollector):
    """Requirement 9: Ingesting sequential alternating trade and depth messages works continuously."""
    trade_writer = MockBufferWriter()
    depth_writer = MockBufferWriter()
    collector.register_writer("BTCUSDT_trades", trade_writer)
    collector.register_writer("BTCUSDT_depth", depth_writer)

    for i in range(10):
        if i % 2 == 0:
            collector.dispatch_raw_message(json.dumps({
                "e": "trade",
                "E": 1700000000000 + i * 100,
                "s": "BTCUSDT",
                "t": 1000 + i,
                "p": f"{65000.0 + i}",
                "q": "0.1",
                "b": 10,
                "a": 20,
                "m": (i % 4 == 0),
            }))
        else:
            collector.dispatch_raw_message(json.dumps({
                "e": "depthUpdate",
                "E": 1700000000000 + i * 100,
                "s": "BTCUSDT",
                "U": 2000 + i,
                "u": 2000 + i + 1,
                "b": [[f"{65000.0 - i}", "1.0"]],
                "a": [[f"{65000.0 + i}", "1.0"]],
            }))

    assert len(trade_writer.events) == 5
    assert len(depth_writer.events) == 10  # 5 depth updates * 2 levels (1 bid + 1 ask)


def test_10_collector_stop_behavior(collector: BinanceUSStreamCollector):
    """Requirement 10: Calling stop() flushes all registered buffer writers and sets is_running=False."""
    trade_writer = MockBufferWriter()
    depth_writer = MockBufferWriter()
    collector.register_writer("BTCUSDT_trades", trade_writer)
    collector.register_writer("BTCUSDT_depth", depth_writer)

    collector.is_running = True
    collector.stop()

    assert collector.is_running is False
    assert trade_writer.flushed is True
    assert depth_writer.flushed is True


def test_11_exception_isolation_and_continuation(collector: BinanceUSStreamCollector):
    """Requirement 11: Failures on malformed packets do not crash stream or impede valid packets."""
    trade_writer = MockBufferWriter()
    collector.register_writer("BTCUSDT_trades", trade_writer)

    # 1. Invalid syntax
    collector.dispatch_raw_message("{not_valid_json")
    # 2. Non-dict root
    collector.dispatch_raw_message('"string_not_object"')
    # 3. Missing required trade fields (missing 'p' and 't')
    collector.dispatch_raw_message(json.dumps({"e": "trade", "E": 100, "s": "BTCUSDT", "q": "0.1", "m": True}))
    # 4. Valid trade
    collector.dispatch_raw_message(json.dumps({
        "e": "trade", "E": 1700000000800, "s": "BTCUSDT", "t": 55555, "p": "65100.0", "q": "0.2", "b": 1, "a": 2, "m": True
    }))
    # 5. Non-numeric price
    collector.dispatch_raw_message(json.dumps({
        "e": "trade", "E": 1700000000900, "s": "BTCUSDT", "t": 55556, "p": "NaN_OR_CORRUPT", "q": "0.2", "b": 1, "a": 2, "m": True
    }))
    # 6. Valid trade
    collector.dispatch_raw_message(json.dumps({
        "e": "trade", "E": 1700000001000, "s": "BTCUSDT", "t": 55557, "p": "65105.0", "q": "0.3", "b": 1, "a": 2, "m": False
    }))

    assert len(trade_writer.events) == 2
    assert trade_writer.events[0]["id"] == "55555"
    assert trade_writer.events[1]["id"] == "55557"


def test_12_no_cross_routing_between_depth_and_trades(collector: BinanceUSStreamCollector):
    """Requirement 12: Adversarial payload with 'b' and 'a' keys never routes to depth."""
    trade_writer = MockBufferWriter()
    depth_writer = MockBufferWriter()
    collector.register_writer("BTCUSDT_trades", trade_writer)
    collector.register_writer("BTCUSDT_depth", depth_writer)

    # Trade payload containing 'b' and 'a' integer IDs
    adversarial_trade = json.dumps({
        "e": "trade",
        "E": 1700000002000,
        "s": "BTCUSDT",
        "t": 777,
        "p": "65000.0",
        "q": "0.5",
        "b": 99999,
        "a": 88888,
        "m": True,
    })
    collector.dispatch_raw_message(adversarial_trade)

    assert len(depth_writer.events) == 0, "Trade message was cross-routed to depth writer!"
    assert len(trade_writer.events) == 1

    # Depth payload containing bids and asks
    depth_msg = json.dumps({
        "e": "depthUpdate",
        "E": 1700000002100,
        "s": "BTCUSDT",
        "U": 300,
        "u": 305,
        "b": [["65000.0", "1.0"]],
        "a": [["65001.0", "1.0"]],
    })
    collector.dispatch_raw_message(depth_msg)

    assert len(trade_writer.events) == 1, "Depth message was cross-routed to trade writer!"
    assert len(depth_writer.events) == 2
