"""Command-line interface runner for Phase 2 historical backtesting.

Usage:
  python -m backtest.run
  python -m backtest.run --symbol BTCUSDT --timeframe 5m
"""

import argparse
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from typing import Optional

import pandas as pd

from backtest import __version__
from backtest.dataset import DatasetManager
from backtest.engine import BacktestEngine, BacktestConfig
from backtest.forward_returns import calculate_forward_returns, analyze_confidence_buckets
from backtest.walk_forward import run_walk_forward_evaluation
from backtest.analysis import run_threshold_sweep, run_benchmark_comparisons, generate_rule_based_decisions


async def async_run_backtest(args: argparse.Namespace) -> None:
    # 1. Check live Jev safety invariant
    if args.use_live_jev and not args.confirm_live_jev:
        print("ERROR: Safety Stop. Live Jev evaluation is disabled for historical backtesting.")
        print("To override explicitly, you must supply: --use-live-jev --confirm-live-jev")
        sys.exit(1)

    print("=" * 80)
    print(f"CRYPTO TRADING BOT — PHASE 2 HISTORICAL BACKTEST (v{__version__})")
    print("=" * 80)

    # Prepare directories
    results_dir = Path("data") / "backtest_results"
    results_dir.mkdir(parents=True, exist_ok=True)
    historical_dir = Path("data") / "historical"
    historical_dir.mkdir(parents=True, exist_ok=True)

    dataset_mgr = DatasetManager(historical_dir)

    # 2. Load or generate historical candles
    candle_file = historical_dir / f"{args.symbol}_{args.timeframe}_candles.csv"
    decision_file = historical_dir / f"{args.symbol}_{args.timeframe}_decisions.csv"

    if candle_file.exists():
        print(f"Loading cached historical candles from: {candle_file}")
        candles = pd.read_csv(candle_file)
    else:
        print(f"Generating deterministic synthetic historical dataset for {args.symbol} ({args.timeframe})...")
        candles = dataset_mgr.generate_synthetic_history(count=args.candle_count, seed=42)
        candles.to_csv(candle_file, index=False)

    enriched_candles = dataset_mgr.compute_causal_indicators(candles)

    # 3. Load or generate Jev decisions (offline replay)
    if decision_file.exists():
        print(f"Loading stored Jev decisions from: {decision_file}")
        decisions = dataset_mgr.load_decisions_csv(decision_file)
    else:
        print("Replaying deterministic Jev decisions across historical dataset...")
        decisions = dataset_mgr.generate_simulated_decisions(
            enriched_candles,
            symbol=args.symbol,
            timeframe=args.timeframe,
            seed=123,
        )
        dataset_mgr.save_decisions_csv(decisions, decision_file)

    print(f"Loaded {len(candles)} candles and {len(decisions)} decision points.")
    start_dt = datetime.fromtimestamp(candles["timestamp"].min() / 1000.0, tz=timezone.utc).isoformat()
    end_dt = datetime.fromtimestamp(candles["timestamp"].max() / 1000.0, tz=timezone.utc).isoformat()
    print(f"Historical Window: {start_dt} to {end_dt}")

    # 4. Configure Backtest Engine
    config = BacktestConfig(
        initial_balance=args.initial_balance,
        fee_rate=args.fee,
        slippage_rate=args.slippage,
        max_risk_per_trade=0.005,
        max_position_size=0.10,
        max_daily_loss=0.02,
        stop_loss_pct=args.stop_loss,
        take_profit_pct=args.take_profit,
        max_holding_period=args.max_holding,
        confidence_threshold=args.threshold,
    )

    print("\n--- SIMULATION PARAMETERS ---")
    print(f"Virtual Capital:       ${config.initial_balance:,.2f}")
    print(f"Trading Fee:           {config.fee_rate * 100:.2f}% (per execution)")
    print(f"Execution Slippage:    {config.slippage_rate * 100:.2f}% (per fill)")
    print(f"Risk Limits:           0.5% max risk / trade, 10% max position, 2% daily loss")
    print(f"Exit Parameters:       SL {config.stop_loss_pct*100:.1f}%, TP {config.take_profit_pct*100:.1f}%, Max Hold {config.max_holding_period} bars")
    print(f"Confidence Threshold:  {config.confidence_threshold:.2f}")

    # 5. Run Primary Backtest Replay
    engine = BacktestEngine(config)
    jev_result = engine.run(candles, decisions)
    metrics = jev_result.metrics

    print("\n" + "=" * 80)
    print("1. PRIMARY PERFORMANCE METRICS")
    print("=" * 80)
    print(f"Starting Balance:          ${metrics.starting_balance:,.2f}")
    print(f"Ending Balance:            ${metrics.ending_balance:,.2f}")
    print(f"Total Return:              {metrics.total_return_pct:+.2f}%")
    print(f"Total Trades:              {metrics.total_trades}")
    print(f"Winning / Losing Trades:   {metrics.winning_trades} / {metrics.losing_trades}")
    print(f"Win Rate:                  {metrics.win_rate_pct:.2f}%")
    print(f"Average Win:               ${metrics.average_win:,.2f}")
    print(f"Average Loss:              ${metrics.average_loss:,.2f}")
    print(f"Profit Factor:             {metrics.profit_factor:.2f}")
    print(f"Maximum Drawdown:          {metrics.max_drawdown_pct:.2f}%")
    print(f"Max Consecutive Losses:    {metrics.max_consecutive_losses}")
    print(f"Average Holding Time:      {metrics.average_holding_periods:.1f} bars ({metrics.average_holding_periods * 5:.0f} mins)")
    print(f"Total Fees Paid:           ${metrics.total_fees:,.2f}")
    print(f"Total Slippage Incurred:   ${metrics.total_slippage:,.2f}")

    # 6. Forward Returns & Confidence Bucketing
    print("\n" + "=" * 80)
    print("2. JEV PREDICTIVE POWER — CONFIDENCE BUCKETING ANALYSIS (15m Forward Returns)")
    print("=" * 80)
    fwd_df = calculate_forward_returns(candles, decisions)
    bucket_results = analyze_confidence_buckets(fwd_df, horizon="15m")

    print(f"{'Confidence Bucket':<18} | {'Count':<6} | {'Long':<5} | {'Short':<5} | {'Hold':<5} | {'Win Rate':<9} | {'Avg Ret (%)':<11} | {'Med Ret (%)':<11}")
    print("-" * 84)
    for b in bucket_results:
        print(f"{b.bucket_range:<18} | {b.total_count:<6} | {b.long_count:<5} | {b.short_count:<5} | {b.hold_count:<5} | {b.win_rate:>7.2f}% | {b.avg_return_pct:>10.3f}% | {b.median_return_pct:>10.3f}%")

    # 7. Confidence Threshold Sensitivity Analysis
    print("\n" + "=" * 80)
    print("3. CONFIDENCE THRESHOLD SENSITIVITY SWEEP (0.50 -> 0.80)")
    print("=" * 80)
    threshold_sweep = run_threshold_sweep(candles, decisions, config)
    print(f"{'Threshold':<10} | {'Trades':<7} | {'Win Rate':<9} | {'Profit Factor':<13} | {'Total Return':<13} | {'Max Drawdown':<12}")
    print("-" * 75)
    for row in threshold_sweep:
        print(f"{row.threshold:<10.2f} | {row.total_trades:<7} | {row.win_rate_pct:>7.2f}% | {row.profit_factor:>13.2f} | {row.total_return_pct:>12.2f}% | {row.max_drawdown_pct:>11.2f}%")

    # 8. Benchmark Comparisons
    print("\n" + "=" * 80)
    print("4. BENCHMARK COMPARISONS (SIDE-BY-SIDE)")
    print("=" * 80)
    rule_decisions = await generate_rule_based_decisions(enriched_candles, symbol=args.symbol, timeframe=args.timeframe)
    benchmarks = run_benchmark_comparisons(candles, jev_result, rule_decisions)
    print(f"{'Strategy Name':<28} | {'Return (%)':<11} | {'Trades':<7} | {'Win Rate':<9} | {'Profit Factor':<13} | {'Max Drawdown':<12}")
    print("-" * 88)
    for bm in benchmarks:
        print(f"{bm.strategy_name:<28} | {bm.total_return_pct:>10.2f}% | {bm.total_trades:<7} | {bm.win_rate_pct:>7.2f}% | {bm.profit_factor:>13.2f} | {bm.max_drawdown_pct:>11.2f}%")

    # 9. Walk-Forward Testing
    print("\n" + "=" * 80)
    print("5. CHRONOLOGICAL WALK-FORWARD VALIDATION (3 FOLDS)")
    print("=" * 80)
    wf_folds = run_walk_forward_evaluation(candles, decisions, config, folds=3, train_ratio=0.60)
    print(f"{'Fold':<5} | {'Train Return':<13} | {'Test Return':<12} | {'Train Trades':<12} | {'Test Trades':<11} | {'Test Win Rate':<13} | {'Test Max DD':<11}")
    print("-" * 88)
    for f in wf_folds:
        print(f"{f.fold:<5} | {f.train_return_pct:>12.2f}% | {f.test_return_pct:>11.2f}% | {f.train_trades:<12} | {f.test_trades:<11} | {f.test_win_rate_pct:>12.2f}% | {f.test_max_drawdown_pct:>10.2f}%")

    # 10. Save JSON Results and CSV Trade Log
    run_timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    json_path = results_dir / f"backtest_{args.symbol}_{run_timestamp}.json"
    trades_path = results_dir / f"trades_{args.symbol}_{run_timestamp}.csv"

    output_payload = {
        "reproducibility": {
            "software_version": __version__,
            "run_timestamp": datetime.now(timezone.utc).isoformat(),
            "symbol": args.symbol,
            "timeframe": args.timeframe,
            "period_start": start_dt,
            "period_end": end_dt,
            "candle_count": len(candles),
            "fee_rate": config.fee_rate,
            "slippage_rate": config.slippage_rate,
            "risk_parameters": {
                "max_risk_per_trade": config.max_risk_per_trade,
                "max_position_size": config.max_position_size,
                "max_daily_loss": config.max_daily_loss,
                "stop_loss_pct": config.stop_loss_pct,
                "take_profit_pct": config.take_profit_pct,
                "max_holding_period": config.max_holding_period,
            },
            "confidence_threshold": config.confidence_threshold,
        },
        "metrics": metrics.to_dict(),
        "confidence_buckets": [b.to_dict() for b in bucket_results],
        "threshold_sensitivity": [r.to_dict() for r in threshold_sweep],
        "benchmarks": [b.to_dict() for b in benchmarks],
        "walk_forward_folds": [f.to_dict() for f in wf_folds],
    }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(output_payload, f, indent=2)

    trades_df = pd.DataFrame([t.to_dict() for t in jev_result.trades])
    trades_df.to_csv(trades_path, index=False)

    print("\n" + "=" * 80)
    print("OUTPUT SAVED:")
    print(f"  JSON Results: {json_path}")
    print(f"  Trades Log:   {trades_path}")
    print("=" * 80)
    print("DISCLAIMER: Historical backtesting is an analytical evaluation of past data.")
    print("It does not guarantee future profitability or performance.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Crypto Trading Bot - Phase 2 Historical Backtester")
    parser.add_argument("--symbol", type=str, default="BTCUSDT", help="Trading pair symbol (default: BTCUSDT)")
    parser.add_argument("--timeframe", type=str, default="5m", help="Candle timeframe (default: 5m)")
    parser.add_argument("--initial-balance", type=float, default=10000.0, help="Starting paper balance (default: 10000.0)")
    parser.add_argument("--fee", type=float, default=0.001, help="Fee rate per fill (default: 0.001 / 0.1%)")
    parser.add_argument("--slippage", type=float, default=0.0005, help="Slippage rate per fill (default: 0.0005 / 0.05%)")
    parser.add_argument("--threshold", type=float, default=0.60, help="Jev confidence threshold (default: 0.60)")
    parser.add_argument("--stop-loss", type=float, default=0.015, help="Stop loss pct (default: 0.015 / 1.5%)")
    parser.add_argument("--take-profit", type=float, default=0.030, help="Take profit pct (default: 0.030 / 3.0%)")
    parser.add_argument("--max-holding", type=int, default=24, help="Max holding periods (default: 24 bars)")
    parser.add_argument("--candle-count", type=int, default=1500, help="Number of candles for synthetic test set (default: 1500)")
    parser.add_argument("--use-live-jev", action="store_true", help="Attempt live Jev API calls (default: False)")
    parser.add_argument("--confirm-live-jev", action="store_true", help="Explicit confirmation for live Jev API calls")

    args = parser.parse_args()
    asyncio.run(async_run_backtest(args))


if __name__ == "__main__":
    main()
