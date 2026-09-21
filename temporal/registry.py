"""Pre-Registered Hypothesis and Experiment Registry for Phase 7.

Records immutable pre-registered hypotheses, configuration hashes,
execution details, and applies Benjamini-Hochberg False Discovery Rate (FDR)
adjustments across all tested hypotheses.
"""

from dataclasses import dataclass, asdict
import hashlib
import json
from typing import Dict, Any, List, Optional, Tuple
from generalization.statistics import apply_benjamini_hochberg_fdr


@dataclass
class Phase7ExperimentEntry:
    experiment_id: str
    hypothesis: str
    asset: str
    horizon: str
    execution_frequency: str
    dataset_hash: str
    period: str
    jev_provider: str
    prompt_version: str
    feature_version: str
    configuration_hash: str
    random_seed: int
    primary_metric: str
    success_criterion: str
    raw_p_value: float
    adjusted_p_value: float
    observed_effect_bps: float
    result: str  # e.g., "SUPPORTED", "NOT_SUPPORTED", "PREDICTIVE_BUT_NOT_ECONOMIC"
    status: str  # "COMPLETED", "REJECTED"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class Phase7ExperimentRegistry:
    """Manages pre-registered Phase 7 hypotheses and FDR control."""

    FROZEN_CONFIG = {
        "jev_provider": "JevApiProvider (Frozen Phase 5/6 System One API)",
        "prompt_version": "v5.0-structured-choice-abstention",
        "feature_version": "v5.0-causal-market-structure",
        "regime_version": "v5.0-6class-causal",
        "uncertainty_version": "v5.0-indicator-contradiction",
        "abstention_version": "v5.0-explicit-no-edge-threshold-0.50",
        "cost_model": {
            "fee_bps": 10.0,
            "slippage_bps": 5.0,
            "round_trip_friction_bps": 30.0,
            "safety_margin_bps": 10.0,
            "economic_hurdle_bps": 40.0,
        },
    }

    def __init__(self):
        self.experiments: List[Phase7ExperimentEntry] = []
        self._config_hash = hashlib.sha256(
            json.dumps(self.FROZEN_CONFIG, sort_keys=True).encode("utf-8")
        ).hexdigest()

    @property
    def configuration_hash(self) -> str:
        return self._config_hash

    def register_experiment(
        self,
        experiment_id: str,
        hypothesis: str,
        asset: str,
        horizon: str,
        execution_frequency: str,
        dataset_hash: str,
        period: str,
        primary_metric: str,
        success_criterion: str,
        raw_p_value: float,
        observed_effect_bps: float,
        result: str,
        random_seed: int = 42,
    ) -> Phase7ExperimentEntry:
        """Appends a completed experiment record."""
        entry = Phase7ExperimentEntry(
            experiment_id=experiment_id,
            hypothesis=hypothesis,
            asset=asset,
            horizon=horizon,
            execution_frequency=execution_frequency,
            dataset_hash=dataset_hash,
            period=period,
            jev_provider=self.FROZEN_CONFIG["jev_provider"],
            prompt_version=self.FROZEN_CONFIG["prompt_version"],
            feature_version=self.FROZEN_CONFIG["feature_version"],
            configuration_hash=self._config_hash,
            random_seed=random_seed,
            primary_metric=primary_metric,
            success_criterion=success_criterion,
            raw_p_value=raw_p_value,
            adjusted_p_value=raw_p_value,  # Updated on finalize
            observed_effect_bps=observed_effect_bps,
            result=result,
            status="COMPLETED",
        )
        self.experiments.append(entry)
        return entry

    def finalize_multiple_testing_correction(self, alpha: float = 0.05) -> List[Phase7ExperimentEntry]:
        """Applies Benjamini-Hochberg FDR correction across all registered experiments."""
        if not self.experiments:
            return []

        raw_p_vals = [e.raw_p_value for e in self.experiments]
        fdr_results = apply_benjamini_hochberg_fdr(raw_p_vals, alpha=alpha)

        for i, (adj_p, is_sig) in enumerate(fdr_results):
            self.experiments[i].adjusted_p_value = round(adj_p, 4)
            if not is_sig and self.experiments[i].result == "SUPPORTED":
                self.experiments[i].result = "NOT_SUPPORTED_FAILED_FDR"

        return self.experiments

    def to_dict_list(self) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self.experiments]
