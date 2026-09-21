"""Dataset provenance and immutable metadata module for Phase 9.

Ensures every historical, ingested, or benchmark dataset is cryptographically hashed,
explicitly classified by independence and synthetic status, and fully auditable.
"""

from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any, List


class SyntheticStatus:
    GENUINE = "GENUINE"
    SYNTHETIC = "SYNTHETIC"
    UNKNOWN = "UNKNOWN"


class IndependenceStatus:
    INDEPENDENT = "INDEPENDENT"
    NON_INDEPENDENT = "NON_INDEPENDENT"
    UNKNOWN = "UNKNOWN"


def compute_file_sha256(file_path: Path | str) -> str:
    """Computes deterministic SHA256 checksum of a given file."""
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"File not found for hashing: {path}")
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


@dataclass
class DatasetProvenanceRecord:
    """Immutable provenance record for a market or microstructure dataset."""
    dataset_id: str
    asset: str
    symbol: str
    exchange: str
    market_type: str  # SPOT, PERPETUAL, MARGIN, SIMULATED
    instrument_type: str  # CANDLE, ORDERBOOK_L2, TRADE_FLOW, FUNDING, TICK
    timeframe: str  # 5m, 1m, 1s, tick
    start_timestamp: str
    end_timestamp: str
    row_count: int
    source: str
    source_url: str
    retrieval_timestamp: str
    timezone: str = "UTC"
    schema_version: str = "1.0.0"
    sha256: str = ""
    synthetic_status: str = SyntheticStatus.UNKNOWN
    independence_status: str = IndependenceStatus.UNKNOWN
    parent_dataset: Optional[str] = None
    license_or_usage_notes: str = ""
    file_path: Optional[str] = None
    metadata_extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DatasetProvenanceRecord":
        return cls(**data)
