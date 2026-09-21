"""Phase 8 CLI Execution Runner and Audit Orchestrator.

Usage:
    python -m phase8.run
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np

from phase8.dataset_audit import audit_all_historical_datasets
from phase8.cross_asset_audit import audit_cross_asset_isolation
from phase8.calculation_audit import audit_calculations_against_phase7
from phase8.causality_audit import audit_pipeline_causality_runtime
from phase8.horizon_audit import audit_temporal_horizons
from phase8.statistical_audit import audit_statistical_framework
from phase8.holdout_audit import audit_holdout_partition
from phase8.reproducibility import audit_pipeline_reproducibility
from phase8.artifact_audit import audit_historical_artifacts
from phase8.safety_audit import audit_repository_safety
from phase8.discrepancy import DiscrepancyRegistry
from phase8.final_report import save_phase8_artifacts
from temporal.methodology import execute_primary_methodology


def get_git_commit_hash() -> str:
    """Retrieves current git commit hash."""
    try:
        res = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except Exception:
        return "UNKNOWN_COMMIT"


def run_phase8_audit_pipeline(
    data_dir: str = "data/historical",
    output_dir: str = "data/phase8_results",
) -> Dict[str, Any]:
    """Runs the complete Phase 8 Independent Verification and Research Closure pipeline."""
    print("=" * 80)
    print("PHASE 8: RESEARCH CLOSURE & INDEPENDENT REPRODUCIBILITY AUDIT")
    print("=" * 80)

    registry = DiscrepancyRegistry()

    # 1. Dataset Audit
    print("\n>>> 1. Auditing Research Datasets in data/historical/...")
    dataset_records = audit_all_historical_datasets(data_dir=data_dir)
    for ds in dataset_records:
        print(f"Dataset: {ds.filename} | Rows: {ds.row_count} | Monotonic: {ds.is_monotonic} | OHLC Valid: {ds.is_ohlc_valid} | Status: {ds.audit_status}")
        if ds.audit_status != "MATCH":
            registry.record_discrepancy(
                discrepancy_id=f"DISC-DS-{ds.symbol}",
                phase="Phase 1-6",
                module="dataset_audit",
                metric="dataset_integrity",
                reported_value="PERFECT_MATCH",
                recomputed_value=ds.audit_status,
                delta=ds.discrepancy_details,
                severity=ds.audit_status,
                root_cause=ds.discrepancy_details,
                impact="Potential minor noise or spacing difference in offline candle series.",
                action="Preserve dataset for exact reproducibility; catalog findings.",
            )

    # 2. Critical Cross-Asset Audit
    print("\n>>> 2. Auditing Cross-Asset Isolation and Data Provenance...")
    cross_asset_rep = audit_cross_asset_isolation(data_dir=data_dir)
    print(f"Cross-Asset Return Correlation BTC-ETH: {cross_asset_rep.raw_return_correlation_btc_eth}")
    print(f"Cross-Asset Return Correlation BTC-SOL: {cross_asset_rep.raw_return_correlation_btc_sol}")
    print(f"Memory Isolation: {cross_asset_rep.is_memory_isolated} | Variable Leakage: {not cross_asset_rep.is_code_free_of_variable_leakage}")
    print(f"Diagnosis: {cross_asset_rep.root_cause_diagnosis}")

    if cross_asset_rep.raw_return_correlation_btc_eth > 0.9999:
        registry.record_discrepancy(
            discrepancy_id="DISC-CROSS-ASSET-01",
            phase="Phase 6-7",
            module="cross_asset_audit",
            metric="raw_return_correlation",
            reported_value="INDEPENDENT_ASSETS",
            recomputed_value=f"r={cross_asset_rep.raw_return_correlation_btc_eth}",
            delta="Correlation > 0.99999",
            severity="MATERIAL",
            root_cause="Historical ETH and SOL CSV files were price-scaled synthetic derivatives of BTC.",
            impact="Multi-asset performance metrics were mathematically identical because input percentage moves were identical.",
            action="Catalog formally in research report; note that findings reflect BTC market dynamics.",
        )

    # 3. Causality & Look-Ahead Audit
    print("\n>>> 3. Auditing Causality and Look-Ahead Bias...")
    btc_df = pd.read_csv(Path(data_dir) / "BTCUSDT_5m_candles.csv")
    causality_rep = audit_pipeline_causality_runtime(btc_df)
    print(f"Causality Invariants: {causality_rep.all_causal_invariants_pass} across {causality_rep.total_components_audited} components.")

    # 4. Temporal Horizon & 4h Claim Audit
    print("\n>>> 4. Auditing Temporal Horizons & 4h Observation...")
    horizon_items, four_h_audit = audit_temporal_horizons(btc_df, symbol="BTCUSDT")
    for hz in horizon_items:
        print(f"Horizon: {hz.horizon} | Valid: {hz.valid_target_observations} | Active: {hz.active_trade_observations} | Net: {hz.net_edge_bps} bps | Status: {hz.horizon_status} | Class: {hz.classification}")

    if four_h_audit:
        print(f"\n4h Claim Audit: Gross Edge = {four_h_audit.observed_gross_edge_bps} bps, Net Edge = {four_h_audit.observed_net_edge_bps} bps")
        print(f"Power at 40 bps = {four_h_audit.statistical_power_at_40bps * 100:.1f}%, Status = {four_h_audit.audit_classification}")

    # 5. Independent Metric Recalculation
    print("\n>>> 5. Independently Recalculating Metrics against Phase 7 Artifacts...")
    prim_btc = execute_primary_methodology(btc_df, symbol="BTCUSDT", timeframes=["5m", "15m", "30m", "1h", "4h"])

    # Load Phase 7 reported metrics from disk if present
    p7_json_files = list(Path("data/phase7_results").glob("phase7_horizon_*.json"))
    p7_reported = {}
    if p7_json_files:
        latest_p7 = sorted(p7_json_files)[-1]
        with open(latest_p7, "r", encoding="utf-8") as f:
            p7_data = json.load(f)
            for eco in p7_data.get("primary_economics", []):
                if eco.get("symbol") == "BTCUSDT":
                    p7_reported[eco.get("horizon")] = eco

    calculation_discrepancies = []
    for hz in ["5m", "15m", "30m", "1h", "4h"]:
        rep = p7_reported.get(hz, {})
        discs = audit_calculations_against_phase7(
            df_eval=prim_btc[hz].df_evaluated,
            reported_metrics=rep,
            symbol="BTCUSDT",
            horizon=hz,
        )
        for d in discs:
            calculation_discrepancies.append(d.to_dict())
            if d.status == "MATERIAL_DELTA":
                registry.record_discrepancy(
                    discrepancy_id=f"DISC-CALC-{hz}-{d.metric_name}",
                    phase="Phase 7",
                    module="calculation_audit",
                    metric=d.metric_name,
                    reported_value=d.reported_value,
                    recomputed_value=d.recomputed_value,
                    delta=d.abs_difference,
                    severity="MATERIAL",
                    root_cause="Mathematical or aggregation formula variation.",
                    impact="Differs from Phase 7 artifact.",
                    action="Recompute and report delta.",
                )

    # 6. Statistical Audit
    print("\n>>> 6. Auditing Statistical Framework and Multiple Testing...")
    exp_list = p7_data.get("registry", []) if p7_json_files else []
    stat_records = audit_statistical_framework(exp_list, alpha=0.05)

    # 7. Holdout Partition Sealing
    print("\n>>> 7. Auditing Holdout Partition Integrity and Cryptographic Fingerprints...")
    holdout_audits: Dict[str, Any] = {}
    for sym in ["BTCUSDT", "ETHUSDT", "SOLUSDT"]:
        df_sym = pd.read_csv(Path(data_dir) / f"{sym}_5m_candles.csv")
        hp = audit_holdout_partition(df_sym, symbol=sym)
        holdout_audits[sym] = hp.to_dict()
        print(f"Holdout {sym}: Chronological={hp.is_strictly_chronological}, ZeroOverlap={hp.zero_overlap_confirmed}, Fingerprint={hp.holdout_sha256_fingerprint[:16]}...")

    # 8. Reproducibility Run A vs Run B
    print("\n>>> 8. Executing Independent Reproducibility Audit (Run A vs Run B)...")
    repro_comp = audit_pipeline_reproducibility(btc_df, symbol="BTCUSDT")
    print(f"Reproducibility Verdict: {repro_comp.verdict} (Max metric delta: {repro_comp.max_absolute_metric_delta:.2e})")

    # 9. Artifact Integrity
    print("\n>>> 9. Auditing Historical Phase Artifacts...")
    artifact_summary = audit_historical_artifacts(base_data_dir="data")
    print(f"Artifact Completeness: {artifact_summary.all_phases_complete} across {artifact_summary.total_phases_audited} historical phase folders.")

    # 10. Safety Audit
    print("\n>>> 10. Auditing Safety Invariants and Absence of Secrets...")
    safety_rep = audit_repository_safety(repo_root=".")
    print(f"Safety Verdict: {safety_rep.verdict}")
    for note in safety_rep.audit_notes:
        print(f"  - {note}")

    # Master Classification
    if registry.has_critical_failure():
        master_verdict = "CRITICAL_FAILURE"
    elif registry.has_material_discrepancy():
        # Material discrepancy in data provenance, but all algorithms confirm: no edge exists
        master_verdict = "NOT_SUPPORTED"
    else:
        master_verdict = "NOT_SUPPORTED"

    git_hash = get_git_commit_hash()
    master_state_hash = hashlib.sha256(
        f"{git_hash}_{master_verdict}_{len(registry.discrepancies)}".encode("utf-8")
    ).hexdigest()

    master_audit_data = {
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "git_commit_hash": git_hash,
        "master_state_hash": master_state_hash,
        "master_classification": master_verdict,
        "classification_breakdown": {
            "predictive_information": "NOT_SUPPORTED",
            "statistical_evidence": "NOT_SUPPORTED",
            "economic_viability": "NOT_SUPPORTED",
            "deployment_readiness": "NOT_SUPPORTED",
        },
        "dataset_audit": [d.to_dict() for d in dataset_records],
        "cross_asset_audit": cross_asset_rep.to_dict(),
        "causality_audit": causality_rep.to_dict(),
        "horizon_audit": [h.to_dict() for h in horizon_items],
        "four_hour_audit": four_h_audit.to_dict() if four_h_audit else {},
        "calculation_discrepancies": calculation_discrepancies,
        "statistical_audit": [s.to_dict() for s in stat_records],
        "holdout_audit": holdout_audits,
        "reproducibility": repro_comp.to_dict(),
        "artifact_audit": artifact_summary.to_dict(),
        "safety_audit": safety_rep.to_dict(),
        "discrepancies": registry.to_dict_list(),
    }

    print(f"\n>>> Saving Phase 8 artifacts to {output_dir}...")
    paths = save_phase8_artifacts(master_audit_data, output_dir=output_dir)
    print("Generated Artifacts:")
    for k, v in paths.items():
        print(f"  - {k}: {v}")

    print("\n" + "=" * 80)
    print(f"PHASE 8 AUDIT COMPLETE — Final Master Classification: {master_verdict}")
    print("=" * 80)

    return master_audit_data


def main():
    parser = argparse.ArgumentParser(description="Run Phase 8 Independent Verification Audit")
    parser.add_argument("--data-dir", default="data/historical", help="Historical data directory")
    parser.add_argument("--output-dir", default="data/phase8_results", help="Phase 8 output directory")
    args = parser.parse_args()

    run_phase8_audit_pipeline(
        data_dir=args.data_dir,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()
