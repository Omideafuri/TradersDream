"""Deterministic Order-Book Reconstructor from Snapshot + Incremental Deltas."""

from typing import Dict, List, Optional, Tuple

from phase10b.models import (
    BookSide,
    L2Delta,
    L2DeltaPacket,
    L2Snapshot,
    ReconstructedBookState,
    SequenceGapRecord,
    GapSeverity,
    ValidationIssue,
)


class OrderBookReconstructionError(Exception):
    """Raised when an unrecoverable sequence or invariant error occurs during reconstruction."""
    pass


class OrderBookReconstructor:
    """Deterministic Level-2 (Price-by-Price) Order Book Reconstructor.
    
    Maintains an exact price-time priority ladder by taking an initial full snapshot
    and deterministically applying strictly sequenced incremental deltas.
    """

    def __init__(self, symbol: str, exchange: str, strict_mode: bool = True):
        self.symbol = symbol
        self.exchange = exchange
        self.strict_mode = strict_mode
        
        # Bids: sorted descending by price (highest price first)
        # Asks: sorted ascending by price (lowest price first)
        # We store price -> quantity
        self._bids: Dict[float, float] = {}
        self._asks: Dict[float, float] = {}
        
        self.last_sequence_id: Optional[int] = None
        self.last_timestamp_ms: Optional[int] = None
        self.is_initialized: bool = False
        
        self.sequence_gaps: List[SequenceGapRecord] = []
        self.validation_issues: List[ValidationIssue] = []

    def load_snapshot(self, snapshot: L2Snapshot) -> ReconstructedBookState:
        """Initializes or resets the order book ladder from a full depth snapshot."""
        if snapshot.symbol != self.symbol:
            raise OrderBookReconstructionError(
                f"Snapshot symbol '{snapshot.symbol}' does not match reconstructor symbol '{self.symbol}'"
            )
            
        self._bids.clear()
        self._asks.clear()

        # Validate prices and quantities in snapshot
        for p, q in snapshot.bids:
            if p <= 0 or q <= 0:
                raise OrderBookReconstructionError(f"Invalid bid in snapshot: price={p}, size={q}")
            self._bids[p] = q

        for p, q in snapshot.asks:
            if p <= 0 or q <= 0:
                raise OrderBookReconstructionError(f"Invalid ask in snapshot: price={p}, size={q}")
            self._asks[p] = q

        self.last_sequence_id = snapshot.sequence_id
        self.last_timestamp_ms = snapshot.exchange_timestamp_ms
        self.is_initialized = True

        state = self.get_current_state()
        if state.is_crossed and self.strict_mode:
            raise OrderBookReconstructionError(
                f"Crossed book in initial snapshot: best_bid={state.best_bid}, best_ask={state.best_ask}"
            )
        return state

    def apply_delta(self, delta: L2Delta) -> ReconstructedBookState:
        """Applies a single incremental L2 delta to the book state with strict sequence checking."""
        if not self.is_initialized:
            raise OrderBookReconstructionError("Cannot apply delta before order book is initialized with snapshot.")

        if delta.symbol != self.symbol:
            raise OrderBookReconstructionError(
                f"Delta symbol '{delta.symbol}' does not match reconstructor symbol '{self.symbol}'"
            )

        # 1. Sequence Validation
        expected_seq = (self.last_sequence_id + 1) if self.last_sequence_id is not None else delta.sequence_id
        if self.last_sequence_id is not None and delta.sequence_id == self.last_sequence_id:
            # Intra-packet price level update: shares sequence ID with current event packet
            pass
        elif delta.sequence_id != expected_seq:
            gap_size = delta.sequence_id - expected_seq
            gap_rec = SequenceGapRecord(
                symbol=self.symbol,
                exchange=self.exchange,
                expected_sequence=expected_seq,
                observed_sequence=delta.sequence_id,
                gap_size=gap_size,
                timestamp_ms=delta.exchange_timestamp_ms,
                severity=GapSeverity.FATAL if gap_size > 0 else GapSeverity.WARNING,
                notes=f"Sequence discontinuity: expected {expected_seq}, got {delta.sequence_id}",
            )
            self.sequence_gaps.append(gap_rec)
            if self.strict_mode:
                raise OrderBookReconstructionError(
                    f"Sequence gap detected: expected {expected_seq}, observed {delta.sequence_id} (gap: {gap_size})"
                )

        # 2. Timestamp Validation (Monotonicity)
        if self.last_timestamp_ms is not None and delta.exchange_timestamp_ms < self.last_timestamp_ms:
            issue = ValidationIssue(
                check_name="timestamp_monotonicity",
                symbol=self.symbol,
                timestamp_ms=delta.exchange_timestamp_ms,
                description=f"Out-of-order timestamp: current {delta.exchange_timestamp_ms} < last {self.last_timestamp_ms}",
                severity=GapSeverity.CRITICAL,
            )
            self.validation_issues.append(issue)
            if self.strict_mode:
                raise OrderBookReconstructionError(issue.description)

        # 3. Price and Quantity Invariants
        if delta.price <= 0:
            raise OrderBookReconstructionError(f"Non-positive price in delta: {delta.price}")
        if delta.quantity < 0:
            raise OrderBookReconstructionError(f"Negative quantity in delta: {delta.quantity}")

        # 4. Apply Update
        ladder = self._bids if delta.side == BookSide.BID else self._asks
        if delta.quantity == 0.0:
            # Exchange deletion semantics: quantity 0 removes the level
            ladder.pop(delta.price, None)
        else:
            # Add or modify quantity at price
            ladder[delta.price] = delta.quantity

        self.last_sequence_id = delta.sequence_id
        self.last_timestamp_ms = delta.exchange_timestamp_ms

        state = self.get_current_state()
        if state.is_crossed:
            issue = ValidationIssue(
                check_name="crossed_book",
                symbol=self.symbol,
                timestamp_ms=delta.exchange_timestamp_ms,
                description=f"Crossed book: best_bid {state.best_bid} >= best_ask {state.best_ask}",
                severity=GapSeverity.CRITICAL,
            )
            self.validation_issues.append(issue)
            if self.strict_mode:
                raise OrderBookReconstructionError(issue.description)

        return state

    def get_current_state(self, top_n: int = 5) -> ReconstructedBookState:
        """Returns the sorted snapshot representation of the current book state."""
        sorted_bids = sorted(self._bids.items(), key=lambda x: x[0], reverse=True)
        sorted_asks = sorted(self._asks.items(), key=lambda x: x[0])

        best_bid = sorted_bids[0][0] if sorted_bids else 0.0
        best_ask = sorted_asks[0][0] if sorted_asks else float("inf")

        is_crossed = bool(sorted_bids and sorted_asks and best_bid >= best_ask)
        spread = (best_ask - best_bid) if (sorted_bids and sorted_asks and not is_crossed) else 0.0
        midpoint = (best_bid + best_ask) / 2.0 if (sorted_bids and sorted_asks) else 0.0
        spread_bps = (spread / midpoint * 10000.0) if midpoint > 0 else 0.0

        bid_depth_top5 = sum(q for _, q in sorted_bids[:top_n])
        ask_depth_top5 = sum(q for _, q in sorted_asks[:top_n])

        return ReconstructedBookState(
            symbol=self.symbol,
            exchange=self.exchange,
            timestamp_ms=self.last_timestamp_ms or 0,
            sequence_id=self.last_sequence_id or 0,
            best_bid=best_bid,
            best_ask=best_ask if best_ask != float("inf") else 0.0,
            spread=spread,
            spread_bps=spread_bps,
            midpoint=midpoint,
            bid_depth_top5=bid_depth_top5,
            ask_depth_top5=ask_depth_top5,
            bid_levels=sorted_bids[:top_n],
            ask_levels=sorted_asks[:top_n],
            is_crossed=is_crossed,
        )

    def apply_delta_packet(self, packet: L2DeltaPacket) -> ReconstructedBookState:
        """Applies an atomic packet of deltas spanning [first_update_id, final_update_id]."""
        if not self.is_initialized:
            raise OrderBookReconstructionError("Cannot apply delta packet before order book is initialized.")

        if packet.symbol != self.symbol:
            raise OrderBookReconstructionError(
                f"Packet symbol '{packet.symbol}' does not match reconstructor symbol '{self.symbol}'"
            )

        # 1. Packet Sequence Validation
        expected_seq = (self.last_sequence_id + 1) if self.last_sequence_id is not None else packet.first_update_id
        if packet.first_update_id > expected_seq:
            gap_size = packet.first_update_id - expected_seq
            gap_rec = SequenceGapRecord(
                symbol=self.symbol,
                exchange=self.exchange,
                expected_sequence=expected_seq,
                observed_sequence=packet.first_update_id,
                gap_size=gap_size,
                timestamp_ms=packet.exchange_timestamp_ms,
                severity=GapSeverity.FATAL,
                notes=f"Packet sequence gap: expected {expected_seq}, got {packet.first_update_id}",
            )
            self.sequence_gaps.append(gap_rec)
            if self.strict_mode:
                raise OrderBookReconstructionError(
                    f"Sequence gap detected: expected {expected_seq}, observed {packet.first_update_id} (gap: {gap_size})"
                )

        # 2. Timestamp Validation (Monotonicity)
        if self.last_timestamp_ms is not None and packet.exchange_timestamp_ms < self.last_timestamp_ms:
            issue = ValidationIssue(
                check_name="timestamp_monotonicity",
                symbol=self.symbol,
                timestamp_ms=packet.exchange_timestamp_ms,
                description=f"Out-of-order timestamp: current {packet.exchange_timestamp_ms} < last {self.last_timestamp_ms}",
                severity=GapSeverity.CRITICAL,
            )
            self.validation_issues.append(issue)
            if self.strict_mode:
                raise OrderBookReconstructionError(issue.description)

        # 3. Apply all deltas in the packet
        for delta in packet.deltas:
            if delta.price <= 0:
                raise OrderBookReconstructionError(f"Non-positive price in delta: {delta.price}")
            if delta.quantity < 0:
                raise OrderBookReconstructionError(f"Negative quantity in delta: {delta.quantity}")

            ladder = self._bids if delta.side == BookSide.BID else self._asks
            if delta.quantity == 0.0:
                ladder.pop(delta.price, None)
            else:
                ladder[delta.price] = delta.quantity

        self.last_sequence_id = packet.final_update_id
        self.last_timestamp_ms = packet.exchange_timestamp_ms

        state = self.get_current_state()
        if state.is_crossed:
            issue = ValidationIssue(
                check_name="crossed_book",
                symbol=self.symbol,
                timestamp_ms=packet.exchange_timestamp_ms,
                description=f"Crossed book: best_bid {state.best_bid} >= best_ask {state.best_ask}",
                severity=GapSeverity.CRITICAL,
            )
            self.validation_issues.append(issue)
            if self.strict_mode:
                raise OrderBookReconstructionError(issue.description)

        return state
