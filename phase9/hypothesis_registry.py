"""Pre-registered Hypothesis Registry for Phase 9 research.

Implements strict scientific hypothesis registration prior to model development or
data exploration, preventing hindsight bias, p-hacking, and post-hoc rationalization.
"""

from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Dict, List, Optional, Any


class HypothesisStatus:
    PREREGISTERED = "PREREGISTERED"
    DATA_PENDING = "DATA_PENDING"
    EVALUATING = "EVALUATING"
    SUPPORTED = "SUPPORTED"
    NOT_SUPPORTED = "NOT_SUPPORTED"
    INCONCLUSIVE = "INCONCLUSIVE"


@dataclass
class HypothesisRecord:
    hypothesis_id: str
    statement: str
    required_data: str
    primary_metric: str
    null_hypothesis: str
    alternative_hypothesis: str
    economic_hurdle_bps: float
    dataset_scope: str
    status: str = HypothesisStatus.PREREGISTERED
    registration_timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    evaluation_notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HypothesisRecord":
        return cls(**data)


class HypothesisRegistry:
    """Registry maintaining formal pre-registered research hypotheses."""

    def __init__(self, storage_path: Optional[Path | str] = None):
        self.storage_path = Path(storage_path) if storage_path else Path("phase9/manifests/hypothesis_registry.json")
        self._hypotheses: Dict[str, HypothesisRecord] = {}
        self.load()
        if not self._hypotheses:
            self._register_default_phase9_hypotheses()

    def register(self, record: HypothesisRecord, allow_update: bool = False) -> None:
        """Registers a new hypothesis. Updates to existing hypotheses require allow_update=True."""
        if record.hypothesis_id in self._hypotheses and not allow_update:
            raise ValueError(f"Hypothesis {record.hypothesis_id} is already registered. Modifications forbidden.")
        self._hypotheses[record.hypothesis_id] = record
        self.save()

    def get(self, hypothesis_id: str) -> HypothesisRecord:
        if hypothesis_id not in self._hypotheses:
            raise KeyError(f"Hypothesis {hypothesis_id} not found in registry.")
        return self._hypotheses[hypothesis_id]

    def list_all(self) -> List[HypothesisRecord]:
        return list(self._hypotheses.values())

    def update_status(self, hypothesis_id: str, new_status: str, notes: str = "") -> None:
        rec = self.get(hypothesis_id)
        rec.status = new_status
        if notes:
            rec.evaluation_notes = notes
        self.save()

    def save(self) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = {k: v.to_dict() for k, v in self._hypotheses.items()}
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def load(self) -> None:
        if self.storage_path.is_file():
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._hypotheses = {k: HypothesisRecord.from_dict(v) for k, v in data.items()}
            except Exception:
                self._hypotheses = {}

    def _register_default_phase9_hypotheses(self) -> None:
        """Registers canonical H1–H8 hypotheses pre-specified in the Phase 9 research charter."""
        defaults = [
            HypothesisRecord(
                hypothesis_id="H1_ORDERBOOK_IMBALANCE",
                statement="Order-book depth imbalance contains directional predictive information beyond OHLCV.",
                required_data="L2_ORDERBOOK_DEPTH",
                primary_metric="Spearman rank correlation with forward 1m/5m return",
                null_hypothesis="rho(depth_imbalance, forward_return) <= 0",
                alternative_hypothesis="rho(depth_imbalance, forward_return) > 0.05",
                economic_hurdle_bps=20.0,
                dataset_scope="BTCUSDT, ETHUSDT, SOLUSDT (independent)",
            ),
            HypothesisRecord(
                hypothesis_id="H2_TRADE_FLOW",
                statement="Aggressive buy/sell trade volume imbalance contains directional information beyond technical indicators.",
                required_data="TICK_AGGRESSIVE_FLOW",
                primary_metric="Information coefficient (IC) with forward 1m/5m return",
                null_hypothesis="IC(flow_imbalance, forward_return) <= 0",
                alternative_hypothesis="IC(flow_imbalance, forward_return) > 0.05",
                economic_hurdle_bps=20.0,
                dataset_scope="BTCUSDT, ETHUSDT, SOLUSDT (independent)",
            ),
            HypothesisRecord(
                hypothesis_id="H3_SPREAD_CONDITIONING",
                statement="Predictive signal quality and directional expectancy vary systematically as a function of bid-ask spread.",
                required_data="SPREAD_SERIES, CANDLES",
                primary_metric="Net return difference across spread quartiles",
                null_hypothesis="Delta_return(narrow_spread, wide_spread) <= 0",
                alternative_hypothesis="Delta_return(narrow_spread, wide_spread) > 10.0 bps",
                economic_hurdle_bps=15.0,
                dataset_scope="BTCUSDT, ETHUSDT, SOLUSDT (independent)",
            ),
            HypothesisRecord(
                hypothesis_id="H4_LIQUIDITY_CONDITIONING",
                statement="Signal quality improves in high top-of-book depth regimes compared to thin market conditions.",
                required_data="TOP_OF_BOOK_DEPTH, CANDLES",
                primary_metric="Sharpe ratio differential between high vs low liquidity regimes",
                null_hypothesis="Sharpe(high_liq) - Sharpe(low_liq) <= 0",
                alternative_hypothesis="Sharpe(high_liq) - Sharpe(low_liq) > 0.3",
                economic_hurdle_bps=15.0,
                dataset_scope="BTCUSDT, ETHUSDT, SOLUSDT (independent)",
            ),
            HypothesisRecord(
                hypothesis_id="H5_FUNDING_RATE",
                statement="Perpetual swap funding rate and open interest contain incremental predictive information for spot/perp basis drift.",
                required_data="FUNDING_RATES, OPEN_INTEREST",
                primary_metric="8-hour forward return predictability from funding skew",
                null_hypothesis="Beta(funding_rate, forward_8h_return) == 0",
                alternative_hypothesis="|Beta(funding_rate, forward_8h_return)| > 0",
                economic_hurdle_bps=30.0,
                dataset_scope="BTCUSDT, ETHUSDT, SOLUSDT (perpetual)",
            ),
            HypothesisRecord(
                hypothesis_id="H6_EXECUTION_TIMING",
                statement="Execution quality (passive limit orders vs active taker orders) materially affects realized trading edge.",
                required_data="LIMIT_QUEUE_SIMULATION, SPREAD, LATENCY",
                primary_metric="Net P&L difference between maker vs taker execution",
                null_hypothesis="Net_PnL(maker) - Net_PnL(taker) <= 0",
                alternative_hypothesis="Net_PnL(maker) - Net_PnL(taker) > 20.0 bps",
                economic_hurdle_bps=10.0,
                dataset_scope="BTCUSDT, ETHUSDT, SOLUSDT (independent)",
            ),
            HypothesisRecord(
                hypothesis_id="H7_HORIZON_SURVIVAL",
                statement="Any microstructure-derived signal retains predictive power beyond the immediate 1m–5m microstructure horizon.",
                required_data="MULTI_TIMEFRAME_MICROSTRUCTURE",
                primary_metric="Decay half-life of directional accuracy across 1m, 5m, 15m, 1h",
                null_hypothesis="Half_life(signal) <= 5 minutes",
                alternative_hypothesis="Half_life(signal) > 15 minutes",
                economic_hurdle_bps=25.0,
                dataset_scope="BTCUSDT, ETHUSDT, SOLUSDT (independent)",
            ),
            HypothesisRecord(
                hypothesis_id="H8_ECONOMIC_VIABILITY",
                statement="At least one predictive signal clears realistic total execution friction (fees + spread + slippage + market impact + latency + safety margin) with statistically significant positive net expectancy.",
                required_data="COMBINED_MICROSTRUCTURE_AND_PRICES",
                primary_metric="Net expectancy per trade after total friction",
                null_hypothesis="Net_Expectancy <= 0.0 bps",
                alternative_hypothesis="Net_Expectancy > 0.0 bps with p < 0.05 after FDR correction",
                economic_hurdle_bps=35.0,
                dataset_scope="BTCUSDT, ETHUSDT, SOLUSDT (independent)",
            ),
        ]
        for h in defaults:
            self.register(h)
