"""Paper trading engine for Crypto Trading Bot - Phase 1.

Simulates pure virtual execution:
- Virtual starting balance: $10,000
- Order entry and exit
- Accurate fee calculations (taker / maker)
- Realized and unrealized P&L
- Account balance and equity tracking
- Peak portfolio tracking and maximum drawdown calculation
- Strictly disconnected from real network exchanges.
"""

from dataclasses import dataclass, field
import time
from typing import Optional, List, Dict, Any


@dataclass
class Position:
    symbol: str
    side: str  # "LONG" or "SHORT"
    entry_price: float
    quantity: float
    entry_time: int
    entry_fee: float

    def unrealized_pnl(self, current_price: float) -> float:
        """Calculates unrealized P&L given current price."""
        if self.side == "LONG":
            return (current_price - self.entry_price) * self.quantity
        elif self.side == "SHORT":
            return (self.entry_price - current_price) * self.quantity
        return 0.0

    def to_dict(self, current_price: Optional[float] = None) -> Dict[str, Any]:
        pnl = self.unrealized_pnl(current_price) if current_price else 0.0
        return {
            "symbol": self.symbol,
            "side": self.side,
            "entry_price": round(self.entry_price, 2),
            "quantity": round(self.quantity, 6),
            "entry_time": self.entry_time,
            "entry_fee": round(self.entry_fee, 4),
            "unrealized_pnl": round(pnl, 2),
        }


@dataclass
class TradeRecord:
    symbol: str
    side: str
    entry_price: float
    exit_price: float
    quantity: float
    entry_time: int
    exit_time: int
    entry_fee: float
    exit_fee: float
    gross_pnl: float
    net_pnl: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "side": self.side,
            "entry_price": round(self.entry_price, 2),
            "exit_price": round(self.exit_price, 2),
            "quantity": round(self.quantity, 6),
            "entry_time": self.entry_time,
            "exit_time": self.exit_time,
            "fees_paid": round(self.entry_fee + self.exit_fee, 4),
            "gross_pnl": round(self.gross_pnl, 2),
            "net_pnl": round(self.net_pnl, 2),
        }


class PaperTradingEngine:
    """Local, paper-trading-only portfolio and position manager."""

    def __init__(
        self,
        initial_balance: float = 10000.0,
        taker_fee: float = 0.00075,  # 0.075% taker fee
        maker_fee: float = 0.0002,   # 0.02% maker fee
    ):
        self.initial_balance = float(initial_balance)
        self.cash_balance = float(initial_balance)
        self.taker_fee = taker_fee
        self.maker_fee = maker_fee

        self.current_position: Optional[Position] = None
        self.realized_pnl: float = 0.0
        self.total_fees_paid: float = 0.0
        self.trade_history: List[TradeRecord] = []

        self.last_price: float = 0.0
        self.peak_portfolio_value: float = float(initial_balance)
        self.max_drawdown_pct: float = 0.0

    @property
    def has_open_position(self) -> bool:
        return self.current_position is not None

    def get_portfolio_value(self, current_price: Optional[float] = None) -> float:
        """Calculates total portfolio value (cash + position value + unrealized PnL)."""
        price = current_price or self.last_price
        if self.current_position is None or price <= 0:
            return self.cash_balance

        unrealized = self.current_position.unrealized_pnl(price)
        # Position capital + unrealized profit/loss
        position_cost = self.current_position.entry_price * self.current_position.quantity
        return self.cash_balance + position_cost + unrealized

    def update_market_price(self, current_price: float) -> None:
        """Updates internal price marker and refreshes drawdown metrics."""
        self.last_price = current_price
        pv = self.get_portfolio_value(current_price)

        if pv > self.peak_portfolio_value:
            self.peak_portfolio_value = pv

        drawdown = (self.peak_portfolio_value - pv) / self.peak_portfolio_value * 100.0
        if drawdown > self.max_drawdown_pct:
            self.max_drawdown_pct = drawdown

    def execute_buy(
        self,
        symbol: str,
        price: float,
        quantity: float,
        timestamp: Optional[int] = None,
    ) -> Position:
        """Executes a virtual BUY (Long) order."""
        if self.has_open_position:
            raise RuntimeError("Cannot open position: maximum one position allowed.")

        notional = price * quantity
        fee = notional * self.taker_fee
        total_cost = notional + fee

        if total_cost > self.cash_balance:
            raise ValueError(
                f"Insufficient funds: required ${total_cost:.2f}, available ${self.cash_balance:.2f}"
            )

        self.cash_balance -= total_cost
        self.total_fees_paid += fee

        now_ts = timestamp or int(time.time() * 1000)
        self.current_position = Position(
            symbol=symbol,
            side="LONG",
            entry_price=price,
            quantity=quantity,
            entry_time=now_ts,
            entry_fee=fee,
        )

        self.update_market_price(price)
        return self.current_position

    def execute_sell(
        self,
        price: float,
        timestamp: Optional[int] = None,
    ) -> TradeRecord:
        """Closes an open position (Sell)."""
        if not self.has_open_position:
            raise RuntimeError("Cannot execute sell: no open position exists.")

        pos = self.current_position
        notional = price * pos.quantity
        exit_fee = notional * self.taker_fee

        if pos.side == "LONG":
            gross_pnl = (price - pos.entry_price) * pos.quantity
            returned_capital = (pos.entry_price * pos.quantity) + gross_pnl
        else:
            # Short simulation
            gross_pnl = (pos.entry_price - price) * pos.quantity
            returned_capital = (pos.entry_price * pos.quantity) + gross_pnl

        net_pnl = gross_pnl - pos.entry_fee - exit_fee
        self.cash_balance += (returned_capital - exit_fee)
        self.realized_pnl += net_pnl
        self.total_fees_paid += exit_fee

        now_ts = timestamp or int(time.time() * 1000)
        record = TradeRecord(
            symbol=pos.symbol,
            side=pos.side,
            entry_price=pos.entry_price,
            exit_price=price,
            quantity=pos.quantity,
            entry_time=pos.entry_time,
            exit_time=now_ts,
            entry_fee=pos.entry_fee,
            exit_fee=exit_fee,
            gross_pnl=gross_pnl,
            net_pnl=net_pnl,
        )

        self.trade_history.append(record)
        self.current_position = None
        self.update_market_price(price)
        return record

    def get_snapshot(self, current_price: Optional[float] = None) -> Dict[str, Any]:
        """Returns structured paper portfolio snapshot."""
        price = current_price or self.last_price
        pv = self.get_portfolio_value(price)
        unrealized = self.current_position.unrealized_pnl(price) if self.current_position and price > 0 else 0.0

        return {
            "initial_balance": self.initial_balance,
            "cash_balance": round(self.cash_balance, 2),
            "portfolio_value": round(pv, 2),
            "realized_pnl": round(self.realized_pnl, 2),
            "unrealized_pnl": round(unrealized, 2),
            "total_fees_paid": round(self.total_fees_paid, 4),
            "max_drawdown_pct": round(self.max_drawdown_pct, 4),
            "has_open_position": self.has_open_position,
            "position": self.current_position.to_dict(price) if self.current_position else None,
        }
