"""Dual Economic Gate Module for Phase 9D.

Models both:
1. Static 40.0 bps benchmark hurdle
2. Dynamic microstructure-aware execution friction:
   fee + observed spread + volatility-scaled slippage + market impact + latency + adverse selection + safety margin
"""

from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional
import numpy as np


@dataclass
class DynamicCostBreakdown:
    taker_fee_roundtrip_bps: float
    observed_spread_bps: float
    slippage_bps: float
    market_impact_bps: float
    latency_penalty_bps: float
    adverse_selection_bps: float
    safety_margin_bps: float
    total_dynamic_hurdle_bps: float
    static_hurdle_bps: float = 40.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DualGateResult:
    gross_edge_bps: float
    static_hurdle_bps: float
    dynamic_hurdle_bps: float
    net_edge_static_bps: float
    net_edge_dynamic_bps: float
    survives_static_gate: bool
    survives_dynamic_gate: bool
    classification: str
    breakdown: DynamicCostBreakdown

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gross_edge_bps": self.gross_edge_bps,
            "static_hurdle_bps": self.static_hurdle_bps,
            "dynamic_hurdle_bps": self.dynamic_hurdle_bps,
            "net_edge_static_bps": self.net_edge_static_bps,
            "net_edge_dynamic_bps": self.net_edge_dynamic_bps,
            "survives_static_gate": self.survives_static_gate,
            "survives_dynamic_gate": self.survives_dynamic_gate,
            "classification": self.classification,
            "breakdown": self.breakdown.to_dict(),
        }


class DualEconomicGate:
    """Evaluates strategy gross expectancy against both static and dynamic microstructure friction."""

    def __init__(
        self,
        base_taker_fee_bps: float = 10.0,    # 20 bps roundtrip
        safety_margin_bps: float = 10.0,
    ):
        self.base_taker_fee_bps = base_taker_fee_bps
        self.safety_margin_bps = safety_margin_bps

    def compute_dynamic_cost(
        self,
        spread_bps: float = 5.0,
        realized_vol_daily: float = 0.50,
        depth_ratio: float = 1.0,
    ) -> DynamicCostBreakdown:
        """Calculates point-in-time dynamic execution friction."""
        fee_rt = self.base_taker_fee_bps * 2.0
        obs_spread = max(1.0, float(spread_bps))

        # Slippage scales with realized volatility
        slippage = float(np.clip(3.0 * (realized_vol_daily / 0.50), 1.5, 10.0))

        # Impact scales with imbalance/depth asymmetry
        impact = float(np.clip(2.0 * max(1.0, depth_ratio if depth_ratio > 1 else 1.0 / (depth_ratio + 1e-9)), 1.0, 8.0))

        latency = 1.5
        adverse_selection = 2.0
        safety = self.safety_margin_bps

        total_dynamic = fee_rt + obs_spread + slippage + impact + latency + adverse_selection + safety

        return DynamicCostBreakdown(
            taker_fee_roundtrip_bps=fee_rt,
            observed_spread_bps=obs_spread,
            slippage_bps=slippage,
            market_impact_bps=impact,
            latency_penalty_bps=latency,
            adverse_selection_bps=adverse_selection,
            safety_margin_bps=safety,
            total_dynamic_hurdle_bps=total_dynamic,
            static_hurdle_bps=40.0,
        )

    def evaluate(
        self,
        gross_edge_bps: float,
        spread_bps: float = 5.0,
        realized_vol_daily: float = 0.50,
        depth_ratio: float = 1.0,
    ) -> DualGateResult:
        """Evaluates whether gross edge clears static and dynamic hurdles."""
        cost = self.compute_dynamic_cost(spread_bps, realized_vol_daily, depth_ratio)
        static_hurdle = cost.static_hurdle_bps
        dynamic_hurdle = cost.total_dynamic_hurdle_bps

        net_static = gross_edge_bps - static_hurdle
        net_dynamic = gross_edge_bps - dynamic_hurdle

        survives_static = bool(net_static > 0.0)
        survives_dynamic = bool(net_dynamic > 0.0)

        if gross_edge_bps <= 0.0:
            classification = "NEGATIVE_GROSS"
        elif not survives_static and not survives_dynamic:
            classification = "FRICTION_DOMINATED"
        elif survives_static and not survives_dynamic:
            classification = "MICROSTRUCTURE_FRICTION_DOMINATED"
        else:
            classification = "ECONOMICALLY_VIABLE"

        return DualGateResult(
            gross_edge_bps=gross_edge_bps,
            static_hurdle_bps=static_hurdle,
            dynamic_hurdle_bps=dynamic_hurdle,
            net_edge_static_bps=net_static,
            net_edge_dynamic_bps=net_dynamic,
            survives_static_gate=survives_static,
            survives_dynamic_gate=survives_dynamic,
            classification=classification,
            breakdown=cost,
        )
