"""Event-driven candle replay Backtest Engine for Crypto Trading Bot - Phase 2.

Simulates virtual execution with:
- Strict Risk Engine invariants (0.5% risk, 2% daily loss, 10% max position, 1 open position, no leverage)
- Configurable execution fees (default 0.1%)
- Configurable execution slippage (default 0.05%)
- Configurable deterministic exits (Stop Loss, Take Profit, Max Holding Period)
- Accurate equity curve and drawdown tracking
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import pandas as pd

from backtest.dataset import HistoricalDecision
from backtest.metrics import BacktestTrade, PerformanceMetrics, compute_metrics


@dataclass
class BacktestConfig:
    initial_balance: float = 10000.0
    fee_rate: float = 0.001          # 0.1%
    slippage_rate: float = 0.0005     # 0.05%
    max_risk_per_trade: float = 0.005 # 0.5%
    max_position_size: float = 0.10   # 10.0%
    max_daily_loss: float = 0.02      # 2.0%
    stop_loss_pct: float = 0.015      # 1.5%
    take_profit_pct: float = 0.030    # 3.0%
    max_holding_period: int = 24      # 24 candles (2 hours on 5m)
    confidence_threshold: float = 0.60


@dataclass
class ActivePosition:
    trade_id: int
    symbol: str
    side: str  # LONG or SHORT
    entry_time: int
    entry_price_raw: float
    entry_price_fill: float
    quantity: float
    entry_fee: float
    entry_slippage: float
    stop_loss_price: float
    take_profit_price: float
    holding_periods: int = 0

    def unrealized_pnl(self, current_price: float) -> float:
        if self.side == "LONG":
            return (current_price - self.entry_price_fill) * self.quantity
        elif self.side == "SHORT":
            return (self.entry_price_fill - current_price) * self.quantity
        return 0.0


@dataclass
class BacktestResult:
    metrics: PerformanceMetrics
    trades: List[BacktestTrade]
    equity_curve: List[float]
    timestamps: List[int]
    config: BacktestConfig

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metrics": self.metrics.to_dict(),
            "trade_count": len(self.trades),
            "config": {
                "initial_balance": self.config.initial_balance,
                "fee_rate": self.config.fee_rate,
                "slippage_rate": self.config.slippage_rate,
                "max_risk_per_trade": self.config.max_risk_per_trade,
                "max_position_size": self.config.max_position_size,
                "max_daily_loss": self.config.max_daily_loss,
                "stop_loss_pct": self.config.stop_loss_pct,
                "take_profit_pct": self.config.take_profit_pct,
                "max_holding_period": self.config.max_holding_period,
                "confidence_threshold": self.config.confidence_threshold,
            },
        }


class BacktestEngine:
    """Deterministic candle replay backtester with embedded risk controls."""

    def __init__(self, config: Optional[BacktestConfig] = None):
        self.config = config or BacktestConfig()

    def run(
        self,
        candles_df: pd.DataFrame,
        decisions: List[HistoricalDecision],
    ) -> BacktestResult:
        """Executes chronological replay of candles and decisions."""
        candles = candles_df.sort_values("timestamp").reset_index(drop=True)
        decision_map = {d.timestamp: d for d in decisions}

        cash = self.config.initial_balance
        position: Optional[ActivePosition] = None
        trades: List[BacktestTrade] = []
        equity_curve: List[float] = []
        timestamps: List[int] = []

        trade_counter = 0
        current_day: Optional[str] = None
        day_start_equity = cash
        day_realized_pnl = 0.0

        for idx, row in candles.iterrows():
            ts = int(row["timestamp"])
            open_p = float(row["open"])
            high_p = float(row["high"])
            low_p = float(row["low"])
            close_p = float(row["close"])

            # 1. Daily loss tracking (UTC day boundary)
            dt = datetime.fromtimestamp(ts / 1000.0, tz=timezone.utc)
            day_str = dt.strftime("%Y-%m-%d")
            if current_day != day_str:
                current_day = day_str
                day_start_equity = cash + (position.unrealized_pnl(close_p) if position else 0.0)
                day_realized_pnl = 0.0

            # 2. Manage open position exits if active
            if position is not None:
                position.holding_periods += 1
                exit_triggered = False
                exit_price_raw = close_p
                exit_reason = "END_OF_DATA"

                # Check Stop Loss & Take Profit against candle extremes
                if position.side == "LONG":
                    if self.config.stop_loss_pct > 0 and low_p <= position.stop_loss_price:
                        exit_triggered = True
                        exit_price_raw = position.stop_loss_price
                        exit_reason = "STOP_LOSS"
                    elif self.config.take_profit_pct > 0 and high_p >= position.take_profit_price:
                        exit_triggered = True
                        exit_price_raw = position.take_profit_price
                        exit_reason = "TAKE_PROFIT"
                    elif position.holding_periods >= self.config.max_holding_period:
                        exit_triggered = True
                        exit_price_raw = close_p
                        exit_reason = "MAX_HOLD"
                elif position.side == "SHORT":
                    if self.config.stop_loss_pct > 0 and high_p >= position.stop_loss_price:
                        exit_triggered = True
                        exit_price_raw = position.stop_loss_price
                        exit_reason = "STOP_LOSS"
                    elif self.config.take_profit_pct > 0 and low_p <= position.take_profit_price:
                        exit_triggered = True
                        exit_price_raw = position.take_profit_price
                        exit_reason = "TAKE_PROFIT"
                    elif position.holding_periods >= self.config.max_holding_period:
                        exit_triggered = True
                        exit_price_raw = close_p
                        exit_reason = "MAX_HOLD"

                # Check signal reversal exit
                if not exit_triggered and ts in decision_map:
                    dec = decision_map[ts]
                    if dec.confidence >= self.config.confidence_threshold:
                        if position.side == "LONG" and dec.action == "SHORT":
                            exit_triggered = True
                            exit_price_raw = close_p
                            exit_reason = "SIGNAL_REVERSAL"
                        elif position.side == "SHORT" and dec.action == "LONG":
                            exit_triggered = True
                            exit_price_raw = close_p
                            exit_reason = "SIGNAL_REVERSAL"

                # Execute exit if triggered
                if exit_triggered:
                    # Apply slippage on exit
                    if position.side == "LONG":
                        exit_fill = exit_price_raw * (1.0 - self.config.slippage_rate)
                        exit_slippage = (exit_price_raw - exit_fill) * position.quantity
                        gross_pnl = (exit_fill - position.entry_price_fill) * position.quantity
                    else:
                        exit_fill = exit_price_raw * (1.0 + self.config.slippage_rate)
                        exit_slippage = (exit_fill - exit_price_raw) * position.quantity
                        gross_pnl = (position.entry_price_fill - exit_fill) * position.quantity

                    exit_fee = exit_fill * position.quantity * self.config.fee_rate
                    net_pnl = gross_pnl - position.entry_fee - exit_fee
                    total_slip = position.entry_slippage + exit_slippage

                    # Capital return: returns exact capital deployed at fill price
                    position_capital = position.entry_price_fill * position.quantity
                    cash += (position_capital + gross_pnl - exit_fee)
                    day_realized_pnl += net_pnl

                    trades.append(
                        BacktestTrade(
                            trade_id=position.trade_id,
                            symbol=position.symbol,
                            side=position.side,
                            entry_time=position.entry_time,
                            exit_time=ts,
                            entry_price_raw=position.entry_price_raw,
                            entry_price_fill=position.entry_price_fill,
                            exit_price_raw=exit_price_raw,
                            exit_price_fill=exit_fill,
                            quantity=position.quantity,
                            gross_pnl=gross_pnl,
                            net_pnl=net_pnl,
                            entry_fee=position.entry_fee,
                            exit_fee=exit_fee,
                            slippage_cost=total_slip,
                            exit_reason=exit_reason,
                            holding_periods=position.holding_periods,
                        )
                    )
                    position = None

            # 3. Evaluate New Entry Signals (if no open position)
            current_portfolio_val = cash
            if position is None and ts in decision_map:
                decision = decision_map[ts]

                # Check Daily Loss Limit (2.0%)
                max_allowed_daily_loss = day_start_equity * self.config.max_daily_loss
                daily_loss_halt = (day_realized_pnl < 0 and abs(day_realized_pnl) >= max_allowed_daily_loss)

                # Check Confidence Gate
                confident = (decision.confidence >= self.config.confidence_threshold)

                if confident and not daily_loss_halt and decision.action in ("LONG", "SHORT"):
                    # Position Sizing: strictly cap at 10% of portfolio
                    max_notional_cap = current_portfolio_val * self.config.max_position_size
                    # Risk-based sizing: 0.5% risk / stop_loss_pct (or cap if no SL)
                    if self.config.stop_loss_pct > 0:
                        risk_notional = (current_portfolio_val * self.config.max_risk_per_trade) / self.config.stop_loss_pct
                    else:
                        risk_notional = max_notional_cap
                    target_notional = min(max_notional_cap, risk_notional, cash)

                    if target_notional > 50.0 and close_p > 0:
                        # Apply slippage on entry
                        if decision.action == "LONG":
                            fill_price = close_p * (1.0 + self.config.slippage_rate)
                            entry_slip = (fill_price - close_p) * (target_notional / fill_price)
                            sl_price = fill_price * (1.0 - self.config.stop_loss_pct) if self.config.stop_loss_pct > 0 else 0.0
                            tp_price = fill_price * (1.0 + self.config.take_profit_pct) if self.config.take_profit_pct > 0 else float("inf")
                        else:
                            fill_price = close_p * (1.0 - self.config.slippage_rate)
                            entry_slip = (close_p - fill_price) * (target_notional / fill_price)
                            sl_price = fill_price * (1.0 + self.config.stop_loss_pct) if self.config.stop_loss_pct > 0 else float("inf")
                            tp_price = fill_price * (1.0 - self.config.take_profit_pct) if self.config.take_profit_pct > 0 else 0.0

                        qty = target_notional / fill_price
                        entry_fee = target_notional * self.config.fee_rate
                        total_outflow = target_notional + entry_fee

                        if total_outflow <= cash:
                            cash -= total_outflow
                            trade_counter += 1
                            position = ActivePosition(
                                trade_id=trade_counter,
                                symbol=decision.symbol,
                                side=decision.action,
                                entry_time=ts,
                                entry_price_raw=close_p,
                                entry_price_fill=fill_price,
                                quantity=qty,
                                entry_fee=entry_fee,
                                entry_slippage=entry_slip,
                                stop_loss_price=sl_price,
                                take_profit_price=tp_price,
                                holding_periods=0,
                            )

            # 4. Record Equity Snapshot
            if position is not None:
                pos_cost = position.entry_price_fill * position.quantity
                unrealized = position.unrealized_pnl(close_p)
                equity = cash + pos_cost + unrealized
            else:
                equity = cash

            equity_curve.append(equity)
            timestamps.append(ts)

        # Close any open position at end of data
        if position is not None:
            last_p = float(candles.iloc[-1]["close"])
            if position.side == "LONG":
                exit_fill = last_p * (1.0 - self.config.slippage_rate)
                exit_slippage = (last_p - exit_fill) * position.quantity
                gross_pnl = (exit_fill - position.entry_price_fill) * position.quantity
            else:
                exit_fill = last_p * (1.0 + self.config.slippage_rate)
                exit_slippage = (exit_fill - last_p) * position.quantity
                gross_pnl = (position.entry_price_fill - exit_fill) * position.quantity

            exit_fee = exit_fill * position.quantity * self.config.fee_rate
            net_pnl = gross_pnl - position.entry_fee - exit_fee
            total_slip = position.entry_slippage + exit_slippage
            cash += (position.entry_price_fill * position.quantity + gross_pnl - exit_fee)
            if equity_curve:
                equity_curve[-1] = cash
            trades.append(
                BacktestTrade(
                    trade_id=position.trade_id,
                    symbol=position.symbol,
                    side=position.side,
                    entry_time=position.entry_time,
                    exit_time=int(candles.iloc[-1]["timestamp"]),
                    entry_price_raw=position.entry_price_raw,
                    entry_price_fill=position.entry_price_fill,
                    exit_price_raw=last_p,
                    exit_price_fill=exit_fill,
                    quantity=position.quantity,
                    gross_pnl=gross_pnl,
                    net_pnl=net_pnl,
                    entry_fee=position.entry_fee,
                    exit_fee=exit_fee,
                    slippage_cost=total_slip,
                    exit_reason="END_OF_DATA",
                    holding_periods=position.holding_periods,
                )
            )

        metrics = compute_metrics(self.config.initial_balance, equity_curve, trades)
        return BacktestResult(
            metrics=metrics,
            trades=trades,
            equity_curve=equity_curve,
            timestamps=timestamps,
            config=self.config,
        )
