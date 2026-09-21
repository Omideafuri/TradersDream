"""Dataset Registry for Phase 9 research.

Maintains an immutable, versioned catalog of all datasets (historical, ingested, and derived).
Prevents silent overwrites, tracks cryptographic hashes, and enables auditability.
"""

from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
import pandas as pd

from phase9.provenance import DatasetProvenanceRecord, compute_file_sha256, SyntheticStatus, IndependenceStatus


class DatasetRegistry:
    """Central registry for immutable dataset cataloging and verification."""

    def __init__(self, storage_path: Optional[Path | str] = None):
        self.storage_path = Path(storage_path) if storage_path else Path("phase9/manifests/dataset_registry.json")
        self._registry: Dict[str, DatasetProvenanceRecord] = {}
        self.load()

    def register_dataset(self, record: DatasetProvenanceRecord, overwrite: bool = False) -> None:
        """Registers a dataset record in the catalog.
        
        Args:
            record: The DatasetProvenanceRecord to register.
            overwrite: If True, explicitly allows replacing an existing record.
                       Otherwise raises ValueError on duplicate ID with different hash.
        """
        # If file_path is provided, verify or populate sha256 and row_count
        if record.file_path and Path(record.file_path).exists():
            computed_hash = compute_file_sha256(record.file_path)
            if not record.sha256:
                record.sha256 = computed_hash
            elif record.sha256 != computed_hash:
                raise ValueError(
                    f"Provided SHA256 {record.sha256} does not match computed file hash {computed_hash} for {record.file_path}"
                )

        if record.dataset_id in self._registry and not overwrite:
            existing = self._registry[record.dataset_id]
            if existing.sha256 != record.sha256:
                raise ValueError(
                    f"Dataset ID '{record.dataset_id}' already exists with different hash "
                    f"({existing.sha256} != {record.sha256}). Create a new version identifier (e.g. {record.dataset_id}_V2)."
                )

        self._registry[record.dataset_id] = record
        self.save()

    def get_dataset(self, dataset_id: str) -> DatasetProvenanceRecord:
        """Retrieves a dataset record by ID."""
        if dataset_id not in self._registry:
            raise KeyError(f"Dataset '{dataset_id}' not found in registry.")
        return self._registry[dataset_id]

    def list_datasets(
        self,
        asset: Optional[str] = None,
        independence_status: Optional[str] = None,
        synthetic_status: Optional[str] = None,
    ) -> List[DatasetProvenanceRecord]:
        """Lists registered datasets with optional filtering."""
        results = list(self._registry.values())
        if asset:
            results = [r for r in results if r.asset.upper() == asset.upper()]
        if independence_status:
            results = [r for r in results if r.independence_status == independence_status]
        if synthetic_status:
            results = [r for r in results if r.synthetic_status == synthetic_status]
        return results

    def verify_dataset(self, dataset_id: str) -> Dict[str, Any]:
        """Verifies integrity of a registered dataset against its physical file."""
        record = self.get_dataset(dataset_id)
        if not record.file_path:
            return {"dataset_id": dataset_id, "status": "NO_FILE_PATH", "is_valid": False}
        path = Path(record.file_path)
        if not path.is_file():
            return {"dataset_id": dataset_id, "status": "FILE_NOT_FOUND", "is_valid": False}

        current_hash = compute_file_sha256(path)
        is_hash_valid = (current_hash == record.sha256)

        row_count_valid = True
        actual_rows = -1
        try:
            df = pd.read_csv(path)
            actual_rows = len(df)
            row_count_valid = (actual_rows == record.row_count)
        except Exception:
            row_count_valid = False

        return {
            "dataset_id": dataset_id,
            "status": "VALID" if (is_hash_valid and row_count_valid) else "CORRUPTED",
            "is_valid": is_hash_valid and row_count_valid,
            "registered_sha256": record.sha256,
            "current_sha256": current_hash,
            "registered_rows": record.row_count,
            "actual_rows": actual_rows,
        }

    def compare_datasets(self, dataset_id_a: str, dataset_id_b: str) -> Dict[str, Any]:
        """Compares metadata between two registered datasets."""
        rec_a = self.get_dataset(dataset_id_a)
        rec_b = self.get_dataset(dataset_id_b)
        return {
            "dataset_a": rec_a.to_dict(),
            "dataset_b": rec_b.to_dict(),
            "same_asset": rec_a.asset == rec_b.asset,
            "same_timeframe": rec_a.timeframe == rec_b.timeframe,
            "same_sha256": rec_a.sha256 == rec_b.sha256,
            "both_independent": (
                rec_a.independence_status == IndependenceStatus.INDEPENDENT and
                rec_b.independence_status == IndependenceStatus.INDEPENDENT
            ),
        }

    def save(self) -> None:
        """Persists registry catalog to JSON file."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = {k: v.to_dict() for k, v in self._registry.items()}
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def load(self) -> None:
        """Loads registry catalog from JSON file if it exists."""
        if self.storage_path.is_file():
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._registry = {k: DatasetProvenanceRecord.from_dict(v) for k, v in data.items()}
            except Exception:
                self._registry = {}

    def register_historical_phase_datasets(self, base_dir: Path | str = "data/historical") -> None:
        """Registers the existing Phase 1–8 historical datasets with strict provenance classification."""
        base = Path(base_dir)
        configs = [
            {
                "id": "HIST_BTCUSDT_5M_202401_V1",
                "asset": "BTC",
                "symbol": "BTCUSDT",
                "filename": "BTCUSDT_5m_candles.csv",
                "synthetic": SyntheticStatus.GENUINE,
                "independence": IndependenceStatus.INDEPENDENT,
                "notes": "Historical baseline 5m BTC candle series from Jan 2024 (1,500 bars). Genuinely independent.",
            },
            {
                "id": "HIST_ETHUSDT_5M_202401_V1",
                "asset": "ETH",
                "symbol": "ETHUSDT",
                "filename": "ETHUSDT_5m_candles.csv",
                "synthetic": SyntheticStatus.SYNTHETIC,
                "independence": IndependenceStatus.NON_INDEPENDENT,
                "notes": "SYNTHETIC / NON-INDEPENDENT / HISTORICAL-ONLY. DISC-001: generated by scaling BTC price series (r > 0.9999).",
            },
            {
                "id": "HIST_SOLUSDT_5M_202401_V1",
                "asset": "SOL",
                "symbol": "SOLUSDT",
                "filename": "SOLUSDT_5m_candles.csv",
                "synthetic": SyntheticStatus.SYNTHETIC,
                "independence": IndependenceStatus.NON_INDEPENDENT,
                "notes": "SYNTHETIC / NON-INDEPENDENT / HISTORICAL-ONLY. DISC-001: generated by scaling BTC price series (r > 0.9999).",
            },
        ]

        for cfg in configs:
            fpath = base / cfg["filename"]
            if not fpath.exists():
                continue
            df = pd.read_csv(fpath)
            start_ts = ""
            end_ts = ""
            if "timestamp" in df.columns and len(df) > 0:
                start_ts = str(df["timestamp"].iloc[0])
                end_ts = str(df["timestamp"].iloc[-1])

            record = DatasetProvenanceRecord(
                dataset_id=cfg["id"],
                asset=cfg["asset"],
                symbol=cfg["symbol"],
                exchange="LOCAL_HISTORICAL",
                market_type="SPOT",
                instrument_type="CANDLE",
                timeframe="5m",
                start_timestamp=start_ts,
                end_timestamp=end_ts,
                row_count=len(df),
                source="HISTORICAL_ARCHIVE",
                source_url="local://data/historical/" + cfg["filename"],
                retrieval_timestamp="2026-09-21T00:00:00Z",
                timezone="UTC",
                schema_version="1.0.0",
                sha256=compute_file_sha256(fpath),
                synthetic_status=cfg["synthetic"],
                independence_status=cfg["independence"],
                license_or_usage_notes=cfg["notes"],
                file_path=str(fpath),
            )
            self.register_dataset(record, overwrite=True)
