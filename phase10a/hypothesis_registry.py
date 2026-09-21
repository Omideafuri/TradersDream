"""Pre-registered Hypothesis Registry for Phase 10A Passive Execution & Queue Dynamics.

Formally records and freezes hypotheses prior to simulator implementation and evaluation,
enforcing scientific rigor, non-retrospective inquiry, and strict falsifiability.
"""

from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Dict, List, Optional, Any


class Phase10AStatus:
    REGISTERED = "REGISTERED"
    EVALUATING = "EVALUATING"
    SUPPORTED = "SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    INCONCLUSIVE = "INCONCLUSIVE"
    REJECTED = "REJECTED"


@dataclass
class PreRegisteredHypothesis:
    """Dataclass capturing a pre-registered scientific hypothesis in Phase 10A."""
    hypothesis_id: str
    name: str
    rationale: str
    measurable_prediction: str
    metric: str
    statistical_test: str
    economic_gate: str
    rejection_criterion: str
    status: str = Phase10AStatus.REGISTERED
    registered_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    evaluation_notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PreRegisteredHypothesis":
        return cls(**data)


class Phase10AHypothesisRegistry:
    """Registry maintaining formal pre-registered Phase 10A research hypotheses."""

    DEFAULT_HYPOTHESES = [
        PreRegisteredHypothesis(
            hypothesis_id="P10A-H01",
            name="Positive Realized Spread After Maker Fees",
            rationale=(
                "Passive limit orders placed at the inside quote earn the half-spread upon execution and "
                "incur maker fees (or rebates) rather than paying taker fee penalties. If the subsequent "
                "midpoint price movement does not fully erode the half-spread, the realized spread retained "
                "after maker fees will be strictly positive."
            ),
            measurable_prediction=(
                "Mean realized spread at the 1-second and 5-second post-fill markout horizons exceeds the "
                "exchange maker fee schedule (e.g., > 1.0 bps on Binance.US tier 1 maker fees) with p < 0.01."
            ),
            metric="Realized Spread (bps) = Dir * (Mid_t+k - Fill_t) - Fee_maker",
            statistical_test="Stationary block-bootstrap one-sample t-test (H0: mean realized spread <= 0)",
            economic_gate="Mean realized spread > 0.0 bps across all non-stressed validation regimes",
            rejection_criterion=(
                "Mean realized spread <= 0.0 bps at the 5-second markout horizon, or bootstrap p >= 0.05."
            ),
        ),
        PreRegisteredHypothesis(
            hypothesis_id="P10A-H02",
            name="Queue Position Determinism of Realized Profitability",
            rationale=(
                "In price-time priority matching engines, orders joined at the back of the queue (top of queue "
                "depth high) only execute when incoming taker volume is large enough to deplete earlier orders, "
                "which strongly correlates with adverse momentum and toxic flow. Orders executed near the front "
                "of the queue experience significantly lower adverse selection."
            ),
            measurable_prediction=(
                "Fills occurring from the front tercile of estimated queue depth display statistically significant "
                "higher net markout (at least +3.0 bps higher) than fills occurring from the back tercile (p < 0.001)."
            ),
            metric="Queue Position Markout Delta = E[Markout | Queue_front] - E[Markout | Queue_back]",
            statistical_test="Two-sample Mann-Whitney U test and Welch t-test on front vs back queue tercile markouts",
            economic_gate="Markout difference between front and back queue terciles >= 2.0 bps",
            rejection_criterion=(
                "Queue position markout delta < 1.0 bps or failure to reject null at alpha = 0.01."
            ),
        ),
        PreRegisteredHypothesis(
            hypothesis_id="P10A-H03",
            name="Adverse Selection Offsetting Quoted Spread",
            rationale=(
                "Taker orders arriving at the book carry informed flow. Fills on passive limit orders suffer from "
                "immediate price drift in the direction of the aggressive order (adverse selection), eroding a "
                "substantial fraction of the quoted half-spread."
            ),
            measurable_prediction=(
                "The adverse price movement (markout drift) within 5 seconds of execution offsets at least 60% of "
                "the initial half-spread across liquid spot crypto pairs."
            ),
            metric="Adverse Selection Ratio = E[Adverse Price Drift (5s)] / E[Quoted Half-Spread]",
            statistical_test="Block bootstrap confidence interval on the adverse selection ratio (H0: ratio < 0.50)",
            economic_gate="Quantification of adverse selection ratio with lower 95% bootstrap bound > 0.50",
            rejection_criterion=(
                "Mean adverse selection ratio < 0.40 or post-fill drift is indistinguishable from zero (p >= 0.05)."
            ),
        ),
        PreRegisteredHypothesis(
            hypothesis_id="P10A-H04",
            name="Microstructure Conditioning for Superior Fill Economics",
            rationale=(
                "Conditioning passive order placement and cancellation on microstructure signals (order-book imbalance, "
                "recent trade flow aggression, and spread volatility) can selectively avoid toxic adverse selection fills "
                "and concentrate fills in balanced, mean-reverting regimes."
            ),
            measurable_prediction=(
                "Microstructure-conditioned quoting yields a net realized spread improvement of at least +2.5 bps over "
                "an unconditioned static inside quoting baseline on out-of-sample validation data (p < 0.01)."
            ),
            metric="Conditioned Alpha Delta = Net Expectancy (Conditioned) - Net Expectancy (Static Inside)",
            statistical_test="Paired block bootstrap difference test with Holm-Bonferroni correction",
            economic_gate="Net expectancy improvement >= 2.0 bps with positive OOS Sharpe ratio",
            rejection_criterion=(
                "Incremental net expectancy < 1.0 bps or paired test p-value >= 0.05."
            ),
        ),
        PreRegisteredHypothesis(
            hypothesis_id="P10A-H05",
            name="Inventory-Aware Quoting and Liquidation Cost Reduction",
            rationale=(
                "Accumulating directional inventory imposes adverse price drift risk and forced aggressive liquidation costs. "
                "Skewing quotes (asymmetrically widening quotes on the side of accumulated inventory and tightening on the reducing side) "
                "reduces inventory variance and avoids costly taker liquidation."
            ),
            measurable_prediction=(
                "Inventory-aware quoting (Avellaneda-Stoikov style skew) reduces round-trip liquidation and inventory "
                "carrying drag by at least 40% compared to symmetric quoting, resulting in higher net expectancy."
            ),
            metric="Inventory Drag Ratio = Total Terminal Liquidation & Holding Drag / Cumulative Gross Spread",
            statistical_test="Paired bootstrap test on terminal net P&L and inventory variance",
            economic_gate="Reduction of inventory standard deviation by >= 30% without negative net expectancy impact",
            rejection_criterion=(
                "Inventory variance reduction < 15% or net expectancy deterioration of > 1.5 bps."
            ),
        ),
        PreRegisteredHypothesis(
            hypothesis_id="P10A-H06",
            name="Positive Net Expectancy Under Conservative Fill and Latency Models",
            rationale=(
                "A realistic, conservative passive market making model incorporating queue priority, cancellation latency, "
                "partial fills, and conservative maker fees can achieve positive net expectancy per round trip without "
                "assuming perfect fill rates or zero-latency cancellations."
            ),
            measurable_prediction=(
                "Simulated passive execution with >= 50 ms cancel latency and queue-depletion fill modeling achieves "
                "OOS net expectancy > 0.0 bps per filled round trip (p < 0.01) across BTCUSDT, ETHUSDT, and SOLUSDT."
            ),
            metric="Net Expectancy per Round Trip (bps) after all maker fees, taker liquidation, and adverse selection",
            statistical_test="Block bootstrap t-test against null hypothesis of non-positive net expectancy (H0: Net <= 0)",
            economic_gate="Net expectancy > 0.0 bps per round trip in out-of-sample validation",
            rejection_criterion=(
                "OOS net expectancy <= 0.0 bps or lower 95% bootstrap confidence bound < 0.0 bps."
            ),
        ),
        PreRegisteredHypothesis(
            hypothesis_id="P10A-H07",
            name="Passive Edge Robustness Under Stressed Execution Assumptions",
            rationale=(
                "A genuine passive execution edge must remain robust to parameter degradation (increased latency, degraded "
                "fill probability, widened adverse selection, and fee increases) rather than collapsing under friction."
            ),
            measurable_prediction=(
                "Subjecting the model to the Phase 10A stress matrix (-10% fill probability, +25% latency, +25% slippage/adverse drift) "
                "preserves positive net expectancy (> 0.0 bps)."
            ),
            metric="Stressed Net Expectancy (bps) across the 7-dimensional stress test matrix",
            statistical_test="Worst-case stress scenario evaluation across block bootstrap realizations",
            economic_gate="Worst-case scenario net expectancy >= 0.0 bps",
            rejection_criterion=(
                "Net expectancy becomes negative (< 0.0 bps) under any single baseline stress perturbation."
            ),
        ),
    ]

    def __init__(self, storage_path: Optional[Path | str] = None):
        self.storage_path = Path(storage_path) if storage_path else Path("phase10a/manifests/hypothesis_registry.json")
        self._hypotheses: Dict[str, PreRegisteredHypothesis] = {}
        self.load()
        if not self._hypotheses:
            for hyp in self.DEFAULT_HYPOTHESES:
                self.register(hyp)
            self.save()

    def register(self, hypothesis: PreRegisteredHypothesis) -> None:
        """Registers a new hypothesis. Immutable once registered."""
        if hypothesis.hypothesis_id in self._hypotheses:
            raise ValueError(f"Hypothesis {hypothesis.hypothesis_id} is already registered.")
        self._hypotheses[hypothesis.hypothesis_id] = hypothesis

    def get(self, hypothesis_id: str) -> PreRegisteredHypothesis:
        """Retrieves a registered hypothesis by ID."""
        if hypothesis_id not in self._hypotheses:
            raise KeyError(f"Hypothesis {hypothesis_id} not found in registry.")
        return self._hypotheses[hypothesis_id]

    def list_all(self) -> List[PreRegisteredHypothesis]:
        """Lists all registered hypotheses ordered by ID."""
        return [self._hypotheses[k] for k in sorted(self._hypotheses.keys())]

    def update_status(self, hypothesis_id: str, new_status: str, notes: str = "") -> None:
        """Updates the evaluation status of a hypothesis."""
        hyp = self.get(hypothesis_id)
        hyp.status = new_status
        if notes:
            hyp.evaluation_notes = notes
        self.save()

    def save(self) -> None:
        """Persists the hypothesis registry to disk."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = {k: v.to_dict() for k, v in sorted(self._hypotheses.items())}
        self.storage_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def load(self) -> None:
        """Loads hypotheses from disk if present."""
        if self.storage_path.is_file():
            raw = json.loads(self.storage_path.read_text(encoding="utf-8"))
            self._hypotheses = {k: PreRegisteredHypothesis.from_dict(v) for k, v in raw.items()}
