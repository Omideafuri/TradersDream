"""Performance metrics computation for historical backtests."""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import numpy as np


@dataclass
class BacktestTrade:
    trade_id: int
    symbol: str
    side: str  # LONG or SHORT
    entry_time: int
    exit_time: int
    entry_price_raw: float
    entry_price_fill: float
    exit_price_raw: float
    exit_price_fill: float
    quantity: float
    gross_pnl: float
    net_pnl: float
    entry_fee: float
    exit_fee: float
    slippage_cost: float
    exit_reason: str  # STOP_LOSS, TAKE_PROFIT, MAX_HOLD, SIGNAL_REVERSAL, END_OF_DATA
    holding_periods: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trade_id": self.trade_id,
            "symbol": self.symbol,
            "side": self.side,
            "entry_time": self.entry_time,
            "exit_time": self.exit_time,
            "entry_price_raw": round(self.entry_price_raw, 2),
            "entry_price_fill": round(self.entry_price_fill, 2),
            "exit_price_raw": round(self.exit_price_raw, 2),
            "exit_price_fill": round(self.exit_price_fill, 2),
            "quantity": round(self.quantity, 6),
            "gross_pnl": round(self.gross_pnl, 2),
            "net_pnl": round(self.net_pnl, 2),
            "fees": round(self.entry_fee + self.exit_fee, 4),
            "slippage_cost": round(self.slippage_cost, 4),
            "exit_reason": self.exit_reason,
            "holding_periods": self.holding_periods,
        }


@dataclass
class PerformanceMetrics:
    starting_balance: float
    ending_balance: float
    total_return_pct: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: float
    average_win: float
    average_loss: float
    profit_factor: float
    max_drawdown_pct: float
    max_consecutive_losses: int
    average_holding_periods: float
    total_fees: float
    total_slippage: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "starting_balance": round(self.starting_balance, 2),
            "ending_balance": round(self.ending_balance, 2),
            "total_return_pct": round(self.total_return_pct, 4),
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate_pct": round(self.win_rate_pct, 2),
            "average_win": round(self.average_win, 2),
            "average_loss": round(self.average_loss, 2),
            "profit_factor": round(self.profit_factor, 4),
            "max_drawdown_pct": round(self.max_drawdown_pct, 4),
            "max_consecutive_losses": self.max_consecutive_losses,
            "average_holding_periods": round(self.average_holding_periods, 2),
            "total_fees": round(self.total_fees, 4),
            "total_slippage": round(self.total_slippage, 4),
        }


def compute_metrics(
    initial_balance: float,
    equity_curve: List[float],
    trades: List[BacktestTrade],
) -> PerformanceMetrics:
    """Computes comprehensive performance statistics for a backtest run.
    
    Avoids divide-by-zero errors when trade count is zero or all trades win/lose.
    """
    final_balance = equity_curve[-1] if equity_curve else initial_balance
    total_return = ((final_balance - initial_balance) / initial_balance) * 100.0

    # Drawdown computation from equity curve
    max_dd = 0.0
    if equity_curve:
        peak = equity_curve[0]
        for val in equity_curve:
            if val > peak:
                peak = val
            dd = (peak - val) / peak * 100.0 if peak > 0 else 0.0
            if dd > max_dd:
                max_dd = dd

    if not trades:
        return PerformanceMetrics(
            starting_balance=initial_balance,
            ending_balance=final_balance,
            total_return_pct=total_return,
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate_pct=0.0,
            average_win=0.0,
            average_loss=0.0,
            profit_factor=0.0,
            max_drawdown_pct=max_dd,
            max_consecutive_losses=0,
            average_holding_periods=0.0,
            total_fees=0.0,
            total_slippage=0.0,
        )

    wins = [t.net_pnl for t in trades if t.net_pnl > 0]
    losses = [t.net_pnl for t in trades if t.net_pnl < 0]
    num_wins = len(wins)
    num_losses = len(losses)
    total_trades = len(trades)

    win_rate = (num_wins / total_trades) * 100.0 if total_trades > 0 else 0.0
    avg_win = float(np.mean(wins)) if wins else 0.0
    avg_loss = float(np.mean(losses)) if losses else 0.0

    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    if gross_loss > 0:
        profit_factor = gross_profit / gross_loss
    elif gross_profit > 0:
        profit_factor = float("inf")
    else:
        profit_factor = 0.0

    # Max consecutive losses
    max_consec_losses = 0
    curr_consec_losses = 0
    for t in trades:
        if t.net_pnl < 0:
            curr_consec_losses += 1
            if curr_consec_losses > max_consec_losses:
                max_consec_losses = curr_consec_losses
        else:
            curr_consec_losses = 0

    avg_holding = float(np.mean([t.holding_periods for t in trades])) if trades else 0.0
    total_fees = sum(t.entry_fee + t.exit_fee for t in trades)
    total_slippage = sum(t.slippage_cost for t in trades)

    return PerformanceMetrics(
        starting_balance=initial_balance,
        ending_balance=final_balance,
        total_return_pct=total_return,
        total_trades=total_trades,
        winning_trades=num_wins,
        losing_trades=num_losses,
        win_rate_pct=win_rate,
        average_win=avg_win,
        average_loss=avg_loss,
        profit_factor=profit_factor if profit_factor != float("inf") else 999.99,
        max_drawdown_pct=max_dd,
        max_consecutive_losses=max_consec_losses,
        average_holding_periods=avg_holding,
        total_fees=total_fees,
        total_slippage=total_slippage,
    )
