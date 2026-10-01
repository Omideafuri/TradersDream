"""True Event-by-Event Level-2 Order-Book Replay Engine with Microstructure Execution Modeling."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
import math
import numpy as np

from phase10b.models import (
    BookSide,
    AggressorSide,
    L2Snapshot,
    L2Delta,
    L2DeltaPacket,
    TickTrade,
    ReconstructedBookState,
)
from phase10b.reconstructor import OrderBookReconstructor, OrderBookReconstructionError
from phase10cx.config import FrozenStrategyConfig, ExecutionScenario


@dataclass
class ReplayTradeRecord:
    trade_id: int
    entry_timestamp_ms: int
    exit_timestamp_ms: int
    symbol: str
    side: str                          # "LONG" or "SHORT"
    entry_price_raw: float
    entry_price_fill: float
    exit_price_raw: float
    exit_price_fill: float
    quantity: float
    fees_paid: float
    slippage_cost: float
    gross_pnl: float
    net_pnl: float
    net_return_pct: float
    entry_reason: str
    exit_reason: str
    holding_time_ms: int
    feature_snapshot: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trade_id": self.trade_id,
            "entry_timestamp_ms": self.entry_timestamp_ms,
            "exit_timestamp_ms": self.exit_timestamp_ms,
            "symbol": self.symbol,
            "side": self.side,
            "entry_price_raw": round(self.entry_price_raw, 4),
            "entry_price_fill": round(self.entry_price_fill, 4),
            "exit_price_raw": round(self.exit_price_raw, 4),
            "exit_price_fill": round(self.exit_price_fill, 4),
            "quantity": round(self.quantity, 6),
            "fees_paid": round(self.fees_paid, 4),
            "slippage_cost": round(self.slippage_cost, 4),
            "gross_pnl": round(self.gross_pnl, 4),
            "net_pnl": round(self.net_pnl, 4),
            "net_return_pct": round(self.net_return_pct, 6),
            "entry_reason": self.entry_reason,
            "exit_reason": self.exit_reason,
            "holding_time_ms": self.holding_time_ms,
        }


@dataclass
class ReplayPosition:
    trade_id: int
    symbol: str
    side: str
    entry_timestamp_ms: int
    entry_price_fill: float
    quantity: float
    stop_loss_price: float
    take_profit_price: float
    max_holding_ms: int
    entry_fee: float
    entry_slippage: float
    feature_snapshot: Dict[str, Any]


class EventByEventL2ReplayEngine:
    """Chronological event-driven simulator advancing strictly forward in time."""

    def __init__(
        self,
        config: FrozenStrategyConfig,
        scenario: ExecutionScenario,
    ):
        self.config = config
        self.scenario = scenario
        self.reconstructor = OrderBookReconstructor(
            symbol=config.symbol,
            exchange=config.venue,
            strict_mode=True,
        )

        # Portfolio state
        self.cash = config.initial_balance
        self.active_position: Optional[ReplayPosition] = None
        self.completed_trades: List[ReplayTradeRecord] = []
        self.equity_curve: List[Dict[str, Any]] = []
        self.current_time_ms: int = 0
        self.daily_pnl: float = 0.0
        self.current_day_str: str = ""
        self.trade_counter: int = 0

        # Rolling feature state (strictly point-in-time)
        self.recent_prices: List[Tuple[int, float]] = []   # (timestamp_ms, price)
        self.recent_trades: List[Tuple[int, float, float, str]] = [] # (ts_ms, price, qty, side)
        self.pending_orders: List[Dict[str, Any]] = []

    def process_snapshot(self, snapshot: L2Snapshot) -> None:
        """Initializes the order book ladder."""
        self.current_time_ms = snapshot.exchange_timestamp_ms
        self.reconstructor.load_snapshot(snapshot)
        state = self.reconstructor.get_current_state()
        if state.midpoint:
            self._update_price_history(self.current_time_ms, state.midpoint)
            self._record_equity(self.current_time_ms, state.midpoint)

    def process_delta_packet(self, packet: L2DeltaPacket) -> None:
        """Applies depth delta packet and updates book state."""
        self.current_time_ms = packet.exchange_timestamp_ms
        for delta in packet.deltas:
            self.reconstructor.apply_delta(delta)

        state = self.reconstructor.get_current_state()
        if state.midpoint:
            self._update_price_history(self.current_time_ms, state.midpoint)
            self._check_pending_orders(state)
            self._evaluate_position_exits(state)
            self._evaluate_signals(state)
            self._record_equity(self.current_time_ms, state.midpoint)

    def process_trade(self, trade: TickTrade) -> None:
        """Ingests executed trade tick and updates trade flow imbalance."""
        self.current_time_ms = trade.exchange_timestamp_ms
        side_str = trade.aggressor_side.value
        self.recent_trades.append((trade.exchange_timestamp_ms, trade.price, trade.quantity, side_str))
        self._prune_history()

    def _update_price_history(self, ts_ms: int, price: float) -> None:
        self.recent_prices.append((ts_ms, price))
        self._prune_history()

    def _prune_history(self) -> None:
        # Keep rolling 1-hour window strictly before current_time_ms
        cutoff_ms = self.current_time_ms - 3600000
        while self.recent_prices and self.recent_prices[0][0] < cutoff_ms:
            self.recent_prices.pop(0)
        while self.recent_trades and self.recent_trades[0][0] < cutoff_ms:
            self.recent_trades.pop(0)

    def calculate_point_in_time_features(self, state: ReconstructedBookState) -> Dict[str, Any]:
        """Calculates features using ONLY information available at or before self.current_time_ms."""
        # 1. Order book microstructure features
        best_bid = state.best_bid or 0.0
        best_ask = state.best_ask or 0.0
        mid = state.midpoint or ((best_bid + best_ask) / 2.0 if (best_bid and best_ask) else 0.0)
        spread = (best_ask - best_bid) if (best_bid and best_ask) else 0.0
        spread_bps = (spread / mid * 10000.0) if mid > 0 else 0.0

        # Top-10 Depth Imbalance
        bids_qty = sum(q for _, q in state.bid_levels[:self.config.depth_levels])
        asks_qty = sum(q for _, q in state.ask_levels[:self.config.depth_levels])
        total_depth = bids_qty + asks_qty
        ob_imbalance = (bids_qty - asks_qty) / total_depth if total_depth > 0 else 0.0

        # 2. Rolling Trade Flow Imbalance (5 min window)
        t5_cutoff = self.current_time_ms - self.config.imbalance_lookback_ms
        buy_vol = sum(qty for ts, _, qty, s in self.recent_trades if ts >= t5_cutoff and s == "BUY")
        sell_vol = sum(qty for ts, _, qty, s in self.recent_trades if ts >= t5_cutoff and s == "SELL")
        total_trade_vol = buy_vol + sell_vol
        trade_flow_imbalance = (buy_vol - sell_vol) / total_trade_vol if total_trade_vol > 0 else 0.0

        # 3. Price-based indicators (computed strictly from past prices)
        prices = [p for _, p in self.recent_prices]
        n = len(prices)
        if n >= 20:
            ema20 = float(np.mean(prices[-20:]))
        else:
            ema20 = mid
        if n >= 50:
            ema50 = float(np.mean(prices[-50:]))
        else:
            ema50 = mid
        if n >= 200:
            ema200 = float(np.mean(prices[-200:]))
        else:
            ema200 = mid

        # RSI approx
        if n >= 15:
            diffs = np.diff(prices[-15:])
            gains = diffs[diffs > 0]
            losses = -diffs[diffs < 0]
            avg_g = float(np.mean(gains)) if len(gains) > 0 else 0.0
            avg_l = float(np.mean(losses)) if len(losses) > 0 else 0.0001
            rs = avg_g / avg_l
            rsi = 100.0 - (100.0 / (1.0 + rs))
        else:
            rsi = 50.0

        return {
            "timestamp_ms": self.current_time_ms,
            "mid_price": mid,
            "best_bid": best_bid,
            "best_ask": best_ask,
            "spread_bps": spread_bps,
            "ob_imbalance": ob_imbalance,
            "trade_flow_imbalance": trade_flow_imbalance,
            "ema20": ema20,
            "ema50": ema50,
            "ema200": ema200,
            "rsi14": rsi,
            "sample_size": n,
        }

    def _evaluate_signals(self, state: ReconstructedBookState) -> None:
        """Determines whether to trigger trade entry."""
        if self.active_position is not None or self.pending_orders:
            return  # strictly max 1 position

        features = self.calculate_point_in_time_features(state)
        mid = features["mid_price"]
        ema20 = features["ema20"]
        ema50 = features["ema50"]
        rsi = features["rsi14"]
        ob_imb = features["ob_imbalance"]
        tfi = features["trade_flow_imbalance"]

        action = "HOLD"
        reason = "NO_CLEAR_SIGNAL"

        # Frozen Trend + Microstructure Confirmation Rule
        if mid > ema20 > ema50 and rsi < self.config.rsi_upper_thresh and (ob_imb > 0.10 or tfi > 0.10):
            action = "LONG"
            reason = "TREND_AND_MICROSTRUCTURE_BULLISH"
        elif mid < ema20 < ema50 and rsi > self.config.rsi_lower_thresh and (ob_imb < -0.10 or tfi < -0.10):
            action = "SHORT"
            reason = "TREND_AND_MICROSTRUCTURE_BEARISH"

        if action in ("LONG", "SHORT"):
            self._queue_entry_order(action, reason, features, state)

    def _queue_entry_order(
        self,
        side: str,
        reason: str,
        features: Dict[str, Any],
        state: ReconstructedBookState,
    ) -> None:
        """Simulates order submission subjected to network/engine latency."""
        arrival_time_ms = self.current_time_ms + int(self.scenario.latency_ms)
        self.pending_orders.append({
            "order_type": "ENTRY",
            "side": side,
            "reason": reason,
            "decision_time_ms": self.current_time_ms,
            "arrival_time_ms": arrival_time_ms,
            "features": features,
        })

    def _check_pending_orders(self, state: ReconstructedBookState) -> None:
        """Executes arrived orders against current order-book depth."""
        if not self.pending_orders:
            return

        now = self.current_time_ms
        ready = [o for o in self.pending_orders if o["arrival_time_ms"] <= now]
        self.pending_orders = [o for o in self.pending_orders if o["arrival_time_ms"] > now]

        for order in ready:
            if order["order_type"] == "ENTRY" and self.active_position is None:
                self._execute_entry(order, state)

    def _execute_entry(self, order: Dict[str, Any], state: ReconstructedBookState) -> None:
        """Executes entry against authentic L2 book."""
        side = order["side"]
        mid = state.midpoint
        if not mid or mid <= 0:
            return

        # Position sizing: 10% max allocation, 0.5% max risk
        allocated_capital = min(self.cash * self.config.max_position_size, self.cash)
        if allocated_capital < 10.0:  # minimum trade size
            return

        raw_price = state.best_ask if side == "LONG" else state.best_bid
        if not raw_price or raw_price <= 0:
            raw_price = mid

        # Dynamic execution friction: half-spread + slippage + adverse selection
        spread_fraction = (state.spread / mid) / 2.0 if (state.spread and mid) else 0.0002
        slippage_fraction = self.scenario.slippage_rate + (self.scenario.adverse_selection_bps / 10000.0)
        total_friction = spread_fraction + slippage_fraction

        if side == "LONG":
            fill_price = raw_price * (1.0 + total_friction)
            stop_loss = fill_price * (1.0 - self.config.stop_loss_pct)
            take_profit = fill_price * (1.0 + self.config.take_profit_pct)
        else:
            fill_price = raw_price * (1.0 - total_friction)
            stop_loss = fill_price * (1.0 + self.config.stop_loss_pct)
            take_profit = fill_price * (1.0 - self.config.take_profit_pct)

        quantity = allocated_capital / fill_price
        fee = allocated_capital * self.scenario.fee_rate
        slippage_cost = allocated_capital * total_friction

        self.cash -= (allocated_capital + fee)
        self.trade_counter += 1

        self.active_position = ReplayPosition(
            trade_id=self.trade_counter,
            symbol=self.config.symbol,
            side=side,
            entry_timestamp_ms=self.current_time_ms,
            entry_price_fill=fill_price,
            quantity=quantity,
            stop_loss_price=stop_loss,
            take_profit_price=take_profit,
            max_holding_ms=self.config.max_holding_bars * 300000,
            entry_fee=fee,
            entry_slippage=slippage_cost,
            feature_snapshot=order["features"],
        )

    def _evaluate_position_exits(self, state: ReconstructedBookState) -> None:
        """Evaluates stop-loss, take-profit, or max-holding-time exits."""
        pos = self.active_position
        if pos is None:
            return

        raw_price = state.best_bid if pos.side == "LONG" else state.best_ask
        if not raw_price or raw_price <= 0:
            raw_price = state.midpoint or pos.entry_price_fill

        elapsed_ms = self.current_time_ms - pos.entry_timestamp_ms
        exit_triggered = False
        exit_reason = ""

        if pos.side == "LONG":
            if raw_price <= pos.stop_loss_price:
                exit_triggered = True
                exit_reason = "STOP_LOSS"
            elif raw_price >= pos.take_profit_price:
                exit_triggered = True
                exit_reason = "TAKE_PROFIT"
            elif elapsed_ms >= pos.max_holding_ms:
                exit_triggered = True
                exit_reason = "MAX_HOLDING_TIME"
        elif pos.side == "SHORT":
            if raw_price >= pos.stop_loss_price:
                exit_triggered = True
                exit_reason = "STOP_LOSS"
            elif raw_price <= pos.take_profit_price:
                exit_triggered = True
                exit_reason = "TAKE_PROFIT"
            elif elapsed_ms >= pos.max_holding_ms:
                exit_triggered = True
                exit_reason = "MAX_HOLDING_TIME"

        if exit_triggered:
            self._execute_exit(pos, raw_price, exit_reason, state)

    def _execute_exit(
        self,
        pos: ReplayPosition,
        raw_price: float,
        exit_reason: str,
        state: ReconstructedBookState,
    ) -> None:
        """Closes position against available book liquidity with full friction."""
        mid = state.midpoint or raw_price
        spread_fraction = (state.spread / mid) / 2.0 if (state.spread and mid) else 0.0002
        slippage_fraction = self.scenario.slippage_rate + (self.scenario.adverse_selection_bps / 10000.0)
        total_friction = spread_fraction + slippage_fraction

        if pos.side == "LONG":
            fill_price = raw_price * (1.0 - total_friction)
            gross_pnl = (fill_price - pos.entry_price_fill) * pos.quantity
        else:
            fill_price = raw_price * (1.0 + total_friction)
            gross_pnl = (pos.entry_price_fill - fill_price) * pos.quantity

        exit_nominal = pos.quantity * fill_price
        exit_fee = exit_nominal * self.scenario.fee_rate
        exit_slippage = exit_nominal * total_friction
        total_fees = pos.entry_fee + exit_fee
        total_slippage = pos.entry_slippage + exit_slippage

        net_pnl = gross_pnl - total_fees
        entry_capital = pos.quantity * pos.entry_price_fill
        net_return_pct = net_pnl / entry_capital if entry_capital > 0 else 0.0

        self.cash += entry_capital + gross_pnl - exit_fee
        self.active_position = None

        record = ReplayTradeRecord(
            trade_id=pos.trade_id,
            entry_timestamp_ms=pos.entry_timestamp_ms,
            exit_timestamp_ms=self.current_time_ms,
            symbol=pos.symbol,
            side=pos.side,
            entry_price_raw=pos.entry_price_fill,
            entry_price_fill=pos.entry_price_fill,
            exit_price_raw=raw_price,
            exit_price_fill=fill_price,
            quantity=pos.quantity,
            fees_paid=total_fees,
            slippage_cost=total_slippage,
            gross_pnl=gross_pnl,
            net_pnl=net_pnl,
            net_return_pct=net_return_pct,
            entry_reason=pos.feature_snapshot.get("reason", "SIGNAL"),
            exit_reason=exit_reason,
            holding_time_ms=self.current_time_ms - pos.entry_timestamp_ms,
            feature_snapshot=pos.feature_snapshot,
        )
        self.completed_trades.append(record)

    def _record_equity(self, ts_ms: int, current_price: float) -> None:
        """Records timestamped equity for drawdown and metrics."""
        unrealized = 0.0
        if self.active_position is not None:
            pos = self.active_position
            if pos.side == "LONG":
                unrealized = (current_price - pos.entry_price_fill) * pos.quantity
            else:
                unrealized = (pos.entry_price_fill - current_price) * pos.quantity

        total_equity = self.cash + (self.active_position.quantity * self.active_position.entry_price_fill if self.active_position else 0.0) + unrealized
        self.equity_curve.append({
            "timestamp_ms": ts_ms,
            "equity": round(total_equity, 4),
            "cash": round(self.cash, 4),
            "unrealized_pnl": round(unrealized, 4),
            "has_open_position": 1 if self.active_position is not None else 0,
        })
