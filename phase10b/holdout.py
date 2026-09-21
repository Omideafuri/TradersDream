"""Holdout Partitioning and Leakage Verification for Phase 10B Event-Level Data."""

from dataclasses import dataclass, asdict
import hashlib
import json
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional


class HoldoutContaminationError(Exception):
    """Raised when data leakage or temporal overlap between partitions is detected."""
    pass


@dataclass
class PartitionMetadata:
    """Metadata for a single chronological partition (Dev, Val, or Holdout)."""
    name: str
    event_count: int
    start_ts_ms: int
    end_ts_ms: int
    start_utc: str
    end_utc: str
    sha256: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EventHoldoutManifest:
    """Immutable manifest locking the Phase 10B chronological splits."""
    symbol: str
    exchange: str
    total_events: int
    dev_partition: PartitionMetadata
    val_partition: PartitionMetadata
    holdout_partition: PartitionMetadata
    is_sealed: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "exchange": self.exchange,
            "total_events": self.total_events,
            "dev_partition": self.dev_partition.to_dict(),
            "val_partition": self.val_partition.to_dict(),
            "holdout_partition": self.holdout_partition.to_dict(),
            "is_sealed": self.is_sealed,
        }


class EventHoldoutManager:
    """Manages strict 60/20/20 chronological partitioning and leakage verification."""

    @staticmethod
    def partition_events(
        events: List[Dict[str, Any]],
        timestamp_key: str = "exchange_timestamp_ms",
        id_key: str = "trade_id",
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Partitions an event sequence into 60% Dev, 20% Val, 20% Holdout chronologically."""
        if len(events) < 10:
            raise ValueError("Insufficient events to partition (minimum 10 events required).")

        # Sort strictly chronologically
        sorted_events = sorted(events, key=lambda x: x[timestamp_key])

        n = len(sorted_events)
        n_dev = int(n * 0.60)
        n_val = int(n * 0.20)

        dev_events = sorted_events[:n_dev]
        val_events = sorted_events[n_dev : n_dev + n_val]
        holdout_events = sorted_events[n_dev + n_val :]

        # Run verification checks
        EventHoldoutManager.verify_no_contamination(
            dev_events, val_events, holdout_events, timestamp_key=timestamp_key, id_key=id_key
        )

        return dev_events, val_events, holdout_events

    @staticmethod
    def verify_no_contamination(
        dev: List[Dict[str, Any]],
        val: List[Dict[str, Any]],
        holdout: List[Dict[str, Any]],
        timestamp_key: str = "exchange_timestamp_ms",
        id_key: str = "trade_id",
    ) -> None:
        """Verifies strict temporal separation and zero overlapping IDs across partitions."""
        if not dev or not val or not holdout:
            raise HoldoutContaminationError("One or more partitions are empty.")

        dev_max_ts = max(x[timestamp_key] for x in dev)
        val_min_ts = min(x[timestamp_key] for x in val)
        val_max_ts = max(x[timestamp_key] for x in val)
        holdout_min_ts = min(x[timestamp_key] for x in holdout)

        # 1. Temporal Monotonicity across splits
        if dev_max_ts > val_min_ts:
            raise HoldoutContaminationError(
                f"Temporal leak: Dev max timestamp ({dev_max_ts}) > Val min timestamp ({val_min_ts})"
            )
        if val_max_ts > holdout_min_ts:
            raise HoldoutContaminationError(
                f"Temporal leak: Val max timestamp ({val_max_ts}) > Holdout min timestamp ({holdout_min_ts})"
            )

        # 2. Identifier Uniqueness across splits
        dev_ids = {x[id_key] for x in dev if id_key in x}
        val_ids = {x[id_key] for x in val if id_key in x}
        holdout_ids = {x[id_key] for x in holdout if id_key in x}

        overlap_dev_val = dev_ids.intersection(val_ids)
        if overlap_dev_val:
            raise HoldoutContaminationError(f"Duplicate IDs between Dev and Val: {len(overlap_dev_val)} found")

        overlap_val_holdout = val_ids.intersection(holdout_ids)
        if overlap_val_holdout:
            raise HoldoutContaminationError(f"Duplicate IDs between Val and Holdout: {len(overlap_val_holdout)} found")

        overlap_dev_holdout = dev_ids.intersection(holdout_ids)
        if overlap_dev_holdout:
            raise HoldoutContaminationError(f"Duplicate IDs between Dev and Holdout: {len(overlap_dev_holdout)} found")

    @staticmethod
    def compute_partition_sha256(events: List[Dict[str, Any]]) -> str:
        """Computes deterministic SHA256 of JSON-serialized event partition."""
        payload = json.dumps(events, sort_keys=True).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()
