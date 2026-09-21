"""Signal Gate and Friction Barrier Engine.

Enforces an economic gate between the decision generator and paper-trading execution:
- Hurdle Rule:
  Expected Edge > Round-Trip Friction (0.30%) + Safety Margin (0.10%) = 0.40% (40 bps).
- Signals failing this test are unconditionally rejected or mapped to NO_EDGE.
- Tracks rejection metrics and why signals fail the gate.
"""

from dataclasses import dataclass
from typing import Dict, Any, Tuple


@dataclass
class SignalGateVerdict:
    passed: bool
    filtered_action: str  # Original action if passed, else NO_EDGE
    expected_edge_bps: float
    hurdle_bps: float
    rejection_reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "filtered_action": self.filtered_action,
            "expected_edge_bps": round(self.expected_edge_bps, 1),
            "hurdle_bps": round(self.hurdle_bps, 1),
            "rejection_reason": self.rejection_reason,
        }


class SignalFrictionGate:
    """Evaluates whether candidate trading signals possess sufficient edge to overcome friction."""

    def __init__(
        self,
        round_trip_fee_bps: float = 20.0,  # 0.10% * 2
        round_trip_slippage_bps: float = 10.0,  # 0.05% * 2
        safety_margin_bps: float = 10.0,  # 0.10%
        max_uncertainty_threshold: float = 0.50,
    ):
        self.friction_bps = round_trip_fee_bps + round_trip_slippage_bps
        self.safety_margin_bps = safety_margin_bps
        self.hurdle_bps = self.friction_bps + self.safety_margin_bps
        self.max_uncertainty_threshold = max_uncertainty_threshold

    def evaluate(
        self,
        raw_action: str,
        prob_win: float,
        expected_move_bps: float,
        uncertainty_score: float,
        market_regime: str = "TRANSITION",
    ) -> SignalGateVerdict:
        """Evaluates raw signal against economic and uncertainty hurdles."""
        if raw_action in ["HOLD", "NO_EDGE"]:
            return SignalGateVerdict(
                passed=False,
                filtered_action=raw_action,
                expected_edge_bps=0.0,
                hurdle_bps=self.hurdle_bps,
                rejection_reason="PASSIVE_ACTION",
            )

        # 1. Epistemic uncertainty hurdle
        if uncertainty_score > self.max_uncertainty_threshold:
            return SignalGateVerdict(
                passed=False,
                filtered_action="NO_EDGE",
                expected_edge_bps=0.0,
                hurdle_bps=self.hurdle_bps,
                rejection_reason=f"EXCESSIVE_UNCERTAINTY ({uncertainty_score:.2f} > {self.max_uncertainty_threshold:.2f})",
            )

        # 2. Regime check: avoid trending signals in pure chop
        if market_regime == "RANGE_BOUND" and expected_move_bps < 30.0:
            return SignalGateVerdict(
                passed=False,
                filtered_action="NO_EDGE",
                expected_edge_bps=expected_move_bps * 0.5,
                hurdle_bps=self.hurdle_bps,
                rejection_reason="CHOPPY_REGIME_WITH_LOW_AMPLITUDE",
            )

        # 3. Expected edge calculation:
        # Edge = Prob(win) * E[Gain] - (1 - Prob(win)) * E[Loss]
        # Assuming symmetric stop/target = expected_move_bps
        edge_bps = (2.0 * prob_win - 1.0) * expected_move_bps

        if edge_bps < self.hurdle_bps:
            return SignalGateVerdict(
                passed=False,
                filtered_action="NO_EDGE",
                expected_edge_bps=edge_bps,
                hurdle_bps=self.hurdle_bps,
                rejection_reason=f"INSUFFICIENT_EDGE ({edge_bps:.1f} bps < hurdle {self.hurdle_bps:.1f} bps)",
            )

        return SignalGateVerdict(
            passed=True,
            filtered_action=raw_action,
            expected_edge_bps=edge_bps,
            hurdle_bps=self.hurdle_bps,
            rejection_reason="NONE",
        )
