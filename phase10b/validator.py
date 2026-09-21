"""Validation and Quality Assurance Engine for Event-Level Market Data."""

from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
import numpy as np

from phase10b.models import (
    TickTrade,
    L2Delta,
    L2Snapshot,
    ReconstructedBookState,
    SequenceGapRecord,
    ValidationIssue,
    GapSeverity,
    BookSide,
)


@dataclass
class StreamValidationReport:
    """Comprehensive validation metrics for an event-level dataset."""
    symbol: str
    exchange: str
    total_events: int
    trade_count: int
    delta_count: int
    snapshot_count: int
    sequence_gaps: int
    max_sequence_gap: int
    timestamp_anomalies: int
    duplicate_events: int
    out_of_order_events: int
    crossed_book_events: int
    invalid_price_events: int
    invalid_quantity_events: int
    coverage_start_ms: int
    coverage_end_ms: int
    timespan_hours: float
    is_valid: bool
    issues: List[ValidationIssue] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["issues"] = [x.to_dict() for x in self.issues]
        return d


class EventDataValidator:
    """Rigorous validator enforcing physical invariants, causal monotonicity, and sequence continuity."""

    @staticmethod
    def validate_trades(trades: List[TickTrade]) -> Tuple[bool, List[ValidationIssue]]:
        """Validates individual tick trades against schema, uniqueness, and monotonicity."""
        issues: List[ValidationIssue] = []
        seen_ids = set()
        last_ts = None

        for t in trades:
            # 1. ID Uniqueness
            if t.trade_id in seen_ids:
                issues.append(ValidationIssue(
                    check_name="duplicate_trade_id",
                    symbol=t.symbol,
                    timestamp_ms=t.exchange_timestamp_ms,
                    description=f"Duplicate trade ID observed: {t.trade_id}",
                    severity=GapSeverity.CRITICAL,
                ))
            seen_ids.add(t.trade_id)

            # 2. Price and Quantity Bounds
            if t.price <= 0:
                issues.append(ValidationIssue(
                    check_name="invalid_trade_price",
                    symbol=t.symbol,
                    timestamp_ms=t.exchange_timestamp_ms,
                    description=f"Non-positive trade price: {t.price}",
                    severity=GapSeverity.FATAL,
                ))
            if t.quantity <= 0:
                issues.append(ValidationIssue(
                    check_name="invalid_trade_quantity",
                    symbol=t.symbol,
                    timestamp_ms=t.exchange_timestamp_ms,
                    description=f"Non-positive trade quantity: {t.quantity}",
                    severity=GapSeverity.FATAL,
                ))

            # 3. Timestamp Monotonicity
            if last_ts is not None and t.exchange_timestamp_ms < last_ts:
                issues.append(ValidationIssue(
                    check_name="trade_timestamp_out_of_order",
                    symbol=t.symbol,
                    timestamp_ms=t.exchange_timestamp_ms,
                    description=f"Trade timestamp {t.exchange_timestamp_ms} < last {last_ts}",
                    severity=GapSeverity.CRITICAL,
                ))
            last_ts = t.exchange_timestamp_ms

        is_valid = len([i for i in issues if i.severity in (GapSeverity.CRITICAL, GapSeverity.FATAL)]) == 0
        return is_valid, issues

    @staticmethod
    def validate_deltas(deltas: List[L2Delta]) -> Tuple[bool, List[ValidationIssue], List[SequenceGapRecord]]:
        """Validates order book deltas for sequence continuity, timestamp monotonicity, and valid price/size."""
        issues: List[ValidationIssue] = []
        gaps: List[SequenceGapRecord] = []
        
        last_seq = None
        last_ts = None
        seen_seq = set()

        for d in deltas:
            # 1. Duplicate sequence
            if d.sequence_id in seen_seq:
                issues.append(ValidationIssue(
                    check_name="duplicate_delta_sequence",
                    symbol=d.symbol,
                    timestamp_ms=d.exchange_timestamp_ms,
                    description=f"Duplicate sequence ID: {d.sequence_id}",
                    severity=GapSeverity.CRITICAL,
                ))
            seen_seq.add(d.sequence_id)

            # 2. Sequence Continuity
            if last_seq is not None:
                expected_seq = last_seq + 1
                if d.sequence_id != expected_seq:
                    gap_size = d.sequence_id - expected_seq
                    gaps.append(SequenceGapRecord(
                        symbol=d.symbol,
                        exchange=d.exchange,
                        expected_sequence=expected_seq,
                        observed_sequence=d.sequence_id,
                        gap_size=gap_size,
                        timestamp_ms=d.exchange_timestamp_ms,
                        severity=GapSeverity.FATAL if gap_size > 0 else GapSeverity.WARNING,
                        notes=f"Sequence discontinuity: {gap_size}",
                    ))

            # 3. Timestamp Monotonicity
            if last_ts is not None and d.exchange_timestamp_ms < last_ts:
                issues.append(ValidationIssue(
                    check_name="delta_timestamp_out_of_order",
                    symbol=d.symbol,
                    timestamp_ms=d.exchange_timestamp_ms,
                    description=f"Delta timestamp {d.exchange_timestamp_ms} < last {last_ts}",
                    severity=GapSeverity.CRITICAL,
                ))

            # 4. Value Bounds
            if d.price <= 0:
                issues.append(ValidationIssue(
                    check_name="invalid_delta_price",
                    symbol=d.symbol,
                    timestamp_ms=d.exchange_timestamp_ms,
                    description=f"Non-positive delta price: {d.price}",
                    severity=GapSeverity.FATAL,
                ))
            if d.quantity < 0:
                issues.append(ValidationIssue(
                    check_name="invalid_delta_quantity",
                    symbol=d.symbol,
                    timestamp_ms=d.exchange_timestamp_ms,
                    description=f"Negative delta quantity: {d.quantity}",
                    severity=GapSeverity.FATAL,
                ))

            last_seq = d.sequence_id
            last_ts = d.exchange_timestamp_ms

        is_valid = len(gaps) == 0 and len([i for i in issues if i.severity in (GapSeverity.CRITICAL, GapSeverity.FATAL)]) == 0
        return is_valid, issues, gaps

    @staticmethod
    def audit_stream_integrity(
        symbol: str,
        exchange: str,
        trades: List[TickTrade],
        deltas: List[L2Delta],
        snapshots: List[L2Snapshot],
    ) -> StreamValidationReport:
        """Runs a complete end-to-end audit of all event streams for an asset."""
        issues: List[ValidationIssue] = []
        trade_valid, trade_issues = EventDataValidator.validate_trades(trades)
        delta_valid, delta_issues, delta_gaps = EventDataValidator.validate_deltas(deltas)

        issues.extend(trade_issues)
        issues.extend(delta_issues)

        all_ts = [t.exchange_timestamp_ms for t in trades] + [d.exchange_timestamp_ms for d in deltas] + [s.exchange_timestamp_ms for s in snapshots]
        cov_start = min(all_ts) if all_ts else 0
        cov_end = max(all_ts) if all_ts else 0
        timespan_hrs = (cov_end - cov_start) / (1000.0 * 3600.0) if cov_end > cov_start else 0.0

        dup_count = len([i for i in issues if "duplicate" in i.check_name])
        ooo_count = len([i for i in issues if "out_of_order" in i.check_name])
        crossed_count = len([i for i in issues if "crossed_book" in i.check_name])
        price_errs = len([i for i in issues if "invalid" in i.check_name and "price" in i.check_name])
        qty_errs = len([i for i in issues if "invalid" in i.check_name and "quantity" in i.check_name])

        is_valid = (
            trade_valid
            and delta_valid
            and len(delta_gaps) == 0
            and len([i for i in issues if i.severity == GapSeverity.FATAL]) == 0
        )

        return StreamValidationReport(
            symbol=symbol,
            exchange=exchange,
            total_events=len(trades) + len(deltas) + len(snapshots),
            trade_count=len(trades),
            delta_count=len(deltas),
            snapshot_count=len(snapshots),
            sequence_gaps=len(delta_gaps),
            max_sequence_gap=max([g.gap_size for g in delta_gaps]) if delta_gaps else 0,
            timestamp_anomalies=ooo_count,
            duplicate_events=dup_count,
            out_of_order_events=ooo_count,
            crossed_book_events=crossed_count,
            invalid_price_events=price_errs,
            invalid_quantity_events=qty_errs,
            coverage_start_ms=cov_start,
            coverage_end_ms=cov_end,
            timespan_hours=round(timespan_hrs, 4),
            is_valid=is_valid,
            issues=issues,
        )
