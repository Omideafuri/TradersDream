"""Validation module executing order-book reconstruction and schema checks on authentic Binance.US free sample."""

import csv
import json
from pathlib import Path
import sys
from typing import Dict, Any, List

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from phase10b.models import (
    TickTrade,
    L2Delta,
    L2Snapshot,
    BookSide,
    AggressorSide,
)
from phase10b.reconstructor import OrderBookReconstructor


def validate_trades_file(csv_path: Path) -> Dict[str, Any]:
    """Validate schema and data integrity of authentic trades CSV."""
    assert csv_path.is_file(), f"Trades file not found: {csv_path}"

    valid_trades = 0
    symbols = set()
    exchanges = set()
    timestamps = []

    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            assert "exchange" in row
            assert "symbol" in row
            assert "timestamp" in row
            assert "local_timestamp" in row
            assert "id" in row
            assert "side" in row
            assert "price" in row
            assert "amount" in row

            exchanges.add(row["exchange"])
            symbols.add(row["symbol"])
            ts = int(row["timestamp"])
            timestamps.append(ts)
            price = float(row["price"])
            amount = float(row["amount"])
            assert price > 0, f"Invalid price: {price}"
            assert amount > 0, f"Invalid amount: {amount}"
            assert row["side"] in ("buy", "sell", "unknown")

            valid_trades += 1

    return {
        "status": "VALID",
        "trade_count": valid_trades,
        "symbols": list(symbols),
        "exchanges": list(exchanges),
        "min_timestamp": min(timestamps) if timestamps else None,
        "max_timestamp": max(timestamps) if timestamps else None,
    }


def validate_orderbook_reconstruction(csv_path: Path) -> Dict[str, Any]:
    """Reconstruct order book from authentic incremental_book_L2 sample."""
    assert csv_path.is_file(), f"L2 file not found: {csv_path}"

    reconstructor = OrderBookReconstructor(symbol="BTCUSDT", exchange="binance-us", strict_mode=False)
    snapshot_loaded = False
    snapshot_bids = []
    snapshot_asks = []
    snapshot_ts = 0
    seq_counter = 1

    deltas_applied = 0
    spreads = []
    states_evaluated = 0

    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            is_snapshot = row["is_snapshot"].lower() == "true"
            side = BookSide.BID if row["side"].lower() == "bid" else BookSide.ASK
            price = float(row["price"])
            amount = float(row["amount"])
            ts = int(row["timestamp"]) // 1000  # convert us to ms
            local_ts = int(row["local_timestamp"]) // 1000

            if is_snapshot:
                snapshot_ts = ts
                if amount > 0:
                    if side == BookSide.BID:
                        snapshot_bids.append((price, amount))
                    else:
                        snapshot_asks.append((price, amount))
            else:
                if not snapshot_loaded and (snapshot_bids or snapshot_asks):
                    snap = L2Snapshot(
                        symbol="BTCUSDT",
                        exchange="binance-us",
                        exchange_timestamp_ms=snapshot_ts,
                        sequence_id=seq_counter,
                        bids=sorted(snapshot_bids, key=lambda x: x[0], reverse=True),
                        asks=sorted(snapshot_asks, key=lambda x: x[0]),
                        local_receive_timestamp_ms=snapshot_ts,
                    )
                    reconstructor.load_snapshot(snap)
                    snapshot_loaded = True
                    seq_counter += 1

                if snapshot_loaded:
                    delta = L2Delta(
                        symbol="BTCUSDT",
                        exchange="binance-us",
                        exchange_timestamp_ms=ts,
                        sequence_id=seq_counter,
                        side=side,
                        price=price,
                        quantity=amount,
                        local_receive_timestamp_ms=local_ts,
                    )
                    seq_counter += 1
                    state = reconstructor.apply_delta(delta)
                    deltas_applied += 1

                    if state.best_bid is not None and state.best_ask is not None:
                        spreads.append(state.spread)
                        states_evaluated += 1

    current_state = reconstructor.get_current_state()
    return {
        "status": "RECONSTRUCTION_SUCCESS",
        "snapshot_loaded": snapshot_loaded,
        "initial_bid_depth": len(snapshot_bids),
        "initial_ask_depth": len(snapshot_asks),
        "deltas_applied": deltas_applied,
        "states_evaluated": states_evaluated,
        "final_best_bid": current_state.best_bid,
        "final_best_ask": current_state.best_ask,
        "final_spread": current_state.spread,
        "min_spread": min(spreads) if spreads else None,
        "max_spread": max(spreads) if spreads else None,
        "avg_spread": sum(spreads) / len(spreads) if spreads else None,
    }


def run_full_validation() -> Dict[str, Any]:
    data_dir = Path(__file__).resolve().parent.parent / "data"
    trades_path = data_dir / "sample_binance-us_trades_2024-03-01_BTCUSDT.csv"
    l2_path = data_dir / "sample_binance-us_incremental_book_L2_2024-03-01_BTCUSDT.csv"

    trades_res = validate_trades_file(trades_path)
    l2_res = validate_orderbook_reconstruction(l2_path)

    return {
        "trades_validation": trades_res,
        "reconstruction_validation": l2_res,
    }


if __name__ == "__main__":
    res = run_full_validation()
    print(json.dumps(res, indent=2))
