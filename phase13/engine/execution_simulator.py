import sys
from datetime import datetime, timezone
from pathlib import Path
import math
from typing import Dict, Tuple, Optional, Any

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pandas as pd

from phase13.engine.state_manager import ForwardState, StateManager


class ExecutionSimulator:
    def __init__(
        self,
        state_mgr: StateManager,
        modeled_spread_bps: float = 4.0,
        modeled_slippage_bps: float = 1.0,
        commission_per_oz: float = 0.02,
        annual_swap_rate: float = 0.035,
        swap_cut_hour_utc: int = 22,
    ):
        self.sm = state_mgr
        self.modeled_spread_bps = modeled_spread_bps
        self.modeled_slippage_bps = modeled_slippage_bps
        self.commission_per_oz = commission_per_oz
        self.annual_swap_rate = annual_swap_rate
        self.swap_cut_hour_utc = swap_cut_hour_utc

    def queue_order(self, action: str, signal_time: str, reference_close: float):
        """
        Queue an order generated at bar t close for execution at bar t+1 open.
        Action must be 'BUY' or 'SELL'.
        """
        assert action in ("BUY", "SELL"), f"Invalid action: {action}"
        self.sm.state.pending_order = {
            "action": action,
            "signal_timestamp": signal_time,
            "reference_close": reference_close,
            "status": "QUEUED_FOR_NEXT_BAR_OPEN",
        }
        self.sm.log_event(
            "ORDER_QUEUED",
            "INFO",
            f"Queued {action} order generated at {signal_time} close (Ref: ${reference_close:.2f}) for execution at next bar open."
        )
        self.sm.save_state()

    def calculate_swap_days(self, entry_dt: pd.Timestamp, exit_dt: pd.Timestamp) -> Tuple[int, int, int]:
        """
        Calculate daily rollovers at 22:00 UTC cut.
        Wednesday 22:00 UTC rollover incurs triple swap.
        """
        cur = entry_dt.floor("D") + pd.Timedelta(hours=self.swap_cut_hour_utc)
        if cur <= entry_dt:
            cur += pd.Timedelta(days=1)
        standard_count = 0
        wednesday_count = 0
        while cur <= exit_dt:
            if cur.weekday() == 2:  # Wednesday
                wednesday_count += 1
            elif cur.weekday() in (0, 1, 3, 4):  # Mon, Tue, Thu, Fri
                standard_count += 1
            cur += pd.Timedelta(days=1)
        total_swap_days = standard_count + 3 * wednesday_count
        return total_swap_days, standard_count, wednesday_count

    def execute_pending_order(
        self,
        bar_open_time: str,
        bar_open_price: float,
        observed_bid: Optional[float] = None,
        observed_ask: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Executes a queued pending order at the open of bar t+1.
        Validates anti-lookahead assertion: signal_timestamp < execution_timestamp.
        """
        order = self.sm.state.pending_order
        if not order or order.get("status") != "QUEUED_FOR_NEXT_BAR_OPEN":
            return None

        signal_time = order["signal_timestamp"]
        action = order["action"]

        # Anti-lookahead assertion
        assert signal_time < bar_open_time, (
            f"INTEGRITY BREACH: Signal timestamp ({signal_time}) must be strictly earlier "
            f"than execution timestamp ({bar_open_time})!"
        )

        exec_details = {}

        if action == "BUY":
            assert self.sm.state.current_state == "FLAT", "Cannot BUY: State is already LONG"

            # Determine execution price
            if observed_ask and observed_ask > 0:
                fill_price = observed_ask + bar_open_price * (self.modeled_slippage_bps / 10000.0)
                price_source = "OBSERVED_ASK"
                spread_bps = ((observed_ask - (observed_bid or bar_open_price)) / bar_open_price) * 10000.0
            else:
                half_spread = bar_open_price * (self.modeled_spread_bps / 2.0 / 10000.0)
                slip = bar_open_price * (self.modeled_slippage_bps / 10000.0)
                fill_price = bar_open_price + half_spread + slip
                price_source = "MODELED_SPREAD"
                spread_bps = self.modeled_spread_bps

            # 100% sequential equity allocation (1.0x leverage)
            units = self.sm.state.cash_balance / fill_price
            spread_cost = (fill_price - bar_open_price) * units
            comm_cost = self.commission_per_oz * units

            self.sm.state.current_state = "LONG"
            self.sm.state.position_units = units
            self.sm.state.position_entry_price = fill_price
            self.sm.state.position_entry_time = bar_open_time
            self.sm.state.cash_balance = 0.0
            self.sm.state.current_equity = units * fill_price
            self.sm.state.total_spread_cost_usd += spread_cost
            self.sm.state.total_commission_usd += comm_cost

            exec_details = {
                "action": "BUY",
                "execution_timestamp": bar_open_time,
                "execution_price": round(fill_price, 4),
                "execution_reference_price": round(bar_open_price, 4),
                "execution_price_source": price_source,
                "position_units": round(units, 6),
                "spread_cost": round(spread_cost, 4),
                "slippage_cost": round(bar_open_price * (self.modeled_slippage_bps / 10000.0) * units, 4),
                "commission_cost": round(comm_cost, 4),
                "financing_cost": 0.0,
                "net_pnl": 0.0,
            }

        elif action == "SELL":
            assert self.sm.state.current_state == "LONG", "Cannot SELL: State is already FLAT"

            if observed_bid and observed_bid > 0:
                fill_price = observed_bid - bar_open_price * (self.modeled_slippage_bps / 10000.0)
                price_source = "OBSERVED_BID"
            else:
                half_spread = bar_open_price * (self.modeled_spread_bps / 2.0 / 10000.0)
                slip = bar_open_price * (self.modeled_slippage_bps / 10000.0)
                fill_price = bar_open_price - half_spread - slip
                price_source = "MODELED_SPREAD"

            units = self.sm.state.position_units
            entry_price = self.sm.state.position_entry_price
            entry_time = self.sm.state.position_entry_time

            # Gross trade PnL
            gross_pnl = (fill_price - entry_price) * units

            # Financing / Swap calculation
            dt_entry = pd.to_datetime(entry_time)
            dt_exit = pd.to_datetime(bar_open_time)
            swap_days, std_s, wed_s = self.calculate_swap_days(dt_entry, dt_exit)
            swap_cost = units * entry_price * (self.annual_swap_rate / 365.0) * swap_days
            comm_cost = self.commission_per_oz * units
            spread_cost = (bar_open_price - fill_price) * units

            net_trade_pnl = gross_pnl - swap_cost - comm_cost
            final_cash = (units * fill_price) - swap_cost - comm_cost

            self.sm.state.current_state = "FLAT"
            self.sm.state.position_units = 0.0
            self.sm.state.position_entry_price = 0.0
            self.sm.state.position_entry_time = ""
            self.sm.state.cash_balance = final_cash
            self.sm.state.current_equity = final_cash
            self.sm.state.total_trades_executed += 1
            if net_trade_pnl > 0:
                self.sm.state.winning_trades += 1
            else:
                self.sm.state.losing_trades += 1

            self.sm.state.gross_pnl_usd += gross_pnl
            self.sm.state.net_pnl_usd += net_trade_pnl
            self.sm.state.cumulative_pnl_usd += net_trade_pnl
            self.sm.state.total_swap_cost_usd += swap_cost
            self.sm.state.total_spread_cost_usd += spread_cost
            self.sm.state.total_commission_usd += comm_cost

            # Drawdown update
            if self.sm.state.current_equity > self.sm.state.peak_equity_usd:
                self.sm.state.peak_equity_usd = self.sm.state.current_equity
            dd = (self.sm.state.peak_equity_usd - self.sm.state.current_equity) / self.sm.state.peak_equity_usd * 100.0
            if dd > self.sm.state.max_drawdown_pct:
                self.sm.state.max_drawdown_pct = dd

            exec_details = {
                "action": "SELL",
                "execution_timestamp": bar_open_time,
                "execution_price": round(fill_price, 4),
                "execution_reference_price": round(bar_open_price, 4),
                "execution_price_source": price_source,
                "position_units": 0.0,
                "spread_cost": round(spread_cost, 4),
                "slippage_cost": round(bar_open_price * (self.modeled_slippage_bps / 10000.0) * units, 4),
                "commission_cost": round(comm_cost, 4),
                "financing_cost": round(swap_cost, 4),
                "net_pnl": round(net_trade_pnl, 4),
            }

        self.sm.state.pending_order = None
        self.sm.log_event(
            "ORDER_EXECUTED",
            "INFO",
            f"Executed {action} at {bar_open_time} (Fill: ${exec_details['execution_price']:.2f}, Source: {exec_details['execution_price_source']}). Equity: ${self.sm.state.current_equity:.2f}"
        )
        self.sm.save_state()
        return exec_details
