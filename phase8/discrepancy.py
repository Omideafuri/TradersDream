"""Formal Discrepancy Registry and Management Engine.

Tracks, categorizes, and audits any numerical, structural, or data discrepancies
discovered across Phases 1–7.
Severity levels:
- INFO: Informational note or minor formatting observation (no impact on conclusions).
- MINOR: Negligible rounding or precision difference (< 0.05% or < 1 bps).
- MATERIAL: Substantive difference that alters interpretation or requires investigation.
- CRITICAL: Severe failure that invalidates prior conclusions or safety invariants.
"""

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Any, List, Optional
import pandas as pd


@dataclass
class DiscrepancyRecord:
    discrepancy_id: str
    phase: str
    module: str
    metric: str
    reported_value: str
    recomputed_value: str
    delta: str
    severity: str  # "INFO", "MINOR", "MATERIAL", "CRITICAL"
    root_cause: str
    impact: str
    action: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DiscrepancyRegistry:
    """Manages the lifecycle of formal research discrepancies."""

    def __init__(self):
        self.discrepancies: List[DiscrepancyRecord] = []

    def record_discrepancy(
        self,
        discrepancy_id: str,
        phase: str,
        module: str,
        metric: str,
        reported_value: Any,
        recomputed_value: Any,
        delta: Any,
        severity: str,
        root_cause: str,
        impact: str,
        action: str,
    ) -> DiscrepancyRecord:
        """Appends a new discrepancy record to the registry."""
        rec = DiscrepancyRecord(
            discrepancy_id=discrepancy_id,
            phase=phase,
            module=module,
            metric=metric,
            reported_value=str(reported_value),
            recomputed_value=str(recomputed_value),
            delta=str(delta),
            severity=severity,
            root_cause=root_cause,
            impact=impact,
            action=action,
        )
        self.discrepancies.append(rec)
        return rec

    def has_critical_failure(self) -> bool:
        """Checks if any CRITICAL discrepancy exists."""
        return any(d.severity == "CRITICAL" for d in self.discrepancies)

    def has_material_discrepancy(self) -> bool:
        """Checks if any MATERIAL discrepancy exists."""
        return any(d.severity == "MATERIAL" for d in self.discrepancies)

    def export_csv(self, file_path: str) -> None:
        """Exports all discrepancies to CSV format."""
        p = Path(file_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        if self.discrepancies:
            df = pd.DataFrame([d.to_dict() for d in self.discrepancies])
        else:
            df = pd.DataFrame(columns=[
                "discrepancy_id", "phase", "module", "metric", "reported_value",
                "recomputed_value", "delta", "severity", "root_cause", "impact", "action"
            ])
        df.to_csv(file_path, index=False)

    def to_dict_list(self) -> List[Dict[str, Any]]:
        return [d.to_dict() for d in self.discrepancies]
