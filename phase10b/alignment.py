"""Causal Trade-to-Order-Book Alignment Engine."""

from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any, Tuple
import numpy as np

from phase10b.models import TickTrade, ReconstructedBookState


class AlignmentError(Exception):
    """Raised when a temporal lookahead or causal violation occurs in alignment."""
    pass


@dataclass
class AlignedTradeRecord:
    """An executed trade causally linked to the immediately preceding order book state."""
    trade: TickTrade
    preceding_book: ReconstructedBookState
    book_age_ms: int  # trade.exchange_timestamp_ms - preceding_book.timestamp_ms
    effective_spread_bps: float
    is_causally_valid: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trade": self.trade.to_dict(),
            "preceding_book": self.preceding_book.to_dict(),
            "book_age_ms": self.book_age_ms,
            "effective_spread_bps": self.effective_spread_bps,
            "is_causally_valid": self.is_causally_valid,
        }


@dataclass
class AlignmentReport:
    """Statistical summary of causal trade-to-book alignment quality."""
    total_trades: int
    aligned_trades: int
    unmatched_trades: int
    stale_book_trades: int
    max_book_age_ms: int
    median_book_age_ms: float
    p95_book_age_ms: float
    causal_violations: int
    is_valid: bool


class TradeBookAligner:
    """Performs deterministic causal alignment between trade events and order-book states."""

    def __init__(self, max_stale_book_ms: int = 5000):
        self.max_stale_book_ms = max_stale_book_ms

    def align_stream(
        self,
        trades: List[TickTrade],
        book_states: List[ReconstructedBookState],
    ) -> Tuple[List[AlignedTradeRecord], AlignmentReport]:
        """Aligns a time-ordered sequence of trades with time-ordered book states causally."""
        aligned_records: List[AlignedTradeRecord] = []
        book_ages: List[int] = []
        unmatched_count = 0
        stale_count = 0
        causal_violations = 0

        # Both streams must be sorted by exchange timestamp
        sorted_trades = sorted(trades, key=lambda x: x.exchange_timestamp_ms)
        sorted_books = sorted(book_states, key=lambda x: x.timestamp_ms)

        book_idx = 0
        n_books = len(sorted_books)

        for trade in sorted_trades:
            # Advance book index to the latest book state with timestamp <= trade timestamp
            while book_idx + 1 < n_books and sorted_books[book_idx + 1].timestamp_ms <= trade.exchange_timestamp_ms:
                book_idx += 1

            if not sorted_books or sorted_books[book_idx].timestamp_ms > trade.exchange_timestamp_ms:
                # No preceding book state exists
                unmatched_count += 1
                continue

            current_book = sorted_books[book_idx]

            # Invariant: t_book <= t_trade
            if current_book.timestamp_ms > trade.exchange_timestamp_ms:
                causal_violations += 1
                raise AlignmentError(
                    f"Lookahead violation: book timestamp {current_book.timestamp_ms} > "
                    f"trade timestamp {trade.exchange_timestamp_ms}"
                )

            age = trade.exchange_timestamp_ms - current_book.timestamp_ms
            book_ages.append(age)

            if age > self.max_stale_book_ms:
                stale_count += 1

            # Effective spread relative to contemporaneous midpoint
            mid = current_book.midpoint
            eff_spread_bps = (abs(trade.price - mid) / mid * 10000.0) if mid > 0 else 0.0

            record = AlignedTradeRecord(
                trade=trade,
                preceding_book=current_book,
                book_age_ms=age,
                effective_spread_bps=eff_spread_bps,
                is_causally_valid=True,
            )
            aligned_records.append(record)

        report = AlignmentReport(
            total_trades=len(trades),
            aligned_trades=len(aligned_records),
            unmatched_trades=unmatched_count,
            stale_book_trades=stale_count,
            max_book_age_ms=max(book_ages) if book_ages else 0,
            median_book_age_ms=float(np.median(book_ages)) if book_ages else 0.0,
            p95_book_age_ms=float(np.percentile(book_ages, 95)) if book_ages else 0.0,
            causal_violations=causal_violations,
            is_valid=(causal_violations == 0 and unmatched_count == 0),
        )

        return aligned_records, report
