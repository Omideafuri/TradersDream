"""Automated tests for OrderBookReconstructor atomicity and transactional integrity.

Verifies:
1. Rollback after invalid middle delta (exact scenario: initial bid 100@1, ask 101@1; packet 100.5@2, -1.0@1 -> 100.5 does not remain, zero mutation).
2. Rollback after crossed-book condition (early delta valid, later delta crosses book -> zero mutation).
3. Rollback after negative quantity delta -> zero mutation.
4. Rollback after sequence failure (gap or invalid bounds) -> zero mutation.
5. Rollback after timestamp regression -> zero mutation.
6. Successful multi-level atomic packet commits all levels and sequence state once.
7. Valid packet with level deletions (quantity = 0.0) commits correctly.
8. Single delta atomicity (apply_delta) produces zero state mutation upon failure.
9. State equivalence: complete state before and after failing packet is identical.
"""

import pytest
from typing import Dict

from phase10b.models import (
    BookSide,
    L2Delta,
    L2DeltaPacket,
    L2Snapshot,
)
from phase10b.reconstructor import (
    OrderBookReconstructor,
    OrderBookReconstructionError,
)


def create_reference_reconstructor(
    bids=[(100.0, 1.0)],
    asks=[(101.0, 1.0)],
    sequence_id: int = 100,
    timestamp_ms: int = 1000,
) -> OrderBookReconstructor:
    """Creates a reconstructor initialized with a known reference snapshot."""
    recon = OrderBookReconstructor(symbol="BTCUSDT", exchange="BINANCE_US", strict_mode=True)
    snapshot = L2Snapshot(
        symbol="BTCUSDT",
        exchange="BINANCE_US",
        exchange_timestamp_ms=timestamp_ms,
        sequence_id=sequence_id,
        bids=bids,
        asks=asks,
    )
    recon.load_snapshot(snapshot)
    return recon


def record_reconstructor_state(recon: OrderBookReconstructor) -> Dict:
    """Captures an exact deep copy of all internal state fields for strict immutability checks."""
    return {
        "bids": dict(recon._bids),
        "asks": dict(recon._asks),
        "last_sequence_id": recon.last_sequence_id,
        "last_timestamp_ms": recon.last_timestamp_ms,
        "gaps_count": len(recon.sequence_gaps),
        "issues_count": len(recon.validation_issues),
    }


def assert_zero_state_mutation(recon: OrderBookReconstructor, initial_state: Dict):
    """Asserts that the reconstructor's current state is byte-for-byte identical to initial state."""
    current_state = record_reconstructor_state(recon)
    assert current_state["bids"] == initial_state["bids"], "Bids ladder was mutated on failed packet!"
    assert current_state["asks"] == initial_state["asks"], "Asks ladder was mutated on failed packet!"
    assert current_state["last_sequence_id"] == initial_state["last_sequence_id"], "Sequence ID was mutated on failed packet!"
    assert current_state["last_timestamp_ms"] == initial_state["last_timestamp_ms"], "Timestamp was mutated on failed packet!"
    assert current_state["gaps_count"] == initial_state["gaps_count"], "Gaps count was mutated on failed packet!"
    assert current_state["issues_count"] == initial_state["issues_count"], "Issues count was mutated on failed packet!"


def test_rollback_after_invalid_middle_delta():
    """Verify exact audit scenario: initial bid 100@1, ask 101@1.
    
    Packet contains:
      delta 1: bid 100.5 @ 2
      delta 2: bid -1.0 @ 1 (invalid price)
    Expected:
      Packet raises OrderBookReconstructionError
      100.5 does NOT remain in book
      Book and sequence state are byte-for-byte identical to initial state.
    """
    recon = create_reference_reconstructor(bids=[(100.0, 1.0)], asks=[(101.0, 1.0)], sequence_id=100)
    initial_state = record_reconstructor_state(recon)

    packet = L2DeltaPacket(
        symbol="BTCUSDT",
        exchange="BINANCE_US",
        exchange_timestamp_ms=1010,
        first_update_id=101,
        final_update_id=102,
        deltas=[
            L2Delta("BTCUSDT", "BINANCE_US", 1010, 101, BookSide.BID, 100.5, 2.0),
            L2Delta("BTCUSDT", "BINANCE_US", 1010, 102, BookSide.BID, -1.0, 1.0),
        ],
    )

    with pytest.raises(OrderBookReconstructionError, match="Non-positive price"):
        recon.apply_delta_packet(packet)

    assert 100.5 not in recon._bids, "Partial mutation leaked into live book!"
    assert_zero_state_mutation(recon, initial_state)


