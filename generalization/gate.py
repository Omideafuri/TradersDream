"""Economic Signal Friction Gate and Cost-Adjusted Edge Engine.

Strictly enforces the Phase 5 economic hurdle across all Phase 6 experiments:
- Round-trip Taker Fee: 0.20% (2 x 0.10%)
- Adverse Slippage: 0.10% (2 x 0.05%)
- Round-trip Transaction Friction: 0.30% (30 bps)
- Safety Margin: 0.10% (10 bps)
- Total Economic Hurdle: 0.40% (40 bps)

Evaluates:
  Gross Edge = (2 * P(win) - 1) * Expected Magnitude
  Net Edge = Gross Edge - 40 bps
- If Gross Edge > 0 but Net Edge <= 0: Classified as PREDICTIVE_BUT_NOT_ECONOMIC.
- If Net Edge > 0 and statistically valid: Classified as SUPPORTED.
- If Gross Edge <= 0: Classified as NOT_SUPPORTED.
"""

from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional

from reconstruction.gate import SignalFrictionGate, SignalGateVerdict


@dataclass
class EconomicEdgeEvaluation:
    symbol: str
    action: str
    win_rate_pct: float
    expected_magnitude_bps: float
    gross_edge_bps: float
    round_trip_friction_bps: float
    safety_margin_bps: float
    total_hurdle_bps: float
    net_edge_bps: float
    gate_passed: bool
    economic_status: str  # SUPPORTED, PREDICTIVE_BUT_NOT_ECONOMIC, NOT_SUPPORTED

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class EconomicSignalGate:
    """Evaluates individual signals and aggregate strategy pools against economic hurdles."""

    def __init__(
        self,
        round_trip_fee_bps: float = 20.0,
        round_trip_slippage_bps: float = 10.0,
        safety_margin_bps: float = 10.0,
    ):
        self.friction_bps = round_trip_fee_bps + round_trip_slippage_bps
        self.safety_margin_bps = safety_margin_bps
        self.hurdle_bps = self.friction_bps + self.safety_margin_bps
        self.inner_gate = SignalFrictionGate(
            round_trip_fee_bps=round_trip_fee_bps,
            round_trip_slippage_bps=round_trip_slippage_bps,
            safety_margin_bps=safety_margin_bps,
        )

    def evaluate_aggregate_edge(
        self,
        symbol: str,
        action: str,
        win_rate_pct: float,
        expected_magnitude_bps: float,
    ) -> EconomicEdgeEvaluation:
        """Evaluates an aggregate pool of decisions against economic friction."""
        p_win = win_rate_pct / 100.0
        # Expected edge = (2 * P(win) - 1) * Expected Magnitude
        gross_edge = (2.0 * p_win - 1.0) * expected_magnitude_bps
        net_edge = gross_edge - self.hurdle_bps

        if gross_edge > 0.0 and net_edge <= 0.0:
            status = "PREDICTIVE_BUT_NOT_ECONOMIC"
            passed = False
        elif net_edge > 0.0:
            status = "SUPPORTED"
            passed = True
        else:
            status = "NOT_SUPPORTED"
            passed = False

        return EconomicEdgeEvaluation(
            symbol=symbol,
            action=action,
            win_rate_pct=round(win_rate_pct, 2),
            expected_magnitude_bps=round(expected_magnitude_bps, 1),
            gross_edge_bps=round(gross_edge, 1),
            round_trip_friction_bps=round(self.friction_bps, 1),
            safety_margin_bps=round(self.safety_margin_bps, 1),
            total_hurdle_bps=round(self.hurdle_bps, 1),
            net_edge_bps=round(net_edge, 1),
            gate_passed=passed,
            economic_status=status,
        )
