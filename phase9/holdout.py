"""Holdout sealing and manifest management for Phase 9B.

Ensures chronological partitioning (60% Dev / 20% Val / 20% Sealed Holdout)
and immutable cryptographic sealing before any model training.
"""

from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
import pandas as pd

from phase9.split_manager import SplitManager, ChronologicalSplitResult


@dataclass
class AssetHoldoutRecord:
    asset: str
    symbol: str
    total_rows: int
    dataset_sha256: str
    dev_start: str
    dev_end: str
    dev_rows: int
    dev_sha256: str
    validation_start: str
    validation_end: str
    validation_rows: int
    validation_sha256: str
    holdout_start: str
    holdout_end: str
    holdout_rows: int
    holdout_sha256: str
    sealed_at: str
    status: str = "SEALED"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class Phase9HoldoutManager:
    """Manages creation, verification, and serialization of sealed holdout manifests."""

    def __init__(
        self,
        manifest_json_path: Path | str = "data/phase9_results/phase9b_holdout_manifest.json",
        manifest_md_path: Path | str = "PHASE9B_HOLDOUT_MANIFEST.md",
    ):
        self.manifest_json_path = Path(manifest_json_path)
        self.manifest_md_path = Path(manifest_md_path)
        self.records: Dict[str, AssetHoldoutRecord] = {}

    def seal_dataset(
        self,
        df: pd.DataFrame,
        asset: str,
        symbol: str,
        dev_ratio: float = 0.60,
        val_ratio: float = 0.20,
    ) -> AssetHoldoutRecord:
        """Splits DataFrame chronologically and seals holdout boundary with SHA256 hashes."""
        dev_df, val_df, holdout_df, split_res = SplitManager.partition(
            df=df,
            dataset_id=f"DATASET_{asset.upper()}",
            dev_ratio=dev_ratio,
            val_ratio=val_ratio,
        )

        full_csv = df.to_csv(index=False).encode("utf-8")
        dataset_sha256 = hashlib.sha256(full_csv).hexdigest()

        def to_iso(ts_ms: int) -> str:
            return datetime.fromtimestamp(ts_ms / 1000.0, timezone.utc).isoformat()

        record = AssetHoldoutRecord(
            asset=asset.upper(),
            symbol=symbol.upper(),
            total_rows=len(df),
            dataset_sha256=dataset_sha256,
            dev_start=to_iso(split_res.dev.start_timestamp),
            dev_end=to_iso(split_res.dev.end_timestamp),
            dev_rows=split_res.dev.row_count,
            dev_sha256=split_res.dev.sha256,
            validation_start=to_iso(split_res.val.start_timestamp),
            validation_end=to_iso(split_res.val.end_timestamp),
            validation_rows=split_res.val.row_count,
            validation_sha256=split_res.val.sha256,
            holdout_start=to_iso(split_res.holdout.start_timestamp),
            holdout_end=to_iso(split_res.holdout.end_timestamp),
            holdout_rows=split_res.holdout.row_count,
            holdout_sha256=split_res.holdout.sha256,
            sealed_at=datetime.now(timezone.utc).isoformat(),
            status="SEALED",
        )

        self.records[asset.upper()] = record
        return record

    def save_manifests(self) -> None:
        """Persists JSON and Markdown manifests."""
        self.manifest_json_path.parent.mkdir(parents=True, exist_ok=True)
        self.manifest_md_path.parent.mkdir(parents=True, exist_ok=True)

        # JSON manifest
        payload = {
            "manifest_type": "PHASE9B_SEALED_HOLDOUT_MANIFEST",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "ALL_HOLDOUTS_SEALED",
            "assets": {k: v.to_dict() for k, v in self.records.items()},
        }
        with open(self.manifest_json_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        # Markdown manifest
        md_lines = [
            "# PHASE 9B SEALED HOLDOUT MANIFEST",
            f"**Sealed Timestamp**: {payload['created_at']}  ",
            "**Status**: **`SEALED & IMMUTABLE`**  ",
            "**Policy**: Chronological non-overlapping splits (60% Dev / 20% Val / 20% Holdout). Shuffling strictly prohibited.",
            "",
            "---",
            "",
            "## Sealed Asset Partitions",
            "",
            "| Asset | Total Rows | Dev Rows (60%) | Val Rows (20%) | Holdout Rows (20%) | Holdout Start UTC | Holdout End UTC | Holdout SHA256 |",
            "| :--- | :---: | :---: | :---: | :---: | :--- | :--- | :--- |",
        ]

        for asset, rec in self.records.items():
            md_lines.append(
                f"| **{rec.asset}** ({rec.symbol}) | {rec.total_rows:,} | {rec.dev_rows:,} | {rec.validation_rows:,} | "
                f"{rec.holdout_rows:,} | `{rec.holdout_start}` | `{rec.holdout_end}` | `{rec.holdout_sha256[:16]}...` |"
            )

        md_lines.extend([
            "",
            "---",
            "",
            "## Detailed Partition Hashes",
            "",
        ])

        for asset, rec in self.records.items():
            md_lines.extend([
                f"### {rec.asset} ({rec.symbol})",
                f"- **Full Dataset SHA256**: `{rec.dataset_sha256}`",
                f"- **Development (60%)**: `{rec.dev_start}` to `{rec.dev_end}` ({rec.dev_rows:,} bars) | Hash: `{rec.dev_sha256}`",
                f"- **Validation (20%)**: `{rec.validation_start}` to `{rec.validation_end}` ({rec.validation_rows:,} bars) | Hash: `{rec.validation_sha256}`",
                f"- **Sealed Holdout (20%)**: `{rec.holdout_start}` to `{rec.holdout_end}` ({rec.holdout_rows:,} bars) | Hash: `{rec.holdout_sha256}`",
                "",
            ])

        md_lines.extend([
            "---",
            "",
            "## Holdout Sealing Rules",
            "1. Holdout observations are strictly forbidden from feature extraction tuning, prompt selection, or threshold calibration.",
            "2. Any mutation to the underlying data requires incrementing the dataset version and creating a new holdout seal.",
            "3. The holdout partition is unlocked exclusively during final out-of-sample evaluation.",
        ])

        with open(self.manifest_md_path, "w", encoding="utf-8") as f:
            f.write("\n".join(md_lines) + "\n")
