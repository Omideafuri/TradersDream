"""Phase 10B: Event-Level Market Data Acquisition & Validation Package."""

from phase10b.models import (
    TickTrade,
    L2Delta,
    L2Snapshot,
    ReconstructedBookState,
    SequenceGapRecord,
    ValidationIssue,
    AggressorSide,
    BookSide,
    GapSeverity,
)
from phase10b.reconstructor import OrderBookReconstructor, OrderBookReconstructionError
from phase10b.validator import EventDataValidator, StreamValidationReport
from phase10b.alignment import TradeBookAligner, AlignedTradeRecord, AlignmentReport, AlignmentError
from phase10b.holdout import EventHoldoutManager, EventHoldoutManifest, PartitionMetadata, HoldoutContaminationError
from phase10b.auditor import Phase10BDataAuditor

__all__ = [
    "TickTrade",
    "L2Delta",
    "L2Snapshot",
    "ReconstructedBookState",
    "SequenceGapRecord",
    "ValidationIssue",
    "AggressorSide",
    "BookSide",
    "GapSeverity",
    "OrderBookReconstructor",
    "OrderBookReconstructionError",
    "EventDataValidator",
    "StreamValidationReport",
    "TradeBookAligner",
    "AlignedTradeRecord",
    "AlignmentReport",
    "AlignmentError",
    "EventHoldoutManager",
    "EventHoldoutManifest",
    "PartitionMetadata",
    "HoldoutContaminationError",
    "Phase10BDataAuditor",
]
