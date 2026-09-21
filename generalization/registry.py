"""Pre-Registered Hypotheses Ledger and Multiple Testing Registry for Phase 6.

Maintains an immutable, pre-registered experiment ledger:
- Unique Experiment ID
- Execution Timestamp
- Formal Hypothesis Statement
- Dataset / Asset / Timeframe / Period
- Feature & Prompt Versions
- Configuration SHA256 Hash
- Random Seed
- Primary Metric & Success Criterion
- Empirical Result & Verdict Status (SUPPORTED, NOT_SUPPORTED, INCONCLUSIVE, INSUFFICIENT_SAMPLE, PREDICTIVE_BUT_NOT_ECONOMIC)
- Benjamini-Hochberg FDR Adjusted Significance
"""

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import hashlib
import json
from typing import Dict, Any, List, Optional


@dataclass
class Phase6ExperimentEntry:
    experiment_id: str
    timestamp: str
    hypothesis: str
    dataset: str
    asset: str
    timeframe: str
    period: str
    feature_version: str
    prompt_version: str
    configuration_hash: str
    random_seed: int
    primary_metric: str
    success_criterion: str
    empirical_result: str
    p_value: float
    adjusted_p_value: float
    fdr_significant: bool
    status: str
    notes: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class Phase6ExperimentRegistry:
    """Manages pre-registered experiments with multiple-testing control."""

    def __init__(self):
        self.entries: List[Phase6ExperimentEntry] = []

    @staticmethod
    def compute_config_hash(config_dict: Dict[str, Any]) -> str:
        """Calculates deterministic SHA256 of configuration parameters."""
        serialized = json.dumps(config_dict, sort_keys=True).encode("utf-8")
        return hashlib.sha256(serialized).hexdigest()[:16]

    def register(
        self,
        experiment_id: str,
        hypothesis: str,
        dataset: str,
        asset: str,
        timeframe: str,
        period: str,
        feature_version: str,
        prompt_version: str,
        configuration_dict: Dict[str, Any],
        random_seed: int,
        primary_metric: str,
        success_criterion: str,
        empirical_result: str,
        p_value: float,
        status: str,
        notes: str,
    ) -> Phase6ExperimentEntry:
        """Registers an experiment entry."""
        config_hash = self.compute_config_hash(configuration_dict)
        entry = Phase6ExperimentEntry(
            experiment_id=experiment_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            hypothesis=hypothesis,
            dataset=dataset,
            asset=asset,
            timeframe=timeframe,
            period=period,
            feature_version=feature_version,
            prompt_version=prompt_version,
            configuration_hash=config_hash,
            random_seed=random_seed,
            primary_metric=primary_metric,
            success_criterion=success_criterion,
            empirical_result=empirical_result,
            p_value=p_value,
            adjusted_p_value=p_value,  # updated by adjust_fdr
            fdr_significant=False,
            status=status,
            notes=notes,
        )
        self.entries.append(entry)
        return entry

    def apply_multiple_testing_adjustments(self, alpha: float = 0.05) -> None:
        """Calculates Benjamini-Hochberg FDR adjustments across all registered tests."""
        from generalization.statistics import apply_benjamini_hochberg_fdr

        p_vals = [e.p_value for e in self.entries]
        if not p_vals:
            return

        adjustments = apply_benjamini_hochberg_fdr(p_vals, alpha=alpha)
        for i, (adj_p, sig) in enumerate(adjustments):
            self.entries[i].adjusted_p_value = round(adj_p, 4)
            self.entries[i].fdr_significant = sig

    def to_list(self) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self.entries]

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_list(), indent=indent)
