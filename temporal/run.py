"""Phase 7 CLI Execution Runner and Pipeline Orchestrator.

Usage:
    python -m temporal.run --symbols BTCUSDT,ETHUSDT,SOLUSDT
"""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np

from generalization.data_loader import DatasetLoader
from temporal.data_aggregator import TemporalDataAggregator
from temporal.methodology import execute_primary_methodology, execute_secondary_methodology
from temporal.signal_eval import evaluate_signal_metrics
from temporal.cost_model import evaluate_horizon_economics
from temporal.frequency_effect import audit_frequency_effect
from temporal.monotonicity import evaluate_temporal_monotonicity
from temporal.power_audit import audit_statistical_power
from temporal.cross_regime import audit_regimes_across_horizon
from temporal.walk_forward import run_temporal_walk_forward
from temporal.baselines import evaluate_temporal_baselines
from temporal.registry import Phase7ExperimentRegistry
from temporal.report import save_phase7_artifacts


def run_phase7_pipeline(
    symbols: List[str] = ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
    horizons: List[str] = ["5m", "15m", "30m", "1h", "4h"],
    data_dir: str = "data/historical",
    output_dir: str = "data/phase7_results",
    round_trip_friction_bps: float = 30.0,
    safety_margin_bps: float = 10.0,
) -> Dict[str, Any]:
    """Executes the complete Phase 7 Horizon Reassessment & Temporal Resolution Study."""
    print("=" * 80)
    print("PHASE 7: HORIZON REASSESSMENT & TEMPORAL RESOLUTION STUDY")
    print(f"Symbols: {symbols} | Horizons: {horizons}")
    print("=" * 80)

    loader = DatasetLoader(data_dir=data_dir)
    registry = Phase7ExperimentRegistry()

    dataset_metas = []
    primary_series_all: Dict[str, Dict[str, Any]] = {}
    secondary_series_all: Dict[str, Dict[str, Any]] = {}

    primary_signals = []
    secondary_signals = []
    primary_economics = []
    frequency_effects = []
    monotonicity_reports = []
    power_audits = []
    regime_audits = []
    walk_forward_folds = []
    baseline_metrics = []

    # 1. Process each asset
    for symbol in symbols:
        print(f"\n>>> Loading base 5m data for {symbol}...")
        df_5m, meta = loader.load_or_fetch_dataset(symbol=symbol, timeframe="5m")
        dataset_metas.append(meta.to_dict())

        # Primary Methodology (Prediction Horizon = Execution Horizon)
        print(f">>> Executing Primary Methodology for {symbol} across {horizons}...")
        prim_results = execute_primary_methodology(df_5m, symbol=symbol, timeframes=horizons)
        primary_series_all[symbol] = prim_results

        # Secondary Methodology (5m execution, forward holds)
        print(f">>> Executing Secondary Methodology for {symbol} across {horizons}...")
        sec_results = execute_secondary_methodology(df_5m, symbol=symbol, horizons=horizons)
        secondary_series_all[symbol] = sec_results

        symbol_prim_metrics = {}

        # Evaluate metrics for Primary Methodology
        for hz in horizons:
            series = prim_results[hz]
            df_eval = series.df_evaluated

            # Signal-level metrics
            sig_met = evaluate_signal_metrics(
                df=df_eval,
                symbol=symbol,
                timeframe=hz,
                horizon=hz,
                methodology="PRIMARY",
            )
            primary_signals.append(sig_met.to_dict())
            symbol_prim_metrics[hz] = sig_met

            # Economic analysis
            eco_rep = evaluate_horizon_economics(
                df=df_eval,
                symbol=symbol,
                timeframe=hz,
                horizon=hz,
                methodology="PRIMARY",
                fee_bps=10.0,
                slippage_bps=5.0,
                safety_margin_bps=safety_margin_bps,
            )
            primary_economics.append(eco_rep.to_dict())

            # Frequency effect
            freq_rep = audit_frequency_effect(
                df=df_eval,
                symbol=symbol,
                timeframe=hz,
                horizon=hz,
                round_trip_friction_bps=round_trip_friction_bps,
            )
            frequency_effects.append(freq_rep.to_dict())

            # Formal power audit
            target_bps_col = f"target_bps_{hz}"
            active_df = df_eval[df_eval["is_active"] & (~df_eval[target_bps_col].isna())]
            if len(active_df) > 0:
                trade_returns = active_df["decision_dir"].values * active_df[target_bps_col].values
            else:
                trade_returns = np.array([])
            pwr = audit_statistical_power(trade_returns, symbol=symbol, horizon=hz, assumed_alternative_bps=40.0)
            power_audits.append(pwr.to_dict())

            # Cross-regime evaluation
            reg_list = audit_regimes_across_horizon(df_eval, symbol=symbol, horizon=hz, round_trip_friction_bps=round_trip_friction_bps)
            for r in reg_list:
                regime_audits.append(r.to_dict())

            # Walk-forward 4-fold validation
            wf_list = run_temporal_walk_forward(df_eval, symbol=symbol, horizon=hz, n_folds=4, round_trip_friction_bps=round_trip_friction_bps)
            for w in wf_list:
                walk_forward_folds.append(w.to_dict())

            # Baselines
            bl_list = evaluate_temporal_baselines(df_eval, symbol=symbol, horizon=hz, round_trip_friction_bps=round_trip_friction_bps)
            for b in bl_list:
                baseline_metrics.append(b.to_dict())

            # Register experiment
            exp_id = f"EXP-P7-{symbol}-{hz}-PRIMARY"
            registry.register_experiment(
                experiment_id=exp_id,
                hypothesis=f"H7: Jev generates positive edge on {symbol} at {hz} resolution",
                asset=symbol,
                horizon=hz,
                execution_frequency=hz,
                dataset_hash=meta.sha256_hash,
                period=f"{meta.start_iso} to {meta.end_iso}",
                primary_metric="net_return_bps",
                success_criterion="net_return_bps > 0 and gross_bps >= 40.0",
                raw_p_value=pwr.p_value,
                observed_effect_bps=eco_rep.net_return_bps,
                result=eco_rep.classification,
            )

        # Monotonicity test for asset
        mono = evaluate_temporal_monotonicity(symbol_prim_metrics, symbol=symbol, methodology="PRIMARY")
        monotonicity_reports.append(mono.to_dict())

        # Evaluate secondary methodology signals
        for hz in horizons:
            series = sec_results[hz]
            sig_sec = evaluate_signal_metrics(
                df=series.df_evaluated,
                symbol=symbol,
                timeframe="5m",
                horizon=hz,
                methodology="SECONDARY",
            )
            secondary_signals.append(sig_sec.to_dict())

    # Finalize multiple testing correction
    print("\n>>> Applying Benjamini-Hochberg FDR correction across pre-registered hypotheses...")
    final_experiments = registry.finalize_multiple_testing_correction(alpha=0.05)

    # Determine master classification:
    # Requires at least one horizon to be SUPPORTED and survive FDR
    supported_count = sum(1 for e in final_experiments if e.result == "SUPPORTED")
    if supported_count > 0:
        master_verdict = "SUPPORTED"
    else:
        master_verdict = "NOT_SUPPORTED"

    master_data: Dict[str, Any] = {
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "master_classification": master_verdict,
        "frozen_config": registry.FROZEN_CONFIG,
        "configuration_hash": registry.configuration_hash,
        "symbols": symbols,
        "horizons": horizons,
        "datasets": dataset_metas,
        "primary_signals": primary_signals,
        "secondary_signals": secondary_signals,
        "primary_economics": primary_economics,
        "frequency_effects": frequency_effects,
        "monotonicity_reports": monotonicity_reports,
        "power_audits": power_audits,
        "regime_audits": regime_audits,
        "walk_forward_folds": walk_forward_folds,
        "baseline_metrics": baseline_metrics,
        "registry": [e.to_dict() for e in final_experiments],
    }

    # Save artifacts
    print(f"\n>>> Saving Phase 7 artifacts to {output_dir}...")
    paths = save_phase7_artifacts(master_data, output_dir=output_dir)
    print(f"Artifacts successfully generated:\n- JSON: {paths['json_path']}\n- CSV: {paths['csv_path']}\n- MD: {paths['md_path']}")

    print("\n" + "=" * 80)
    print(f"PHASE 7 EXECUTION COMPLETE — Master Classification: {master_verdict}")
    print("=" * 80)

    return master_data


def main():
    parser = argparse.ArgumentParser(description="Run Phase 7 Temporal Resolution Study")
    parser.add_argument("--symbols", default="BTCUSDT,ETHUSDT,SOLUSDT", help="Comma-separated symbols")
    parser.add_argument("--horizons", default="5m,15m,30m,1h,4h", help="Comma-separated horizons")
    parser.add_argument("--data-dir", default="data/historical", help="Historical data directory")
    parser.add_argument("--output-dir", default="data/phase7_results", help="Output artifact directory")
    args = parser.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    horizons = [h.strip() for h in args.horizons.split(",") if h.strip()]

    run_phase7_pipeline(
        symbols=symbols,
        horizons=horizons,
        data_dir=args.data_dir,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()
