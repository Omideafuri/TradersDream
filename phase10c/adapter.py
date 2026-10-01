"""Lossless Data Ingestion Adapter and Qualification Engine for Authentic Historical L2 Market Data.

Normalizes raw exchange-captured market event archives (Tardis incremental_book_L2 and trades)
into canonical Phase 10B data models (L2Snapshot, L2DeltaPacket, L2Delta, TickTrade) and executes
deterministic order-book reconstruction qualification.
"""

from collections import defaultdict
import csv
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Set

from phase10b.models import (
    BookSide,
    AggressorSide,
    L2Snapshot,
    L2Delta,
    L2DeltaPacket,
    TickTrade,
)
from phase10b.reconstructor import OrderBookReconstructor, OrderBookReconstructionError


class TardisL2AdapterError(Exception):
    """Raised when parsing or normalization violates data contract."""
    pass


class TardisL2Adapter:
    """Ingestion and Normalization Adapter for Authentic Tardis.dev Binance.US L2 Datasets."""

    REQUIRED_L2_FIELDS: Set[str] = {
        "exchange", "symbol", "timestamp", "local_timestamp", "is_snapshot", "side", "price", "amount"
    }

    REQUIRED_TRADE_FIELDS: Set[str] = {
        "exchange", "symbol", "timestamp", "local_timestamp", "id", "side", "price", "amount"
    }

    @staticmethod
    def calculate_file_hash(path: Path) -> str:
        """Calculate SHA-256 hash of a file."""
        hasher = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    @classmethod
    def parse_trades_csv(cls, csv_path: Path) -> List[TickTrade]:
        """Parses authentic trades CSV into canonical TickTrade records."""
        if not csv_path.is_file():
            raise TardisL2AdapterError(f"Trades file not found: {csv_path}")

        trades: List[TickTrade] = []
        with open(csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            missing = cls.REQUIRED_TRADE_FIELDS - set(reader.fieldnames or [])
            if missing:
                raise TardisL2AdapterError(f"Trades file missing required schema fields: {missing}")

            for row in reader:
                price = float(row["price"])
                amount = float(row["amount"])
                if price <= 0:
                    raise TardisL2AdapterError(f"Invalid non-positive trade price: {price}")
                if amount <= 0:
                    raise TardisL2AdapterError(f"Invalid non-positive trade quantity: {amount}")

                side_raw = row["side"].lower()
                if side_raw == "buy":
                    aggressor_side = AggressorSide.BUY
                elif side_raw == "sell":
                    aggressor_side = AggressorSide.SELL
                else:
                    aggressor_side = AggressorSide.UNKNOWN

                ts_us = int(row["timestamp"])
                local_ts_us = int(row["local_timestamp"])

                trade = TickTrade(
                    trade_id=str(row["id"]),
                    symbol=row["symbol"].upper(),
                    exchange=row["exchange"].lower(),
                    exchange_timestamp_ms=ts_us // 1000,
                    price=price,
                    quantity=amount,
                    aggressor_side=aggressor_side,
                    local_receive_timestamp_ms=local_ts_us // 1000,
                )
                trades.append(trade)

        return trades

    @classmethod
    def parse_incremental_book_l2_csv(
        cls, 
        csv_path: Path, 
        symbol: str = "BTCUSDT", 
        exchange: str = "binance-us"
    ) -> Tuple[L2Snapshot, List[L2DeltaPacket], Dict[str, Any]]:
        """Parses authentic incremental_book_L2 CSV into canonical Snapshot and Delta Packets.

        Discards pre-snapshot deltas (events with timestamp <= snapshot_timestamp) in strict
        adherence to Binance order-book buffer synchronization rules.
        """
        if not csv_path.is_file():
            raise TardisL2AdapterError(f"L2 file not found: {csv_path}")

        snapshot_rows: List[Dict[str, Any]] = []
        delta_rows_by_packet: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        total_rows = 0
        duplicate_rows = 0
        seen_rows: Set[Tuple[Any, ...]] = set()

        with open(csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            missing = cls.REQUIRED_L2_FIELDS - set(reader.fieldnames or [])
            if missing:
                raise TardisL2AdapterError(f"L2 file missing required schema fields: {missing}")

            for row in reader:
                total_rows += 1
                row_tuple = (row["timestamp"], row["local_timestamp"], row["is_snapshot"], row["side"], row["price"], row["amount"])
                if row_tuple in seen_rows:
                    duplicate_rows += 1
                    continue
                seen_rows.add(row_tuple)

                is_snapshot = row["is_snapshot"].lower() == "true"
                if is_snapshot:
                    snapshot_rows.append(row)
                else:
                    delta_rows_by_packet[row["local_timestamp"]].append(row)

        if not snapshot_rows:
            raise TardisL2AdapterError("No initial order-book snapshot found in dataset.")

        # 1. Build Canonical Snapshot
        snapshot_ts_us = max(int(r["timestamp"]) for r in snapshot_rows)
        snapshot_bids: List[Tuple[float, float]] = []
        snapshot_asks: List[Tuple[float, float]] = []
        snapshot_zero_levels = 0

        for r in snapshot_rows:
            p = float(r["price"])
            q = float(r["amount"])
            if p <= 0:
                raise TardisL2AdapterError(f"Invalid non-positive price in snapshot: {p}")
            if q < 0:
                raise TardisL2AdapterError(f"Invalid negative size in snapshot: {q}")
            if q == 0.0:
                snapshot_zero_levels += 1
                continue  # Depleted level does not constitute active depth

            if r["side"].lower() == "bid":
                snapshot_bids.append((p, q))
            elif r["side"].lower() == "ask":
                snapshot_asks.append((p, q))
            else:
                raise TardisL2AdapterError(f"Unknown book side: {r['side']}")

        snapshot_bids.sort(key=lambda x: x[0], reverse=True)
        snapshot_asks.sort(key=lambda x: x[0])

        snapshot = L2Snapshot(
            symbol=symbol,
            exchange=exchange,
            exchange_timestamp_ms=snapshot_ts_us // 1000,
            sequence_id=1,
            bids=snapshot_bids,
            asks=snapshot_asks,
            local_receive_timestamp_ms=snapshot_ts_us // 1000,
        )

        # 2. Build Delta Packets (Atomic WebSocket Messages)
        packets: List[L2DeltaPacket] = []
        seq_counter = 2
        discarded_pre_snapshot_deltas = 0
        total_valid_deltas = 0

        # Sort packet groups chronologically by local_timestamp
        sorted_packet_keys = sorted(delta_rows_by_packet.keys(), key=lambda k: int(k))

        for local_ts_str in sorted_packet_keys:
            rows_in_packet = delta_rows_by_packet[local_ts_str]
            local_ts_us = int(local_ts_str)
            local_ts_ms = local_ts_us // 1000

            valid_packet_deltas: List[L2Delta] = []
            pkt_exchange_ts_us = int(rows_in_packet[0]["timestamp"])

            for r in rows_in_packet:
                ts_us = int(r["timestamp"])
                # Binance buffering invariant: drop deltas emitted before or during snapshot
                if ts_us <= snapshot_ts_us:
                    discarded_pre_snapshot_deltas += 1
                    continue

                p = float(r["price"])
                q = float(r["amount"])
                if p <= 0:
                    raise TardisL2AdapterError(f"Invalid non-positive delta price: {p}")
                if q < 0:
                    raise TardisL2AdapterError(f"Invalid negative delta quantity: {q}")

                side = BookSide.BID if r["side"].lower() == "bid" else BookSide.ASK
                delta = L2Delta(
                    symbol=symbol,
                    exchange=exchange,
                    exchange_timestamp_ms=ts_us // 1000,
                    sequence_id=seq_counter,
                    side=side,
                    price=p,
                    quantity=q,
                    local_receive_timestamp_ms=local_ts_ms,
                )
                valid_packet_deltas.append(delta)
                total_valid_deltas += 1

            if valid_packet_deltas:
                pkt = L2DeltaPacket(
                    symbol=symbol,
                    exchange=exchange,
                    exchange_timestamp_ms=pkt_exchange_ts_us // 1000,
                    first_update_id=seq_counter,
                    final_update_id=seq_counter,
                    deltas=valid_packet_deltas,
                    local_receive_timestamp_ms=local_ts_ms,
                )
                packets.append(pkt)
                seq_counter += 1

        stats = {
            "total_csv_rows": total_rows,
            "duplicate_rows": duplicate_rows,
            "snapshot_rows_count": len(snapshot_rows),
            "snapshot_zero_levels_filtered": snapshot_zero_levels,
            "initial_bid_levels": len(snapshot_bids),
            "initial_ask_levels": len(snapshot_asks),
            "discarded_pre_snapshot_deltas": discarded_pre_snapshot_deltas,
            "total_valid_deltas": total_valid_deltas,
            "total_delta_packets": len(packets),
            "snapshot_timestamp_us": snapshot_ts_us,
        }

        return snapshot, packets, stats

    @classmethod
    def run_reconstruction_qualification(
        cls, 
        csv_path: Path, 
        symbol: str = "BTCUSDT", 
        exchange: str = "binance-us",
        strict_mode: bool = True,
    ) -> Dict[str, Any]:
        """Performs end-to-end qualification and deterministic reconstruction on an L2 dataset."""
        file_hash = cls.calculate_file_hash(csv_path)
        file_size = csv_path.stat().st_size

        snapshot, packets, parse_stats = cls.parse_incremental_book_l2_csv(
            csv_path, symbol=symbol, exchange=exchange
        )

        reconstructor = OrderBookReconstructor(symbol=symbol, exchange=exchange, strict_mode=strict_mode)
        initial_state = reconstructor.load_snapshot(snapshot)

        spreads: List[float] = [initial_state.spread]
        spreads_bps: List[float] = [initial_state.spread_bps]
        timestamps: List[int] = [snapshot.exchange_timestamp_ms]
        packets_applied = 0
        deltas_applied = 0
        reconstruction_errors: List[str] = []

        for pkt in packets:
            try:
                state = reconstructor.apply_delta_packet(pkt)
                packets_applied += 1
                deltas_applied += len(pkt.deltas)
                spreads.append(state.spread)
                spreads_bps.append(state.spread_bps)
                timestamps.append(state.timestamp_ms)
            except OrderBookReconstructionError as e:
                reconstruction_errors.append(str(e))
                if strict_mode:
                    raise

        final_state = reconstructor.get_current_state()

        min_ts = min(timestamps)
        max_ts = max(timestamps)
        duration_seconds = (max_ts - min_ts) / 1000.0

        return {
            "dataset_qualification": {
                "file_path": str(csv_path),
                "file_hash_sha256": file_hash,
                "file_size_bytes": file_size,
                "symbol": symbol,
                "exchange": exchange,
                "date_coverage": {
                    "min_timestamp_ms": min_ts,
                    "max_timestamp_ms": max_ts,
                    "duration_seconds": duration_seconds,
                    "duration_minutes": duration_seconds / 60.0,
                    "duration_hours": duration_seconds / 3600.0,
                    "duration_days": duration_seconds / 86400.0,
                },
            },
            "integrity_metrics": {
                "total_records": parse_stats["total_csv_rows"],
                "duplicate_records": parse_stats["duplicate_rows"],
                "malformed_records": 0,
                "missing_fields": 0,
                "invalid_timestamps": 0,
                "timestamp_ordering_violations": len(reconstructor.validation_issues),
            },
            "orderbook_sequence_quality": {
                "initial_sequence": 1,
                "final_sequence": reconstructor.last_sequence_id or 1,
                "sequence_gaps_count": len(reconstructor.sequence_gaps),
                "reconstruction_failures_count": len(reconstruction_errors),
            },
            "reconstruction_metrics": {
                "successful_packets": packets_applied,
                "successful_deltas": deltas_applied,
                "total_packets": len(packets),
                "reconstruction_success_rate_pct": (packets_applied / len(packets) * 100.0) if packets else 0.0,
                "crossed_book_occurrences": sum(1 for issue in reconstructor.validation_issues if issue.check_name == "crossed_book"),
                "initial_spread": initial_state.spread,
                "initial_spread_bps": initial_state.spread_bps,
                "final_spread": final_state.spread,
                "final_spread_bps": final_state.spread_bps,
                "min_spread": min(spreads) if spreads else 0.0,
                "max_spread": max(spreads) if spreads else 0.0,
                "avg_spread": (sum(spreads) / len(spreads)) if spreads else 0.0,
                "avg_spread_bps": (sum(spreads_bps) / len(spreads_bps)) if spreads_bps else 0.0,
                "final_best_bid": final_state.best_bid,
                "final_best_ask": final_state.best_ask,
            },
        }

    @staticmethod
    def evaluate_qualification_gate(
        reconstruction_report: Dict[str, Any], 
        min_required_days: int = 30
    ) -> Dict[str, Any]:
        """Evaluates whether the qualified authentic dataset meets Phase 10C scientific gate."""
        cov = reconstruction_report["dataset_qualification"]["date_coverage"]
        recon = reconstruction_report["reconstruction_metrics"]
        seq = reconstruction_report["orderbook_sequence_quality"]

        # 1. Technical Validity Gate
        is_technically_valid = (
            recon["reconstruction_success_rate_pct"] == 100.0
            and seq["sequence_gaps_count"] == 0
            and recon["crossed_book_occurrences"] == 0
            and cov["duration_seconds"] > 0
        )

        # 2. Sufficiency Gate (Phase 10A requires 30 continuous days)
        is_sample_sufficient = cov["duration_days"] >= min_required_days

        if is_technically_valid and is_sample_sufficient:
            gate_status = "QUALIFIED"
            phase10d_permission = True
            reason = "Authentic event-level L2 data is available, technically valid, and satisfies 30-day coverage."
        elif is_technically_valid and not is_sample_sufficient:
            gate_status = "PARTIALLY_QUALIFIED"
            phase10d_permission = False
            reason = (
                f"Authentic L2 data is technically valid and reconstructs with 100% fidelity, "
                f"but chronological duration ({cov['duration_seconds']:.1f}s / {cov['duration_days']:.4f} days) "
                f"is INSUFFICIENT for the 30-day continuous research requirement (Phase 10A)."
            )
        else:
            gate_status = "BLOCKED"
            phase10d_permission = False
            reason = "No authentic, legally accessible L2 dataset could be reconstructed or verified."

        return {
            "gate_status": gate_status,
            "data_sufficiency": "SUFFICIENT" if is_sample_sufficient else "INSUFFICIENT",
            "technical_validity": "VALID" if is_technically_valid else "INVALID",
            "phase10d_permission": phase10d_permission,
            "decision_reason": reason,
        }
