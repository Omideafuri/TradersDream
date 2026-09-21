"""Phase 3 Statistical Edge Validation & Robustness Testing CLI.

Usage:
    python -m validation.run --symbol BTCUSDT --timeframe 5m
"""

import argparse
import logging
from pathlib import Path
import platform
import sys
from datetime import datetime, timezone
from typing import Dict, Any, List

import numpy as np
import pandas as pd

from backtest.dataset import DatasetManager, HistoricalDecision
from backtest.engine import BacktestEngine, BacktestConfig, BacktestResult
from backtest.forward_returns import calculate_forward_returns
from validation.data_quality import DatasetIntegrityChecker
from validation.dataset_expansion import MultiAssetDataManager
from validation.forward_returns import evaluate_directional_forward_returns
from validation.calibration import compute_calibration_analysis
from validation.statistical import (
    calculate_expectancy,
    calculate_risk_adjusted_ratios,
    calculate_t_test_one_sample,
    apply_multiple_testing_corrections,
    SignificanceTestResult,
)
from validation.random_baseline import RandomBaselineEngine
from validation.ablation import run_ablation_study
from validation.cost_sensitivity import run_cost_sensitivity_analysis
from validation.regime import classify_causal_regimes, evaluate_regime_performance
from validation.holdout import partition_three_way, evaluate_sealed_holdout
from validation.report import (
    ValidationReportGenerator,
    get_git_commit_hash,
    compute_file_sha256,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("validation")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Phase 3 Statistical Edge Validation & Robustness Framework"
    )
    parser.add_argument("--symbol", type=str, default="BTCUSDT", help="Trading pair symbol")
    parser.add_argument("--timeframe", type=str, default="5m", help="Candle timeframe")
    parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=0.60,
        help="Jev decision confidence threshold",
    )
    parser.add_argument("--fee", type=float, default=0.0010, help="Exchange fee rate (0.0010 = 0.10%)")
    parser.add_argument(
        "--slippage", type=float, default=0.0005, help="Execution slippage rate (0.0005 = 0.05%)"
    )
    parser.add_argument("--seed", type=int, default=42, help="Deterministic random seed")
    parser.add_argument(
        "--bootstrap-samples", type=int, default=500, help="Number of bootstrap resamples"
    )
    parser.add_argument(
        "--null-simulations", type=int, default=50, help="Number of Monte Carlo null iterations"
    )
    parser.add_argument(
        "--data-dir", type=str, default="data/historical", help="Historical data directory"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/validation_results",
        help="Directory to save validation artifacts",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    logger.info("================================================================================")
    logger.info("PHASE 3 STATISTICAL EDGE VALIDATION & ROBUSTNESS TESTING")
    logger.info("================================================================================")
    logger.info(f"Symbol: {args.symbol} | Timeframe: {args.timeframe}")
    logger.info(f"Confidence Threshold: {args.confidence_threshold:.2f} | Fee: {args.fee*100:.2f}% | Slippage: {args.slippage*100:.2f}%")
    logger.info(f"Seed: {args.seed} | Bootstrap: {args.bootstrap_samples} | Null Sims: {args.null_simulations}")

    data_dir = Path(args.data_dir)
    output_dir = Path(args.output_dir)

    # 1. Load or Generate Dataset
    data_mgr = MultiAssetDataManager(data_dir)
    candles_path = data_mgr.get_dataset_path(args.symbol, args.timeframe)
    if not candles_path.exists():
        logger.info(f"Dataset for {args.symbol} not found. Generating standardized benchmark dataset...")
        candles_df = data_mgr.generate_standard_dataset(args.symbol, count=1500, seed=args.seed)
    else:
        logger.info(f"Loading existing candles from {candles_path}")
        candles_df = data_mgr.load_candles(args.symbol, args.timeframe)

    dataset_sha256 = compute_file_sha256(candles_path)

    # 2. Data Quality & Physical Integrity Check
    logger.info("Running Step 1: Data Quality & Physical Integrity Verification...")
    checker = DatasetIntegrityChecker(candles_df)
    integrity_report = checker.run_all_checks()
    if not integrity_report.is_valid:
        logger.warning(f"Data integrity warnings detected: {integrity_report.violations}")
    else:
        logger.info(f"Data integrity verified: {integrity_report.total_candles} candles, 0 violations.")

    # 3. Compute Causal Indicators & Historical Decisions
    logger.info("Enriching candles with causal technical indicators...")
    enriched_df = DatasetManager.compute_causal_indicators(candles_df)
    decisions = DatasetManager.generate_simulated_decisions(
        enriched_df, symbol=args.symbol, timeframe=args.timeframe, seed=args.seed
    )
    logger.info(f"Generated {len(decisions)} deterministic Jev decisions.")

    # 4. Directional Forward Returns Analysis
    logger.info("Running Step 2: Directional Forward Returns Analysis (5m, 15m, 30m, 1h, 4h)...")
    fwd_stats_by_horizon = evaluate_directional_forward_returns(
        candles_df, decisions, n_bootstrap=args.bootstrap_samples, seed=args.seed
    )
    df_fwd = calculate_forward_returns(candles_df, decisions)

    # Extract 15m summaries for high-level comparison
    hz15 = fwd_stats_by_horizon.get("15m", [])
    long_15m = next((h for h in hz15 if h.action == "LONG"), None)
    short_15m = next((h for h in hz15 if h.action == "SHORT"), None)
    mean_fwd_15m_long = long_15m.mean_return_pct if long_15m else 0.0
    mean_fwd_15m_short = short_15m.mean_return_pct if short_15m else 0.0

    # 5. Confidence Score Calibration
    logger.info("Running Step 3: Confidence Score Calibration & Reliability Analysis...")
    calib_report = compute_calibration_analysis(df_fwd, horizon="15m", min_sample_reliable=30)

    # 6. Primary Backtest Run (Base Configuration)
    logger.info("Running Step 4: Primary Backtest Execution...")
    base_config = BacktestConfig(
        initial_balance=10000.0,
        fee_rate=args.fee,
        slippage_rate=args.slippage,
        confidence_threshold=args.confidence_threshold,
    )
    engine = BacktestEngine(base_config)
    actual_result = engine.run(candles_df, decisions)
    logger.info(
        f"Primary Run Completed: Return={actual_result.metrics.total_return_pct:.2f}%, "
        f"Trades={actual_result.metrics.total_trades}, WinRate={actual_result.metrics.win_rate_pct:.1f}%, "
        f"PF={actual_result.metrics.profit_factor:.2f}, MaxDD={actual_result.metrics.max_drawdown_pct:.2f}%"
    )

    # 7. Statistical Significance & Hypothesis Testing
    logger.info("Running Step 5: Statistical Significance & Multiple-Testing Corrections...")
    net_pnls = [t.net_pnl for t in actual_result.trades]
    expectancy_data = calculate_expectancy(net_pnls)
    risk_ratios = calculate_risk_adjusted_ratios(actual_result.equity_curve)

    # Test 1: Return > 0
    t_ret, p_ret = calculate_t_test_one_sample(np.array(net_pnls) if net_pnls else np.array([]), null_mean=0.0)
    test_ret = SignificanceTestResult(
        test_name="Mean Trade PnL > $0",
        sample_size=len(net_pnls),
        observed_value=expectancy_data["expectancy"],
        null_value=0.0,
        t_statistic=t_ret,
        raw_p_value=p_ret,
        is_statistically_significant=p_ret < 0.05 and expectancy_data["expectancy"] > 0,
        interpretation="Reject null of zero/negative expectancy" if (p_ret < 0.05 and expectancy_data["expectancy"] > 0) else "Fail to reject null of zero expectancy",
    )

    # Test 2: Directional Accuracy > 50%
    wins_array = np.array([1.0 if p > 0 else 0.0 for p in net_pnls]) if net_pnls else np.array([])
    t_win, p_win = calculate_t_test_one_sample(wins_array, null_mean=0.50)
    test_win = SignificanceTestResult(
        test_name="Win Rate > 50%",
        sample_size=len(wins_array),
        observed_value=actual_result.metrics.win_rate_pct / 100.0,
        null_value=0.50,
        t_statistic=t_win,
        raw_p_value=p_win,
        is_statistically_significant=p_win < 0.05 and actual_result.metrics.win_rate_pct > 50.0,
        interpretation="Reject null of random 50% accuracy" if (p_win < 0.05 and actual_result.metrics.win_rate_pct > 50.0) else "Fail to reject null of 50% random chance",
    )

    p_vals = [test_ret.raw_p_value, test_win.raw_p_value]
    corr = apply_multiple_testing_corrections(p_vals, alpha=0.05)

    test_ret_dict = test_ret.to_dict()
    test_ret_dict["bonferroni_p"] = min(1.0, test_ret.raw_p_value * len(p_vals))
    test_ret_dict["fdr_significant"] = corr["fdr_significant"][0]

    test_win_dict = test_win.to_dict()
    test_win_dict["bonferroni_p"] = min(1.0, test_win.raw_p_value * len(p_vals))
    test_win_dict["fdr_significant"] = corr["fdr_significant"][1]

    corrected_tests = [test_ret_dict, test_win_dict]

    # 8. Random Baseline & Permutation Null Comparison
    logger.info(f"Running Step 6: Random Baseline Framework ({args.null_simulations} iterations)...")
    baseline_engine = RandomBaselineEngine(base_config, n_simulations=args.null_simulations, base_seed=args.seed)
    null_rand = baseline_engine.evaluate_null_distribution(
        candles_df, decisions, actual_result, baseline_type="random_direction"
    )
    null_perm = baseline_engine.evaluate_null_distribution(
        candles_df, decisions, actual_result, baseline_type="permuted_jev"
    )

    # 9. Feature Group Ablation Study
    logger.info("Running Step 7: Feature Group Ablation Study...")
    ablation_results = run_ablation_study(candles_df, enriched_df, base_config, base_seed=args.seed)

    # 10. Transaction Cost Sensitivity (Scenarios A through E)
    logger.info("Running Step 8: Transaction Cost Sensitivity Analysis...")
    cost_results = run_cost_sensitivity_analysis(candles_df, decisions, base_config)
    scenario_a = next((c for c in cost_results if c.scenario_id == "A"), None)
    breakeven_text = (
        f"Frictionless return is {scenario_a.total_return_pct:.2f}%. "
        f"Strategy requires fee < 0.03% to maintain non-negative return."
        if scenario_a and scenario_a.total_return_pct > 0
        else "Strategy does not achieve profitability even in frictionless Scenario A."
    )

    # 11. Causal Market Regime Segmentation
    logger.info("Running Step 9: Causal Market Regime Segmentation...")
    classified_candles = classify_causal_regimes(enriched_df)
    regime_results = evaluate_regime_performance(classified_candles, decisions, base_config)

    # 12. Holdout Partitioning & Evaluation (Dev 60%, Val 20%, Sealed Holdout 20%)
    logger.info("Running Step 10: Sealed Holdout Partitioning & Out-of-Sample Isolation...")
    dev_set, val_set, holdout_set, part_meta = partition_three_way(candles_df, decisions, 0.60, 0.20)
    holdout_eval = evaluate_sealed_holdout(dev_set, val_set, holdout_set, base_config)

    # 13. Failure Analysis
    logger.info("Running Step 11: Failure Analysis & Adverse Excursions...")
    sorted_trades = sorted(actual_result.trades, key=lambda t: t.net_pnl)
    top_losses = [
        {
            "entry_time": datetime.fromtimestamp(t.entry_time / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d %H:%M"),
            "exit_time": datetime.fromtimestamp(t.exit_time / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d %H:%M"),
            "direction": t.side,
            "size": t.quantity,
            "net_pnl": t.net_pnl,
            "return_pct": round((t.net_pnl / (t.entry_price_fill * t.quantity)) * 100.0, 2) if t.entry_price_fill * t.quantity > 0 else 0.0,
            "exit_reason": t.exit_reason,
        }
        for t in sorted_trades[:5]
    ]

    # Calculate max consecutive losses
    curr_loss_streak = 0
    max_loss_streak = 0
    for t in actual_result.trades:
        if t.net_pnl < 0:
            curr_loss_streak += 1
            max_loss_streak = max(max_loss_streak, curr_loss_streak)
        else:
            curr_loss_streak = 0

    # 14. Assemble Comprehensive Results Dictionary
    execution_ts = datetime.now(timezone.utc).isoformat()
    full_data = {
        "metadata": {
            "symbol": args.symbol,
            "timeframe": args.timeframe,
            "confidence_threshold": args.confidence_threshold,
            "fee_rate": args.fee,
            "slippage_rate": args.slippage,
            "execution_timestamp": execution_ts,
        },
        "reproducibility": {
            "git_commit": get_git_commit_hash(),
            "random_seed": args.seed,
            "bootstrap_samples": args.bootstrap_samples,
            "null_iterations": args.null_simulations,
            "dataset_sha256": dataset_sha256,
            "python_version": sys.version,
            "platform": platform.platform(),
            "pandas_version": pd.__version__,
            "numpy_version": np.__version__,
            "execution_timestamp": execution_ts,
        },
        "data_integrity": integrity_report.to_dict(),
        "primary_metrics": actual_result.metrics.to_dict(),
        "forward_returns": {
            "summary_15m_long": mean_fwd_15m_long,
            "summary_15m_short": mean_fwd_15m_short,
            "horizons": {
                hz: [s.to_dict() for s in stats]
                for hz, stats in fwd_stats_by_horizon.items()
            },
        },
        "calibration": calib_report.to_dict(),
        "statistical_significance": {
            "expectancy": expectancy_data,
            "risk_adjusted": risk_ratios,
            "t_test_returns": test_ret.to_dict(),
            "t_test_win_rate": test_win.to_dict(),
            "tests": corrected_tests,
        },
        "random_baselines": {
            "random_direction": null_rand.to_dict(),
            "permuted_jev": null_perm.to_dict(),
        },
        "ablation": [a.to_dict() for a in ablation_results],
        "cost_sensitivity": [c.to_dict() for c in cost_results],
        "cost_analysis": {
            "breakeven_summary": breakeven_text,
        },
        "regimes": [r.to_dict() for r in regime_results],
        "holdout": {
            "partitions": [p.to_dict() for p in part_meta],
            "evaluation": holdout_eval.to_dict(),
        },
        "failure_analysis": {
            "max_consecutive_losses": max_loss_streak,
            "top_losses": top_losses,
        },
    }

    # 15. Generate Artifacts (JSON, CSV, Markdown)
    logger.info("Generating reports and validation artifacts...")
    generator = ValidationReportGenerator(
        symbol=args.symbol,
        timeframe=args.timeframe,
        results_data=full_data,
        trades=actual_result.trades,
        forward_returns_df=df_fwd,
        dataset_path=candles_path,
        output_dir=output_dir,
    )
    artifacts = generator.generate_all_artifacts()

    logger.info("================================================================================")
    logger.info("VALIDATION COMPLETE - ARTIFACTS GENERATED:")
    logger.info(f"JSON:     {artifacts['json']}")
    logger.info(f"CSV:      {artifacts['csv']}")
    logger.info(f"Markdown: {artifacts['markdown']}")
    logger.info("================================================================================")

    # Print summary verdict table
    verdict = "REJECTED (NO STATISTICAL EDGE)" if (p_ret >= 0.05 or actual_result.metrics.total_return_pct <= 0) else "ACCEPTED (STATISTICAL EDGE PRESENT)"
    print("\n" + "=" * 80)
    print(f"PHASE 3 STATISTICAL VALIDATION SUMMARY: {args.symbol} ({args.timeframe})")
    print("=" * 80)
    print(f"Strategy Return:      {actual_result.metrics.total_return_pct:+.2f}%")
    print(f"Trades / Win Rate:    {actual_result.metrics.total_trades} trades | {actual_result.metrics.win_rate_pct:.1f}% win rate")
    print(f"Profit Factor / MaxDD:{actual_result.metrics.profit_factor:.2f} | {actual_result.metrics.max_drawdown_pct:.2f}%")
    print(f"Expectancy:           ${expectancy_data['expectancy']:.2f} per trade")
    print(f"Return t-stat / p-val:{t_ret:.3f} (p = {p_ret:.4f})")
    print(f"Random Baseline p-val:{null_rand.empirical_p_value_return:.4f}")
    print(f"ECE / Brier Score:    {calib_report.expected_calibration_error_pct:.2f}% ECE | {calib_report.brier_score:.4f} Brier")
    print(f"FINAL VERDICT:        {verdict}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
