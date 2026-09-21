"""Phase 5 Experiment Registry.

Maintains a structured, immutable log of all reconstruction experiments:
- Unique Experiment ID
- Explicit Hypothesis
- Configuration & Feature Sets
- Train / Validation / Test Periods
- Out-of-Sample Performance Metrics
- Status Classification: SUPPORTED, NOT_SUPPORTED, INCONCLUSIVE, INSUFFICIENT_SAMPLE
"""

from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional
import json


@dataclass
class ExperimentRecord:
    experiment_id: str
    hypothesis: str
    feature_set: List[str]
    sample_window: str
    in_sample_metric: str
    out_of_sample_metric: str
    hurdle_rate_bps: float
    status: str  # SUPPORTED, NOT_SUPPORTED, INCONCLUSIVE, INSUFFICIENT_SAMPLE
    key_findings: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ExperimentRegistry:
    """In-memory and serializable registry for Phase 5 experiments."""

    def __init__(self):
        self.records: List[ExperimentRecord] = []

    def register(
        self,
        experiment_id: str,
        hypothesis: str,
        feature_set: List[str],
        sample_window: str,
        in_sample_metric: str,
        out_of_sample_metric: str,
        hurdle_rate_bps: float,
        status: str,
        key_findings: str,
    ) -> ExperimentRecord:
        record = ExperimentRecord(
            experiment_id=experiment_id,
            hypothesis=hypothesis,
            feature_set=feature_set,
            sample_window=sample_window,
            in_sample_metric=in_sample_metric,
            out_of_sample_metric=out_of_sample_metric,
            hurdle_rate_bps=hurdle_rate_bps,
            status=status,
            key_findings=key_findings,
        )
        self.records.append(record)
        return record

    def to_list(self) -> List[Dict[str, Any]]:
        return [r.to_dict() for r in self.records]

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_list(), indent=indent)
