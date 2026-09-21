"""Pre-registered Hypothesis Registry for Phase 9D Microstructure Research.

Formally records and freezes hypotheses prior to feature calculation and evaluation,
enforcing scientific rigor, non-retrospective inquiry, and multiple-testing tracking.
"""

from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Dict, List, Optional, Any


class Phase9DStatus:
    PREREGISTERED = "PREREGISTERED"
    EVALUATING = "EVALUATING"
    SUPPORTED = "SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    INCONCLUSIVE = "INCONCLUSIVE"
    REJECTED = "REJECTED"
    ECONOMICALLY_INSUFFICIENT = "ECONOMICALLY_INSUFFICIENT"
    WEAK_OBSERVATION_ONLY = "WEAK_OBSERVATION_ONLY"


@dataclass
class PreRegisteredHypothesis:
    hypothesis_id: str
    name: str
    statement: str
    mathematical_definition: str
    dependent_variable: str
    independent_variables: List[str]
    prediction_horizons: List[int]       # in bars (e.g. 1=5m, 3=15m, 6=30m, 12=1h)
    train_validation_policy: str
    economic_hurdle_bps: float
    statistical_test: str
    multiple_testing_correction: str
    rejection_criteria: str
    support_criteria: str
    minimum_sample_requirement: int
    status: str = Phase9DStatus.PREREGISTERED
    registered_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    evaluation_notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PreRegisteredHypothesis":
        return cls(**data)


