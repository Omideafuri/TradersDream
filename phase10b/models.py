"""Data models and schemas for Phase 10B event-level market data and order-book reconstruction."""

from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple


class AggressorSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    UNKNOWN = "UNKNOWN"


class BookSide(str, Enum):
    BID = "BID"
    ASK = "ASK"


class GapSeverity(str, Enum):
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    FATAL = "FATAL"


@dataclass
class TickTrade:
    """Canonical representation of an individual executed trade event."""
    trade_id: str
    symbol: str
    exchange: str
    exchange_timestamp_ms: int
    price: float
    quantity: float
    aggressor_side: AggressorSide
    sequence_id: Optional[int] = None
    local_receive_timestamp_ms: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["aggressor_side"] = self.aggressor_side.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TickTrade":
        data_copy = dict(data)
        if isinstance(data_copy.get("aggressor_side"), str):
            data_copy["aggressor_side"] = AggressorSide(data_copy["aggressor_side"])
        return cls(**data_copy)


@dataclass
class L2Delta:
    """Incremental order-book update (add, modify, delete) at a price level."""
    symbol: str
    exchange: str
    exchange_timestamp_ms: int
    sequence_id: int
    side: BookSide
    price: float
    quantity: float  # 0.0 indicates deletion of the price level
    local_receive_timestamp_ms: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["side"] = self.side.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "L2Delta":
        data_copy = dict(data)
        if isinstance(data_copy.get("side"), str):
            data_copy["side"] = BookSide(data_copy["side"])
        return cls(**data_copy)


@dataclass
class L2Snapshot:
    """Full order-book depth snapshot at a discrete point in time."""
    symbol: str
    exchange: str
    exchange_timestamp_ms: int
    sequence_id: int
    bids: List[Tuple[float, float]]  # List of (price, quantity) sorted descending
    asks: List[Tuple[float, float]]  # List of (price, quantity) sorted ascending
    local_receive_timestamp_ms: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "L2Snapshot":
        data_copy = dict(data)
        data_copy["bids"] = [tuple(x) for x in data_copy.get("bids", [])]
        data_copy["asks"] = [tuple(x) for x in data_copy.get("asks", [])]
        return cls(**data_copy)


@dataclass
class ReconstructedBookState:
    """Normalized snapshot of the rebuilt order book after applying deltas."""
    symbol: str
    exchange: str
    timestamp_ms: int
    sequence_id: int
    best_bid: float
    best_ask: float
    spread: float
    spread_bps: float
    midpoint: float
    bid_depth_top5: float
    ask_depth_top5: float
    bid_levels: List[Tuple[float, float]]  # top N (price, size)
    ask_levels: List[Tuple[float, float]]  # top N (price, size)
    is_crossed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SequenceGapRecord:
    """Detailed record of an observed sequence discontinuity or packet loss."""
    symbol: str
    exchange: str
    expected_sequence: int
    observed_sequence: int
    gap_size: int
    timestamp_ms: int
    severity: GapSeverity
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["severity"] = self.severity.value
        return d


@dataclass
class ValidationIssue:
    """Record of an invariant violation, timing anomaly, or data defect."""
    check_name: str
    symbol: str
    timestamp_ms: int
    description: str
    severity: GapSeverity
    event_payload: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["severity"] = self.severity.value
        return d