def test_rollback_after_crossed_book_condition():
    """Verify that if an early delta is valid but a later delta creates best_bid >= best_ask,
    complete rollback occurs with zero mutation.
    """
    recon = create_reference_reconstructor(bids=[(100.0, 1.0)], asks=[(101.0, 1.0)], sequence_id=100)
    initial_state = record_reconstructor_state(recon)

    # Delta 1: valid bid at 100.2
    # Delta 2: crossing bid at 101.5 (crosses ask at 101.0)
    packet = L2DeltaPacket(
        symbol="BTCUSDT",
        exchange="BINANCE_US",
        exchange_timestamp_ms=1010,
        first_update_id=101,
        final_update_id=102,
        deltas=[
            L2Delta("BTCUSDT", "BINANCE_US", 1010, 101, BookSide.BID, 100.2, 1.0),
            L2Delta("BTCUSDT", "BINANCE_US", 1010, 102, BookSide.BID, 101.5, 1.0),
        ],
    )

    with pytest.raises(OrderBookReconstructionError, match="Crossed book"):
        recon.apply_delta_packet(packet)

    assert 100.2 not in recon._bids, "Early delta 100.2 was not rolled back after crossed book!"
    assert_zero_state_mutation(recon, initial_state)


def test_rollback_after_negative_quantity():
    """Verify that a packet containing negative quantity raises and rolls back completely."""
    recon = create_reference_reconstructor(bids=[(100.0, 1.0)], asks=[(101.0, 1.0)], sequence_id=100)
    initial_state = record_reconstructor_state(recon)

    packet = L2DeltaPacket(
        symbol="BTCUSDT",
        exchange="BINANCE_US",
        exchange_timestamp_ms=1010,
        first_update_id=101,
        final_update_id=102,
        deltas=[
            L2Delta("BTCUSDT", "BINANCE_US", 1010, 101, BookSide.BID, 100.2, 1.0),
            L2Delta("BTCUSDT", "BINANCE_US", 1010, 102, BookSide.ASK, 102.0, -0.5),
        ],
    )

    with pytest.raises(OrderBookReconstructionError, match="Negative quantity"):
        recon.apply_delta_packet(packet)

    assert_zero_state_mutation(recon, initial_state)


def test_rollback_after_sequence_gap():
    """Verify that a sequence discontinuity raises and leaves state unchanged."""
    recon = create_reference_reconstructor(bids=[(100.0, 1.0)], asks=[(101.0, 1.0)], sequence_id=100)
    initial_state = record_reconstructor_state(recon)

    # Expected sequence is 101; packet arrives with first_update_id = 105
    packet = L2DeltaPacket(
        symbol="BTCUSDT",
        exchange="BINANCE_US",
        exchange_timestamp_ms=1010,
        first_update_id=105,
        final_update_id=108,
        deltas=[
            L2Delta("BTCUSDT", "BINANCE_US", 1010, 105, BookSide.BID, 100.2, 1.0),
        ],
    )

    with pytest.raises(OrderBookReconstructionError, match="Sequence gap detected"):
        recon.apply_delta_packet(packet)

    assert_zero_state_mutation(recon, initial_state)


def test_rollback_after_timestamp_regression():
    """Verify that an out-of-order timestamp raises and leaves state unchanged."""
    recon = create_reference_reconstructor(bids=[(100.0, 1.0)], asks=[(101.0, 1.0)], timestamp_ms=1000)
    initial_state = record_reconstructor_state(recon)

    packet = L2DeltaPacket(
        symbol="BTCUSDT",
        exchange="BINANCE_US",
        exchange_timestamp_ms=995,  # Regression: 995 < 1000
        first_update_id=101,
        final_update_id=102,
        deltas=[
            L2Delta("BTCUSDT", "BINANCE_US", 995, 101, BookSide.BID, 100.2, 1.0),
        ],
    )

    with pytest.raises(OrderBookReconstructionError, match="Out-of-order timestamp"):
        recon.apply_delta_packet(packet)

    assert_zero_state_mutation(recon, initial_state)