class Phase9DHypothesisRegistry:
    """Registry maintaining formal pre-registered Phase 9D research hypotheses."""

    def __init__(self, storage_path: Optional[Path | str] = None):
        self.storage_path = Path(storage_path) if storage_path else Path("phase9d/manifests/hypothesis_registry.json")
        self._hypotheses: Dict[str, PreRegisteredHypothesis] = {}
        self.load()
        if not self._hypotheses:
            self._register_default_hypotheses()

    def register(self, h: PreRegisteredHypothesis, allow_update: bool = False) -> None:
        if h.hypothesis_id in self._hypotheses and not allow_update:
            raise ValueError(f"Hypothesis {h.hypothesis_id} already registered. Post-hoc mutation forbidden.")
        self._hypotheses[h.hypothesis_id] = h
        self.save()

    def get(self, hypothesis_id: str) -> PreRegisteredHypothesis:
        if hypothesis_id not in self._hypotheses:
            raise KeyError(f"Hypothesis {hypothesis_id} not registered.")
        return self._hypotheses[hypothesis_id]

    def list_all(self) -> List[PreRegisteredHypothesis]:
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
                self._hypotheses = {k: PreRegisteredHypothesis.from_dict(v) for k, v in data.items()}
            except Exception:
                self._hypotheses = {}

    def _register_default_hypotheses(self) -> None:
        """Pre-registers the 5 core Phase 9D research hypotheses."""
        defaults = [
            PreRegisteredHypothesis(
                hypothesis_id="P9D-H01",
                name="Order-Book Depth Imbalance",
                statement="Short-horizon bid/ask depth imbalance contains directional predictive information about subsequent returns after controlling for Phase 9C regime and volatility.",
                mathematical_definition="Imbalance = (BidDepth - AskDepth) / (BidDepth + AskDepth); test Corr(Imbalance_t, Return_{t+h} | Regime_t)",
                dependent_variable="target_ret_1 (5m forward log return)",
                independent_variables=["ob_imbalance_l1", "ob_imbalance_l5", "ob_imbalance_l10"],
                prediction_horizons=[1, 3, 6],
                train_validation_policy="Chronological Dev (60%) -> Validation (20%)",
                economic_hurdle_bps=40.0,
                statistical_test="Partial Spearman rank correlation & logistic regression controlling for realized_vol and regime",
                multiple_testing_correction="Benjamini-Hochberg FDR at alpha = 0.05",
                rejection_criteria="FDR q-value >= 0.05 or Spearman IC <= 0.02 or gross edge <= 0 bps",
                support_criteria="FDR q-value < 0.05, Spearman IC > 0.03, and net edge > 0 bps after total dynamic friction",
                minimum_sample_requirement=500,
            ),
            PreRegisteredHypothesis(
                hypothesis_id="P9D-H02",
                name="Spread State and Adverse Price Drift",
                statement="Relative bid/ask spread predicts subsequent adverse price movement, volatility expansion, and execution cost deterioration.",
                mathematical_definition="Spread_bps = (AskPrice - BidPrice) / MidPrice * 10000; test Corr(Spread_bps_t, Forward_Vol_{t+h})",
                dependent_variable="target_vol_1 (5m forward volatility), target_abs_ret_1",
                independent_variables=["spread_bps", "relative_spread"],
                prediction_horizons=[1, 3, 6],
                train_validation_policy="Chronological Dev (60%) -> Validation (20%)",
                economic_hurdle_bps=40.0,
                statistical_test="Spearman rank correlation and linear regression against forward volatility / execution penalty",
                multiple_testing_correction="Benjamini-Hochberg FDR at alpha = 0.05",
                rejection_criteria="FDR q-value >= 0.05 or Spearman IC <= 0.03",
                support_criteria="FDR q-value < 0.05, Spearman IC > 0.05, predicting execution friction and dispersion",
                minimum_sample_requirement=500,
            ),
            PreRegisteredHypothesis(
                hypothesis_id="P9D-H03",
                name="Trade-Flow Imbalance Persistence",
                statement="Aggressor-side trade volume imbalance contains incremental directional information about subsequent returns beyond OHLCV volume proxies.",
                mathematical_definition="TFI = (BuyVolume - SellVolume) / (BuyVolume + SellVolume); test Incremental IC(TFI_t, Return_{t+h}) beyond rel_volume_48",
                dependent_variable="target_ret_1 (5m forward log return)",
                independent_variables=["aggressor_imbalance", "signed_volume", "buy_sell_ratio"],
                prediction_horizons=[1, 3, 6],
                train_validation_policy="Chronological Dev (60%) -> Validation (20%)",
                economic_hurdle_bps=40.0,
                statistical_test="Incremental R^2 and delta rank IC over Phase 9C volume features",
                multiple_testing_correction="Benjamini-Hochberg FDR at alpha = 0.05",
                rejection_criteria="Delta rank IC <= 0.01 or FDR q-value >= 0.05",
                support_criteria="Delta rank IC > 0.02 with FDR q < 0.05 and positive net expectancy after dynamic friction",
                minimum_sample_requirement=500,
            ),
            PreRegisteredHypothesis(
                hypothesis_id="P9D-H04",
                name="Microstructure x Regime Interaction",
                statement="Microstructure order-book and trade-flow imbalance become significantly more informative under high-volatility and trending regime states.",
                mathematical_definition="Interaction = Imbalance * HighVol_Dummy; test Beta(Interaction) in predicting Return_{t+h}",
                dependent_variable="target_ret_1, target_dir_1",
                independent_variables=["imbalance_x_highvol", "imbalance_x_trending", "tfi_x_highvol"],
                prediction_horizons=[1, 3],
                train_validation_policy="Chronological Dev (60%) -> Validation (20%)",
                economic_hurdle_bps=40.0,
                statistical_test="Likelihood ratio test and interaction coefficient t-test across regime subsets",
                multiple_testing_correction="Benjamini-Hochberg FDR at alpha = 0.05",
                rejection_criteria="Interaction p-value >= 0.05 across all tested horizons",
                support_criteria="Statistically significant interaction coefficient (q < 0.05) with higher IC in target regimes",
                minimum_sample_requirement=300,
            ),
            PreRegisteredHypothesis(
                hypothesis_id="P9D-H05",
                name="Microstructure Incremental Information Content",
                statement="Combining microstructure variables with Phase 9C causal features produces statistically significant incremental accuracy and net expectancy over Phase 9C features alone (Model B vs Baseline A).",
                mathematical_definition="Delta_AUC = AUC(Model_B) - AUC(Baseline_A); Delta_Expectancy = Expectancy(Model_B) - Expectancy(Baseline_A)",
                dependent_variable="target_dir_1 (5m forward direction), net_expectancy_bps",
                independent_variables=["Full Phase 9C Features + Microstructure Vector"],
                prediction_horizons=[1, 3],
                train_validation_policy="Chronological Dev (60%) -> Validation (20%) -> Frozen Holdout (20%)",
                economic_hurdle_bps=40.0,
                statistical_test="Block bootstrap CI of Delta_AUC and DeLong / permutation test for ROC comparison",
                multiple_testing_correction="Holm-Bonferroni FWER at alpha = 0.05",
                rejection_criteria="Delta_AUC <= 0 or 95% CI of Delta_AUC overlaps 0 or Delta_Expectancy <= 0 bps",
                support_criteria="Delta_AUC > 0.015 (p < 0.05) and Delta_Net_Expectancy > 0 bps after dynamic friction",
                minimum_sample_requirement=1000,
            ),
        ]
        for h in defaults:
            self.register(h)
