"""Master Evaluation Driver for Phase 10C.X Historical Blind Replay & Profitability Validation."""

import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import random
import shutil
import time
from typing import Dict, Any, List, Tuple, Optional
import numpy as np
import pandas as pd

from phase10c.adapter import TardisL2Adapter
from phase10b.reconstructor import OrderBookReconstructor
from phase10cx.config import FrozenStrategyConfig, ExecutionScenario, SCENARIOS
from phase10cx.l2_replay_engine import EventByEventL2ReplayEngine, ReplayTradeRecord
from phase10cx.leakage_audit import LeakageAuditor


class Phase10CXEvaluator:
    """Orchestrates L2 event replay, 30-day temporal replay, baseline benchmarks, and report generation."""

    def __init__(self, root_dir: Optional[Path] = None):
        self.root_dir = root_dir or Path(__file__).resolve().parent.parent
        self.config = FrozenStrategyConfig()
        self.l2_csv_path = self.root_dir / "phase10b4" / "data" / "sample_binance-us_incremental_book_L2_2024-03-01_BTCUSDT.csv"
        self.trades_csv_path = self.root_dir / "phase10b4" / "data" / "sample_binance-us_trades_2024-03-01_BTCUSDT.csv"
        self.candles_30d_path = self.root_dir / "data" / "phase9_data" / "BINANCE_US_BTCUSDT_5m.csv"

    def run_leakage_audit(self) -> Dict[str, Dict[str, Any]]:
        """Runs the 8 adversarial leakage tests."""
        auditor = LeakageAuditor(self.config)
        return auditor.run_all_tests()

    def run_l2_reconstruction_audit(self) -> Dict[str, Any]:
        """Audits order-book reconstruction on authentic historical L2 data."""
        snapshot, packets, stats = TardisL2Adapter.parse_incremental_book_l2_csv(self.l2_csv_path)
        reconstructor = OrderBookReconstructor(
            symbol=self.config.symbol,
            exchange=self.config.venue,
            strict_mode=True,
        )

        reconstructor.load_snapshot(snapshot)
        applied_deltas = 0
        crossed_events = 0
        bid_ask_spreads = []

        for p in packets:
            for d in p.deltas:
                state = reconstructor.apply_delta(d)
                applied_deltas += 1
                if state.is_crossed:
                    crossed_events += 1
                if state.spread:
                    bid_ask_spreads.append(state.spread)

        return {
            "snapshot_bids_count": len(snapshot.bids),
            "snapshot_asks_count": len(snapshot.asks),
            "total_packets": len(packets),
            "total_deltas_applied": applied_deltas,
            "discarded_pre_snapshot_deltas": stats.get("discarded_pre_snapshot_deltas", 0),
            "sequence_gaps_detected": len(reconstructor.sequence_gaps),
            "crossed_book_events": crossed_events,
            "min_spread": min(bid_ask_spreads) if bid_ask_spreads else 0.0,
            "avg_spread": float(np.mean(bid_ask_spreads)) if bid_ask_spreads else 0.0,
            "max_spread": max(bid_ask_spreads) if bid_ask_spreads else 0.0,
            "reconstruction_success_rate": 1.0 if len(reconstructor.sequence_gaps) == 0 and crossed_events == 0 else 0.0,
            "verdict": "PASS" if len(reconstructor.sequence_gaps) == 0 and crossed_events == 0 else "FAIL",
        }

    def run_l2_event_replay(self) -> Dict[str, Any]:
        """Executes the microsecond-accurate event-by-event L2 replay across Scenarios A, B, and C."""
        snapshot, packets, _ = TardisL2Adapter.parse_incremental_book_l2_csv(self.l2_csv_path)
        trades = TardisL2Adapter.parse_trades_csv(self.trades_csv_path)

        scenario_results = {}
        trade_ledgers = {}
        equity_curves = {}

        for key, scn in SCENARIOS.items():
            engine = EventByEventL2ReplayEngine(self.config, scn)
            engine.process_snapshot(snapshot)

            # Interleave packets and trades chronologically
            event_stream = []
            for p in packets:
                event_stream.append((p.exchange_timestamp_ms, "PACKET", p))
            for t in trades:
                event_stream.append((t.exchange_timestamp_ms, "TRADE", t))
            event_stream.sort(key=lambda x: x[0])

            for ts, ev_type, ev in event_stream:
                if ev_type == "PACKET":
                    engine.process_delta_packet(ev)
                else:
                    engine.process_trade(ev)

            # Close open position at end of stream if any
            if engine.active_position is not None:
                state = engine.reconstructor.get_current_state()
                engine._evaluate_position_exits(state)

            final_equity = engine.cash + (engine.active_position.quantity * engine.active_position.entry_price_fill if engine.active_position else 0.0)
            net_pnl = final_equity - self.config.initial_balance
            net_return = net_pnl / self.config.initial_balance

            scenario_results[key] = {
                "initial_capital": self.config.initial_balance,
                "final_equity": round(final_equity, 4),
                "net_pnl": round(net_pnl, 4),
                "net_return": round(net_return, 6),
                "trades_count": len(engine.completed_trades),
                "trades": engine.completed_trades,
            }
            trade_ledgers[key] = engine.completed_trades
            equity_curves[key] = engine.equity_curve

        return {
            "scenario_results": scenario_results,
            "trade_ledgers": trade_ledgers,
            "equity_curves": equity_curves,
        }

    def run_30d_temporal_replay(self) -> Dict[str, Any]:
        """Replays the frozen strategy across the 30-day historical window (8,640 5-minute bars)."""
        df_all = pd.read_csv(self.candles_30d_path)
        bars_30d = 30 * 24 * 12  # 8,640 bars
        df_30d = df_all.iloc[-bars_30d:].copy().reset_index(drop=True)

        # Calculate indicators chronologically strictly using trailing data
        df_30d["ema20"] = df_30d["close"].ewm(span=20, adjust=False).mean()
        df_30d["ema50"] = df_30d["close"].ewm(span=50, adjust=False).mean()
        df_30d["ema200"] = df_30d["close"].ewm(span=200, adjust=False).mean()
        
        # Wilder's RSI
        delta = df_30d["close"].diff()
        gain = delta.clip(lower=0.0).ewm(alpha=1.0/14.0, adjust=False).mean()
        loss = (-delta.clip(upper=0.0)).ewm(alpha=1.0/14.0, adjust=False).mean()
        rs = gain / loss.replace(0.0, np.nan)
        df_30d["rsi14"] = (100.0 - (100.0 / (1.0 + rs))).fillna(50.0)

        # Volume ratio (volume / 20-period rolling avg)
        df_30d["vol_ratio"] = df_30d["volume"] / df_30d["volume"].rolling(20, min_periods=1).mean()

        scenario_metrics = {}
        scenario_ledgers = {}
        scenario_curves = {}

        for scn_key, scn in SCENARIOS.items():
            cash = self.config.initial_balance
            active_pos: Optional[Dict[str, Any]] = None
            trades_list: List[Dict[str, Any]] = []
            curve: List[Dict[str, Any]] = []
            trade_id = 0

            for idx, row in df_30d.iterrows():
                ts = int(row["timestamp"])
                price = float(row["close"])
                ema20 = float(row["ema20"])
                ema50 = float(row["ema50"])
                rsi = float(row["rsi14"])
                vol_ratio = float(row["vol_ratio"])

                # 1. Check exits if active position
                if active_pos is not None:
                    holding_periods = idx - active_pos["entry_idx"]
                    exit_triggered = False
                    exit_reason = ""
                    raw_exit_price = price

                    if active_pos["side"] == "LONG":
                        if row["low"] <= active_pos["stop_loss"]:
                            exit_triggered = True
                            exit_reason = "STOP_LOSS"
                            raw_exit_price = active_pos["stop_loss"]
                        elif row["high"] >= active_pos["take_profit"]:
                            exit_triggered = True
                            exit_reason = "TAKE_PROFIT"
                            raw_exit_price = active_pos["take_profit"]
                        elif holding_periods >= self.config.max_holding_bars:
                            exit_triggered = True
                            exit_reason = "MAX_HOLDING_TIME"
                            raw_exit_price = price
                    elif active_pos["side"] == "SHORT":
                        if row["high"] >= active_pos["stop_loss"]:
                            exit_triggered = True
                            exit_reason = "STOP_LOSS"
                            raw_exit_price = active_pos["stop_loss"]
                        elif row["low"] <= active_pos["take_profit"]:
                            exit_triggered = True
                            exit_reason = "TAKE_PROFIT"
                            raw_exit_price = active_pos["take_profit"]
                        elif holding_periods >= self.config.max_holding_bars:
                            exit_triggered = True
                            exit_reason = "MAX_HOLDING_TIME"
                            raw_exit_price = price

                    if exit_triggered:
                        # Apply exit friction
                        fric = scn.slippage_rate + (scn.adverse_selection_bps / 10000.0)
                        fill_exit_price = raw_exit_price * (1.0 - fric) if active_pos["side"] == "LONG" else raw_exit_price * (1.0 + fric)
                        exit_fee = active_pos["qty"] * fill_exit_price * scn.fee_rate
                        
                        if active_pos["side"] == "LONG":
                            gross_pnl = (fill_exit_price - active_pos["fill_price"]) * active_pos["qty"]
                        else:
                            gross_pnl = (active_pos["fill_price"] - fill_exit_price) * active_pos["qty"]

                        net_pnl = gross_pnl - exit_fee
                        total_fees = active_pos["fee"] + exit_fee
                        total_slippage = (active_pos["nominal"] + (active_pos["qty"] * fill_exit_price)) * fric

                        cash += active_pos["nominal"] + net_pnl
                        trades_list.append({
                            "trade_id": active_pos["trade_id"],
                            "entry_timestamp_ms": active_pos["entry_time"],
                            "exit_timestamp_ms": ts,
                            "symbol": self.config.symbol,
                            "side": active_pos["side"],
                            "entry_price_raw": round(active_pos["raw_price"], 2),
                            "entry_price_fill": round(active_pos["fill_price"], 2),
                            "exit_price_raw": round(raw_exit_price, 2),
                            "exit_price_fill": round(fill_exit_price, 2),
                            "quantity": round(active_pos["qty"], 6),
                            "fees_paid": round(total_fees, 4),
                            "slippage_cost": round(total_slippage, 4),
                            "gross_pnl": round(gross_pnl, 4),
                            "net_pnl": round(net_pnl, 4),
                            "net_return_pct": round(net_pnl / active_pos["nominal"], 6),
                            "entry_reason": active_pos["entry_reason"],
                            "exit_reason": exit_reason,
                            "holding_periods": holding_periods,
                        })
                        active_pos = None

                # 2. Check entries if no position
                if active_pos is None:
                    signal = "HOLD"
                    entry_reason = "NO_CLEAR_SIGNAL"

                    if price > ema20 > ema50 and rsi < self.config.rsi_upper_thresh and vol_ratio > self.config.volume_ratio_thresh:
                        signal = "LONG"
                        entry_reason = "TREND_AND_MOMENTUM_BULLISH"
                    elif price < ema20 < ema50 and rsi > self.config.rsi_lower_thresh and vol_ratio > self.config.volume_ratio_thresh:
                        signal = "SHORT"
                        entry_reason = "TREND_AND_MOMENTUM_BEARISH"

                    if signal in ("LONG", "SHORT"):
                        allocated = cash * self.config.max_position_size
                        fric = scn.slippage_rate + (scn.adverse_selection_bps / 10000.0)
                        fill_entry = price * (1.0 + fric) if signal == "LONG" else price * (1.0 - fric)
                        entry_fee = allocated * scn.fee_rate
                        cash -= (allocated + entry_fee)
                        qty = allocated / fill_entry
                        trade_id += 1

                        sl = fill_entry * (1.0 - self.config.stop_loss_pct) if signal == "LONG" else fill_entry * (1.0 + self.config.stop_loss_pct)
                        tp = fill_entry * (1.0 + self.config.take_profit_pct) if signal == "LONG" else fill_entry * (1.0 - self.config.take_profit_pct)

                        active_pos = {
                            "trade_id": trade_id,
                            "side": signal,
                            "entry_time": ts,
                            "entry_idx": idx,
                            "raw_price": price,
                            "fill_price": fill_entry,
                            "nominal": allocated,
                            "qty": qty,
                            "fee": entry_fee,
                            "stop_loss": sl,
                            "take_profit": tp,
                            "entry_reason": entry_reason,
                        }

                # Record equity
                unrealized = 0.0
                if active_pos:
                    if active_pos["side"] == "LONG":
                        unrealized = (price - active_pos["fill_price"]) * active_pos["qty"]
                    else:
                        unrealized = (active_pos["fill_price"] - price) * active_pos["qty"]
                tot_eq = cash + (active_pos["nominal"] if active_pos else 0.0) + unrealized
                curve.append({"timestamp": ts, "equity": round(tot_eq, 4), "cash": round(cash, 4)})

            # Close final trade if any
            if active_pos:
                last_price = float(df_30d.iloc[-1]["close"])
                fric = scn.slippage_rate + (scn.adverse_selection_bps / 10000.0)
                fill_exit_price = last_price * (1.0 - fric) if active_pos["side"] == "LONG" else last_price * (1.0 + fric)
                exit_fee = active_pos["qty"] * fill_exit_price * scn.fee_rate
                gross_pnl = (fill_exit_price - active_pos["fill_price"]) * active_pos["qty"] if active_pos["side"] == "LONG" else (active_pos["fill_price"] - fill_exit_price) * active_pos["qty"]
                net_pnl = gross_pnl - exit_fee
                cash += active_pos["nominal"] + net_pnl
                trades_list.append({
                    "trade_id": active_pos["trade_id"],
                    "entry_timestamp_ms": active_pos["entry_time"],
                    "exit_timestamp_ms": int(df_30d.iloc[-1]["timestamp"]),
                    "symbol": self.config.symbol,
                    "side": active_pos["side"],
                    "entry_price_raw": round(active_pos["raw_price"], 2),
                    "entry_price_fill": round(active_pos["fill_price"], 2),
                    "exit_price_raw": round(last_price, 2),
                    "exit_price_fill": round(fill_exit_price, 2),
                    "quantity": round(active_pos["qty"], 6),
                    "fees_paid": round(active_pos["fee"] + exit_fee, 4),
                    "slippage_cost": round((active_pos["nominal"] + (active_pos["qty"] * fill_exit_price)) * fric, 4),
                    "gross_pnl": round(gross_pnl, 4),
                    "net_pnl": round(net_pnl, 4),
                    "net_return_pct": round(net_pnl / active_pos["nominal"], 6),
                    "entry_reason": active_pos["entry_reason"],
                    "exit_reason": "END_OF_SIMULATION",
                    "holding_periods": len(df_30d) - active_pos["entry_idx"],
                })

            scenario_ledgers[scn_key] = trades_list
            scenario_curves[scn_key] = curve

            # Calculate detailed metrics
            net_pnl_total = cash - self.config.initial_balance
            net_return_pct = net_pnl_total / self.config.initial_balance
            eq_vals = [c["equity"] for c in curve]
            running_max = np.maximum.accumulate(eq_vals)
            dd_series = (running_max - eq_vals) / running_max
            max_dd = float(np.max(dd_series)) if len(dd_series) > 0 else 0.0

            returns_pct = [t["net_return_pct"] for t in trades_list]
            win_trades = [r for r in returns_pct if r > 0]
            loss_trades = [r for r in returns_pct if r < 0]
            win_rate = len(win_trades) / len(returns_pct) if returns_pct else 0.0
            
            tot_win = sum(t["net_pnl"] for t in trades_list if t["net_pnl"] > 0)
            tot_loss = abs(sum(t["net_pnl"] for t in trades_list if t["net_pnl"] < 0))
            profit_factor = tot_win / tot_loss if tot_loss > 0 else (99.0 if tot_win > 0 else 0.0)
            expectancy = float(np.mean(returns_pct)) if returns_pct else 0.0

            # Sharpe & Sortino (per bar returns annualization)
            bar_rets = pd.Series(eq_vals).pct_change().dropna()
            std = bar_rets.std()
            sharpe = float((bar_rets.mean() / std) * math.sqrt(288 * 365)) if std > 0 else 0.0
            downside_std = bar_rets[bar_rets < 0].std()
            sortino = float((bar_rets.mean() / downside_std) * math.sqrt(288 * 365)) if downside_std > 0 else 0.0

            scenario_metrics[scn_key] = {
                "initial_capital": self.config.initial_balance,
                "final_equity": round(cash, 2),
                "net_pnl": round(net_pnl_total, 2),
                "net_return": round(net_return_pct, 4),
                "total_trades": len(trades_list),
                "winning_trades": len(win_trades),
                "losing_trades": len(loss_trades),
                "win_rate": round(win_rate, 4),
                "profit_factor": round(profit_factor, 2),
                "expectancy_pct": round(expectancy * 100.0, 4),
                "max_drawdown": round(max_dd, 4),
                "sharpe_ratio": round(sharpe, 2),
                "sortino_ratio": round(sortino, 2),
                "total_fees": round(sum(t["fees_paid"] for t in trades_list), 2),
                "total_slippage": round(sum(t["slippage_cost"] for t in trades_list), 2),
                "time_in_market_pct": round(sum(t["holding_periods"] for t in trades_list) / len(df_30d), 4),
            }

        # Temporal stability breakdown (Base Scenario)
        base_trades = scenario_ledgers["base"]
        t_start = df_30d["timestamp"].min()
        t_end = df_30d["timestamp"].max()
        duration = t_end - t_start
        period_ms = duration / 4.0

        temporal_results = []
        for p_idx in range(4):
            p_t0 = t_start + p_idx * period_ms
            p_t1 = p_t0 + period_ms
            p_trades = [t for t in base_trades if p_t0 <= t["entry_timestamp_ms"] < p_t1]
            p_pnl = sum(t["net_pnl"] for t in p_trades)
            temporal_results.append({
                "period": f"Days {p_idx * 7 + 1}–{(p_idx + 1) * 7 if p_idx < 3 else 30}",
                "trades": len(p_trades),
                "net_pnl": round(p_pnl, 2),
                "win_rate": round(sum(1 for t in p_trades if t["net_pnl"] > 0) / len(p_trades), 4) if p_trades else 0.0,
            })

        # Baseline comparisons
        # 1. Buy and Hold
        p_start = df_30d.iloc[0]["close"]
        p_end = df_30d.iloc[-1]["close"]
        bah_return = (p_end - p_start) / p_start
        bah_pnl = self.config.initial_balance * bah_return

        # 2. Flat / No trade
        flat_pnl = 0.0

        # 3. Random Entry Baseline (100 Monte Carlo iterations)
        random_pnls = []
        random.seed(42)
        for _ in range(100):
            r_cash = self.config.initial_balance
            for _ in range(len(base_trades)):
                r_ret = random.choice([-0.015, 0.030, -0.005, 0.005])
                r_cash += (r_cash * 0.10) * r_ret - (r_cash * 0.10 * 0.0015)
            random_pnls.append(r_cash - self.config.initial_balance)
        avg_random_pnl = float(np.mean(random_pnls))

        # 4. Cost Sensitivity Curve
        friction_levels_bps = [0, 5, 10, 15, 20, 25, 30, 40, 50, 75, 100]
        sensitivity_curve = []
        for fric_bps in friction_levels_bps:
            fric_rate = fric_bps / 10000.0
            test_pnl = sum(t["gross_pnl"] - (t["quantity"] * t["entry_price_fill"] * 2.0 * fric_rate) for t in base_trades)
            sensitivity_curve.append({
                "friction_bps": fric_bps,
                "net_pnl": round(test_pnl, 2),
            })

        return {
            "scenario_metrics": scenario_metrics,
            "temporal_results": temporal_results,
            "baselines": {
                "buy_and_hold_return_pct": round(bah_return * 100.0, 2),
                "buy_and_hold_pnl": round(bah_pnl, 2),
                "flat_pnl": 0.0,
                "random_entry_avg_pnl": round(avg_random_pnl, 2),
            },
            "sensitivity_curve": sensitivity_curve,
            "scenario_ledgers": scenario_ledgers,
            "scenario_curves": scenario_curves,
        }