def test_successful_multi_level_atomic_packet():
    """Verify that a completely valid multi-level packet commits all updates atomically."""
    recon = create_reference_reconstructor(bids=[(100.0, 1.0)], asks=[(101.0, 1.0)], sequence_id=100, timestamp_ms=1000)

    packet = L2DeltaPacket(
        symbol="BTCUSDT",
        exchange="BINANCE_US",
        exchange_timestamp_ms=1020,
        first_update_id=101,
        final_update_id=104,
        deltas=[
            L2Delta("BTCUSDT", "BINANCE_US", 1020, 101, BookSide.BID, 100.2, 1.5),
            L2Delta("BTCUSDT", "BINANCE_US", 1020, 102, BookSide.BID, 100.4, 2.0),
            L2Delta("BTCUSDT", "BINANCE_US", 1020, 103, BookSide.ASK, 100.8, 0.8),
            L2Delta("BTCUSDT", "BINANCE_US", 1020, 104, BookSide.ASK, 100.9, 1.2),
        ],
    )

    state = recon.apply_delta_packet(packet)

    assert state.best_bid == 100.4
    assert state.best_ask == 100.8
    assert recon.last_sequence_id == 104
    assert recon.last_timestamp_ms == 1020
    assert recon._bids[100.2] == 1.5
    assert recon._bids[100.4] == 2.0
    assert recon._asks[100.8] == 0.8
    assert recon._asks[100.9] == 1.2


def test_valid_packet_with_level_deletions():
    """Verify that level deletions (quantity = 0.0) commit cleanly in atomic packet."""
    recon = create_reference_reconstructor(
        bids=[(100.0, 1.0), (99.0, 2.0)],
        asks=[(101.0, 1.0), (102.0, 2.0)],
        sequence_id=100,
    )

    packet = L2DeltaPacket(
        symbol="BTCUSDT",
        exchange="BINANCE_US",
        exchange_timestamp_ms=1030,
        first_update_id=101,
        final_update_id=102,
        deltas=[
            L2Delta("BTCUSDT", "BINANCE_US", 1030, 101, BookSide.BID, 100.0, 0.0),
            L2Delta("BTCUSDT", "BINANCE_US", 1030, 102, BookSide.ASK, 101.0, 0.0),
        ],
    )

    state = recon.apply_delta_packet(packet)

    assert 100.0 not in recon._bids
    assert 101.0 not in recon._asks
    assert state.best_bid == 99.0
    assert state.best_ask == 102.0
    assert recon.last_sequence_id == 102


def test_single_delta_atomicity():
    """Verify that apply_delta produces zero state mutation if delta causes crossed book."""
    recon = create_reference_reconstructor(bids=[(100.0, 1.0)], asks=[(101.0, 1.0)], sequence_id=100)
    initial_state = record_reconstructor_state(recon)

    crossing_delta = L2Delta("BTCUSDT", "BINANCE_US", 1010, 101, BookSide.BID, 101.5, 1.0)

    with pytest.raises(OrderBookReconstructionError, match="Crossed book"):
        recon.apply_delta(crossing_delta)

    assert_zero_state_mutation(recon, initial_state)


def test_state_equivalence_after_multiple_adversarial_failures():
    """Verify state equivalence before and after multiple failing attempts."""
    recon = create_reference_reconstructor(bids=[(50000.0, 1.0)], asks=[(50010.0, 1.0)], sequence_id=50)
    initial_state = record_reconstructor_state(recon)

    # Attempt 1: wrong symbol
    with pytest.raises(OrderBookReconstructionError):
        recon.apply_delta_packet(L2DeltaPacket("ETHUSDT", "BINANCE_US", 1000, 51, 52, []))

    # Attempt 2: negative price
    with pytest.raises(OrderBookReconstructionError):
        recon.apply_delta_packet(L2DeltaPacket("BTCUSDT", "BINANCE_US", 1000, 51, 52, [
            L2Delta("BTCUSDT", "BINANCE_US", 1000, 51, BookSide.BID, -1.0, 1.0)
        ]))

    # Attempt 3: negative bounds
    with pytest.raises(OrderBookReconstructionError):
        recon.apply_delta_packet(L2DeltaPacket("BTCUSDT", "BINANCE_US", 1000, 55, 52, []))

    assert_zero_state_mutation(recon, initial_state)
