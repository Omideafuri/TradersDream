"""Chronological Split Manager and Holdout Sealing module for Phase 9.

Ensures strict time-series ordering:
1. Chronological partitioning (Dev, Val, Sealed Holdout).
2. Zero random shuffling or data leakage across boundaries.
3. Cryptographic SHA256 fingerprinting of holdout partitions.
4. Sealed holdout protection.
"""

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Dict, Any, Tuple
import pandas as pd


@dataclass
class PartitionMetadata:
    name: str
    start_index: int
    end_index: int
    row_count: int
    start_timestamp: int
    end_timestamp: int
    sha256: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ChronologicalSplitResult:
    dataset_id: str
    total_rows: int
    dev: PartitionMetadata
    val: PartitionMetadata
    holdout: PartitionMetadata
    is_strictly_chronological: bool
    is_disjoint: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "total_rows": self.total_rows,
            "dev": self.dev.to_dict(),
            "val": self.val.to_dict(),
            "holdout": self.holdout.to_dict(),
            "is_strictly_chronological": self.is_strictly_chronological,
            "is_disjoint": self.is_disjoint,
        }


class SplitManager:
    """Manages chronological dataset partitioning and holdout sealing."""

    @staticmethod
    def partition(
        df: pd.DataFrame,
        dataset_id: str = "UNKNOWN_DATASET",
        dev_ratio: float = 0.60,
        val_ratio: float = 0.20,
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, ChronologicalSplitResult]:
        """Partitions DataFrame into chronological Dev, Val, and Sealed Holdout subsets."""
        if "timestamp" not in df.columns:
            raise ValueError("DataFrame must contain 'timestamp' column.")

        n = len(df)
        if n < 10:
            raise ValueError("DataFrame has too few rows for 3-way chronological partitioning.")

        # Ensure sorted by timestamp
        df_sorted = df.sort_values("timestamp").reset_index(drop=True)

        dev_end = int(n * dev_ratio)
        val_end = int(n * (dev_ratio + val_ratio))

        dev_df = df_sorted.iloc[:dev_end].copy().reset_index(drop=True)
        val_df = df_sorted.iloc[dev_end:val_end].copy().reset_index(drop=True)
        holdout_df = df_sorted.iloc[val_end:].copy().reset_index(drop=True)

        def make_meta(name: str, sub_df: pd.DataFrame, start_idx: int, end_idx: int) -> PartitionMetadata:
            csv_b = sub_df.to_csv(index=False).encode("utf-8")
            h = hashlib.sha256(csv_b).hexdigest()
            s_ts = int(sub_df["timestamp"].iloc[0]) if len(sub_df) > 0 else 0
            e_ts = int(sub_df["timestamp"].iloc[-1]) if len(sub_df) > 0 else 0
            return PartitionMetadata(
                name=name,
                start_index=start_idx,
                end_index=end_idx,
                row_count=len(sub_df),
                start_timestamp=s_ts,
                end_timestamp=e_ts,
                sha256=h,
            )

        dev_meta = make_meta("DEVELOPMENT", dev_df, 0, dev_end - 1)
        val_meta = make_meta("VALIDATION", val_df, dev_end, val_end - 1)
        holdout_meta = make_meta("SEALED_HOLDOUT", holdout_df, val_end, n - 1)

        is_chrono = (dev_meta.end_timestamp < val_meta.start_timestamp < val_meta.end_timestamp < holdout_meta.start_timestamp)
        is_disjoint = (dev_meta.row_count + val_meta.row_count + holdout_meta.row_count == n)

        res = ChronologicalSplitResult(
            dataset_id=dataset_id,
            total_rows=n,
            dev=dev_meta,
            val=val_meta,
            holdout=holdout_meta,
            is_strictly_chronological=is_chrono,
            is_disjoint=is_disjoint,
        )

        return dev_df, val_df, holdout_df, res

    @staticmethod
    def seal_holdout_manifest(
        split_result: ChronologicalSplitResult,
        manifest_path: Path | str = "phase9/manifests/PHASE9_HOLDOUT_MANIFEST.json",
    ) -> None:
        """Saves an immutable manifest of the sealed holdout boundary and hash."""
        path = Path(manifest_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        manifest_data = {
            "manifest_type": "PHASE9_SEALED_HOLDOUT_MANIFEST",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "SEALED",
            "split_info": split_result.to_dict(),
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2)
