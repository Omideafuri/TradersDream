"""Dynamic Economic Gate module for Phase 9.

Models realistic round-trip market execution friction:
1. Exchange fees (taker / maker).
2. Bid-ask spread.
3. Volatility-scaled slippage.
4. Order-size market impact.
5. Latency penalty.
6. Adverse selection penalty.
7. Conservative safety margin.

Distinguishes between raw statistical predictability (PREDICTIVE_ONLY)
and genuine economic tradeability (ECONOMICALLY_VIABLE).
"""

from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional


@dataclass
class ExecutionParameters:
    taker_fee_bps: float = 10.0          # 0.10% per fill (20.0 bps round-trip)
    maker_fee_bps: float = 2.0           # 0.02% per fill
    half_spread_bps: float = 2.5         # Half-spread cost (5.0 bps full spread round-trip)
    slippage_bps: float = 3.0            # Average non-linear execution slippage per fill
    market_impact_bps: float = 2.0       # Square-root liquidity impact per fill
    latency_penalty_bps: float = 1.0     # Expected price drift during network/queue latency
    adverse_selection_bps: float = 1.5   # Toxicity penalty on aggressive fills
    safety_margin_bps: float = 10.0      # Required buffer above break-even
    is_maker: bool = False               # False for taker orders, True for passive maker fills

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EconomicGateEvaluation:
    gross_edge_bps: float
    total_friction_bps: float
    net_edge_bps: float
    required_hurdle_bps: float
    economic_margin_bps: float
    is_economically_viable: bool
    classification: str  # ECONOMICALLY_VIABLE, PREDICTIVE_ONLY, or NEGATIVE_GROSS
    breakdown: Dict[str, float]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class EconomicGate:
    """Evaluates whether an observed gross return edge survives realistic market friction."""

    def __init__(self, params: Optional[ExecutionParameters] = None):
        self.params = params or ExecutionParameters()

    def compute_round_trip_cost(self, custom_params: Optional[ExecutionParameters] = None) -> Dict[str, float]:
        """Calculates total two-legged round-trip execution friction."""
        p = custom_params or self.params
        base_fee = (p.maker_fee_bps if p.is_maker else p.taker_fee_bps) * 2.0
        spread_cost = p.half_spread_bps * 2.0
        slippage_cost = p.slippage_bps * 2.0
        impact_cost = p.market_impact_bps * 2.0
        latency_cost = p.latency_penalty_bps * 2.0
        adverse_cost = p.adverse_selection_bps * 2.0

        total_friction = (
            base_fee + spread_cost + slippage_cost +
            impact_cost + latency_cost + adverse_cost
        )

        return {
            "fees_roundtrip": base_fee,
            "spread_roundtrip": spread_cost,
            "slippage_roundtrip": slippage_cost,
            "market_impact_roundtrip": impact_cost,
            "latency_roundtrip": latency_cost,
            "adverse_selection_roundtrip": adverse_cost,
            "total_friction_bps": total_friction,
            "safety_margin_bps": p.safety_margin_bps,
            "required_hurdle_bps": total_friction + p.safety_margin_bps,
        }

    def evaluate(
        self,
        gross_edge_bps: float,
        custom_params: Optional[ExecutionParameters] = None,
    ) -> EconomicGateEvaluation:
        """Evaluates gross edge against the total economic hurdle."""
        p = custom_params or self.params
        costs = self.compute_round_trip_cost(p)
        total_friction = costs["total_friction_bps"]
        safety_margin = p.safety_margin_bps
        required_hurdle = total_friction + safety_margin

        net_edge = gross_edge_bps - total_friction
        economic_margin = gross_edge_bps - required_hurdle
        is_viable = economic_margin > 0.0

        if gross_edge_bps <= 0.0:
            classification = "NEGATIVE_GROSS"
        elif not is_viable and net_edge <= 0.0:
            classification = "FRICTION_DOMINATED"
        elif not is_viable:
            classification = "PREDICTIVE_ONLY"
        else:
            classification = "ECONOMICALLY_VIABLE"

        return EconomicGateEvaluation(
            gross_edge_bps=gross_edge_bps,
            total_friction_bps=total_friction,
            net_edge_bps=net_edge,
            required_hurdle_bps=required_hurdle,
            economic_margin_bps=economic_margin,
            is_economically_viable=is_viable,
            classification=classification,
            breakdown=costs,
        )

    @classmethod
    def get_exchange_preset(cls, exchange_name: str) -> "EconomicGate":
        """Factory providing exchange-specific execution parameters."""
        ex = exchange_name.upper()
        if "COINBASE" in ex:
            # Coinbase Advanced Trade tier: ~40-60 bps taker, 20-40 bps maker
            return cls(ExecutionParameters(
                taker_fee_bps=25.0, maker_fee_bps=10.0, half_spread_bps=2.0,
                slippage_bps=2.5, market_impact_bps=2.0, latency_penalty_bps=1.0,
                adverse_selection_bps=1.5, safety_margin_bps=10.0
            ))
        elif "KRAKEN" in ex:
            # Kraken Spot tier: ~26 bps taker, 16 bps maker
            return cls(ExecutionParameters(
                taker_fee_bps=20.0, maker_fee_bps=12.0, half_spread_bps=3.0,
                slippage_bps=3.0, market_impact_bps=2.5, latency_penalty_bps=1.5,
                adverse_selection_bps=1.5, safety_margin_bps=10.0
            ))
        elif "OKX" in ex:
            # OKX VIP0 tier: ~8-10 bps taker, 2 bps maker
            return cls(ExecutionParameters(
                taker_fee_bps=10.0, maker_fee_bps=2.0, half_spread_bps=2.5,
                slippage_bps=2.5, market_impact_bps=2.0, latency_penalty_bps=1.0,
                adverse_selection_bps=1.0, safety_margin_bps=10.0
            ))
        elif "BINANCE_US" in ex:
            # Binance US tier: ~10 bps taker, 0 bps maker on zero-fee pairs
            return cls(ExecutionParameters(
                taker_fee_bps=10.0, maker_fee_bps=0.0, half_spread_bps=3.5,
                slippage_bps=3.5, market_impact_bps=3.0, latency_penalty_bps=1.5,
                adverse_selection_bps=2.0, safety_margin_bps=10.0
            ))
        else:
            return cls()
