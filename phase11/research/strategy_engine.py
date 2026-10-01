"""
Phase 11: XAU/USD Quantitative Multi-Strategy Research Engine.
Supports vectorized indicators, strictly next-bar execution, realistic microstructure cost modeling,
and multi-timeframe evaluation across Development (2021-2023), Validation (2024), and Holdout (2025).
"""

import json
import math
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


@dataclass
class CostModel:
    name: str
    half_spread_bps: float
    slippage_bps: float
    commission_bps: float = 0.0

    @property
    def total_one_way_friction_bps(self) -> float:
        return self.half_spread_bps + self.slippage_bps + self.commission_bps

    @property
    def total_round_trip_friction_bps(self) -> float:
        return 2.0 * self.total_one_way_friction_bps


# Standard cost scenarios for XAU/USD
COST_SCENARIOS = {
    "zero_friction": CostModel("Zero Friction", 0.0, 0.0, 0.0),
    "optimistic": CostModel("Optimistic", 1.0, 0.5, 0.0),    # ~1.5 bps one-way (~$0.30-$0.35/oz)
    "realistic": CostModel("Realistic", 2.0, 1.0, 0.0),      # ~3.0 bps one-way (~$0.60-$0.70/oz)
    "adverse": CostModel("Adverse", 5.0, 2.5, 0.0),          # ~7.5 bps one-way (~$1.50-$1.80/oz)
    "stress": CostModel("Stress", 10.0, 5.0, 0.0),           # ~15.0 bps one-way (~$3.00-$3.60/oz)
}


@dataclass
class TradeRecord:
    trade_id: int
    strategy: str
    timeframe: str
    direction: str  # 'LONG' or 'SHORT'
    entry_bar_idx: int
    entry_time_utc: str
    entry_price_raw: float
    entry_price_executed: float
    exit_bar_idx: int
    exit_time_utc: str
    exit_price_raw: float
    exit_price_executed: float
    exit_reason: str
    bars_held: int
    units: float
    notional_usd: float
    gross_pnl_usd: float
    gross_return_bps: float
    total_friction_usd: float
    total_friction_bps: float
    net_pnl_usd: float
    net_return_bps: float
    cash_after: float
    drawdown_pct_at_exit: float


@dataclass
class PerformanceSummary:
    strategy_id: str
    strategy_family: str
    timeframe: str
    dataset_split: str
    cost_scenario: str
    start_utc: str
    end_utc: str
    bars_count: int
    initial_cash: float
    final_cash: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: float
    gross_pnl_usd: float
    total_friction_usd: float
    net_pnl_usd: float
    net_return_pct: float
    annualized_return_pct: float
    profit_factor_gross: float
    profit_factor_net: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown_usd: float
    max_drawdown_pct: float
    max_consecutive_losses: int
    avg_trade_bars: float
    avg_net_trade_bps: float
    expectancy_usd: float


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Compute vector technical indicators on OHLCV dataframe."""
    df = df.copy()

    # EMAs
    df["ema_20"] = df["close"].ewm(span=20, adjust=False).mean()
    df["ema_50"] = df["close"].ewm(span=50, adjust=False).mean()
    df["ema_200"] = df["close"].ewm(span=200, adjust=False).mean()

    # SMAs
    df["sma_20"] = df["close"].rolling(20).mean()
    df["sma_50"] = df["close"].rolling(50).mean()
    df["sma_200"] = df["close"].rolling(200).mean()

    # ATR (14)
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift(1)).abs()
    low_close = (df["low"] - df["close"].shift(1)).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df["atr_14"] = tr.rolling(14).mean()
    df["atr_sma_20"] = df["atr_14"].rolling(20).mean()

    # RSI (14)
    delta = df["close"].diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / (avg_loss + 1e-12)
    df["rsi_14"] = 100.0 - (100.0 / (1.0 + rs))

    # Bollinger Bands (20, 2.0 std)
    rolling_std = df["close"].rolling(20).std()
    df["bb_mid"] = df["sma_20"]
    df["bb_upper"] = df["bb_mid"] + 2.0 * rolling_std
    df["bb_lower"] = df["bb_mid"] - 2.0 * rolling_std

    # Donchian Channels (20)
    df["donchian_high_20"] = df["high"].rolling(20).max()
    df["donchian_low_20"] = df["low"].rolling(20).min()

    # ADX (14)
    up_move = df["high"] - df["high"].shift(1)
    down_move = df["low"].shift(1) - df["low"]
    pos_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    neg_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    pos_di = 100.0 * (pd.Series(pos_dm, index=df.index).rolling(14).mean() / (df["atr_14"] + 1e-12))
    neg_di = 100.0 * (pd.Series(neg_dm, index=df.index).rolling(14).mean() / (df["atr_14"] + 1e-12))
    dx = 100.0 * (pos_di - neg_di).abs() / (pos_di + neg_di + 1e-12)
    df["adx_14"] = dx.rolling(14).mean()

    return df


def simulate_strategy(
    df: pd.DataFrame,
    signals: np.ndarray,  # 1 for Long, -1 for Short, 0 for Flat/Exit
    cost_model: CostModel,
    initial_cash: float = 10000.0,
    risk_pct_per_trade: float = 0.005,  # 0.5% max risk per trade
    strategy_id: str = "strategy",
    strategy_family: str = "generic",
    timeframe: str = "1h",
    dataset_split: str = "dev",
    use_trailing_atr_stop: bool = False,
    atr_mult: float = 2.0,
) -> Tuple[PerformanceSummary, List[TradeRecord], pd.DataFrame]:
    """
    Simulate strategy execution with strictly next-bar execution:
    - Signal generated at close of bar t (using data up to and including bar t).
    - Order executed at open of bar t+1 with half-spread and slippage applied.
    - Strictly one position open at a time (sequential execution, no pyramiding).
    """
    n = len(df)
    opens = df["open"].to_numpy()
    highs = df["high"].to_numpy()
    lows = df["low"].to_numpy()
    closes = df["close"].to_numpy()
    atrs = df["atr_14"].to_numpy() if "atr_14" in df else np.zeros(n)
    times = df["dt_utc"].astype(str).to_numpy()

    trades: List[TradeRecord] = []
    cash = initial_cash
    equity_series = np.zeros(n)
    peak_equity = initial_cash
    drawdowns_pct = np.zeros(n)

    current_pos = 0  # 1 for long, -1 for short, 0 for flat
    entry_idx = 0
    entry_raw_price = 0.0
    entry_exec_price = 0.0
    entry_units = 0.0
    entry_notional = 0.0
    trailing_stop_price = 0.0
    trade_counter = 0

    friction_rate = cost_model.total_one_way_friction_bps / 10000.0

    for i in range(n):
        # Update equity before checking new bar
        if current_pos != 0:
            # Mark to market at bar open
            unrealized_pnl = current_pos * entry_units * (opens[i] - entry_raw_price)
            current_equity = cash + unrealized_pnl
        else:
            current_equity = cash

        if current_equity > peak_equity:
            peak_equity = current_equity
        dd = (peak_equity - current_equity) / peak_equity if peak_equity > 0 else 0.0
        drawdowns_pct[i] = dd
        equity_series[i] = current_equity

        # If we have an active position, check trailing stop or exit signal first
        if current_pos != 0 and i > entry_idx:
            should_exit = False
            exit_reason = "signal"
            exit_raw_price = opens[i]

            # 1. Trailing Stop Check (if enabled)
            if use_trailing_atr_stop and atrs[i - 1] > 0:
                if current_pos == 1:
                    new_stop = closes[i - 1] - atr_mult * atrs[i - 1]
                    if new_stop > trailing_stop_price:
                        trailing_stop_price = new_stop
                    if lows[i] <= trailing_stop_price:
                        should_exit = True
                        exit_reason = "trailing_stop"
                        exit_raw_price = min(opens[i], trailing_stop_price)
                elif current_pos == -1:
                    new_stop = closes[i - 1] + atr_mult * atrs[i - 1]
                    if trailing_stop_price == 0.0 or new_stop < trailing_stop_price:
                        trailing_stop_price = new_stop
                    if highs[i] >= trailing_stop_price:
                        should_exit = True
                        exit_reason = "trailing_stop"
                        exit_raw_price = max(opens[i], trailing_stop_price)

            # 2. Strategy Signal Exit Check
            # Signal at bar i-1 triggers exit at open of bar i
            sig = signals[i - 1]
            if not should_exit:
                if current_pos == 1 and sig <= 0:
                    should_exit = True
                    exit_reason = "signal_exit" if sig == 0 else "signal_reversal"
                elif current_pos == -1 and sig >= 0:
                    should_exit = True
                    exit_reason = "signal_exit" if sig == 0 else "signal_reversal"

            # Execute Exit
            if should_exit:
                # One-way friction on exit
                if current_pos == 1:
                    exit_exec_price = exit_raw_price * (1.0 - friction_rate)
                else:
                    exit_exec_price = exit_raw_price * (1.0 + friction_rate)

                gross_pnl = current_pos * entry_units * (exit_raw_price - entry_raw_price)
                gross_ret_bps = (gross_pnl / entry_notional) * 10000.0 if entry_notional > 0 else 0.0

                net_pnl = current_pos * entry_units * (exit_exec_price - entry_exec_price)
                net_ret_bps = (net_pnl / entry_notional) * 10000.0 if entry_notional > 0 else 0.0

                total_friction_usd = gross_pnl - net_pnl
                total_friction_bps = gross_ret_bps - net_ret_bps

                cash += net_pnl
                trade_counter += 1

                trades.append(
                    TradeRecord(
                        trade_id=trade_counter,
                        strategy=strategy_id,
                        timeframe=timeframe,
                        direction="LONG" if current_pos == 1 else "SHORT",
                        entry_bar_idx=entry_idx,
                        entry_time_utc=times[entry_idx],
                        entry_price_raw=round(entry_raw_price, 3),
                        entry_price_executed=round(entry_exec_price, 3),
                        exit_bar_idx=i,
                        exit_time_utc=times[i],
                        exit_price_raw=round(exit_raw_price, 3),
                        exit_price_executed=round(exit_exec_price, 3),
                        exit_reason=exit_reason,
                        bars_held=i - entry_idx,
                        units=round(entry_units, 4),
                        notional_usd=round(entry_notional, 2),
                        gross_pnl_usd=round(gross_pnl, 2),
                        gross_return_bps=round(gross_ret_bps, 2),
                        total_friction_usd=round(total_friction_usd, 2),
                        total_friction_bps=round(total_friction_bps, 2),
                        net_pnl_usd=round(net_pnl, 2),
                        net_return_bps=round(net_ret_bps, 2),
                        cash_after=round(cash, 2),
                        drawdown_pct_at_exit=round(dd * 100.0, 2),
                    )
                )

                current_pos = 0
                entry_units = 0.0
                trailing_stop_price = 0.0

        # Check for Entry Signal (if currently flat)
        if current_pos == 0 and i > 0 and i < n - 1:
            sig = signals[i - 1]  # Signal at close of bar i-1 executes at open of bar i
            if sig != 0:
                current_pos = int(sig)
                entry_idx = i
                entry_raw_price = opens[i]

                # Apply entry friction
                if current_pos == 1:
                    entry_exec_price = entry_raw_price * (1.0 + friction_rate)
                else:
                    entry_exec_price = entry_raw_price * (1.0 - friction_rate)

                # Position Sizing: Risk-based or fixed cash allocation
                # Allocate 100% of current cash as notional (1.0x leverage)
                entry_notional = cash * 1.0
                entry_units = entry_notional / entry_raw_price

                # Initialize trailing stop
                if use_trailing_atr_stop and atrs[i - 1] > 0:
                    if current_pos == 1:
                        trailing_stop_price = entry_raw_price - atr_mult * atrs[i - 1]
                    else:
                        trailing_stop_price = entry_raw_price + atr_mult * atrs[i - 1]

    # Force close any open position at end of backtest period
    if current_pos != 0:
        i = n - 1
        exit_raw_price = closes[i]
        if current_pos == 1:
            exit_exec_price = exit_raw_price * (1.0 - friction_rate)
        else:
            exit_exec_price = exit_raw_price * (1.0 + friction_rate)

        gross_pnl = current_pos * entry_units * (exit_raw_price - entry_raw_price)
        gross_ret_bps = (gross_pnl / entry_notional) * 10000.0 if entry_notional > 0 else 0.0
        net_pnl = current_pos * entry_units * (exit_exec_price - entry_exec_price)
        net_ret_bps = (net_pnl / entry_notional) * 10000.0 if entry_notional > 0 else 0.0
        total_friction_usd = gross_pnl - net_pnl
        total_friction_bps = gross_ret_bps - net_ret_bps
        cash += net_pnl
        trade_counter += 1

        trades.append(
            TradeRecord(
                trade_id=trade_counter,
                strategy=strategy_id,
                timeframe=timeframe,
                direction="LONG" if current_pos == 1 else "SHORT",
                entry_bar_idx=entry_idx,
                entry_time_utc=times[entry_idx],
                entry_price_raw=round(entry_raw_price, 3),
                entry_price_executed=round(entry_exec_price, 3),
                exit_bar_idx=i,
                exit_time_utc=times[i],
                exit_price_raw=round(exit_raw_price, 3),
                exit_price_executed=round(exit_exec_price, 3),
                exit_reason="end_of_data",
                bars_held=i - entry_idx,
                units=round(entry_units, 4),
                notional_usd=round(entry_notional, 2),
                gross_pnl_usd=round(gross_pnl, 2),
                gross_return_bps=round(gross_ret_bps, 2),
                total_friction_usd=round(total_friction_usd, 2),
                total_friction_bps=round(total_friction_bps, 2),
                net_pnl_usd=round(net_pnl, 2),
                net_return_bps=round(net_ret_bps, 2),
                cash_after=round(cash, 2),
                drawdown_pct_at_exit=round(drawdowns_pct[-1] * 100.0, 2),
            )
        )

    # Compute Aggregate Statistics
    total_trades = len(trades)
    winning_trades = sum(1 for t in trades if t.net_pnl_usd > 0)
    losing_trades = sum(1 for t in trades if t.net_pnl_usd < 0)
    win_rate = (winning_trades / total_trades * 100.0) if total_trades > 0 else 0.0

    gross_pnl_total = sum(t.gross_pnl_usd for t in trades)
    net_pnl_total = sum(t.net_pnl_usd for t in trades)
    total_friction = sum(t.total_friction_usd for t in trades)
    net_ret_pct = ((cash - initial_cash) / initial_cash) * 100.0

    # Annualization factor
    years = max(0.1, (pd.to_datetime(times[-1]) - pd.to_datetime(times[0])).total_seconds() / (365.25 * 86400))
    ann_return_pct = ((cash / initial_cash) ** (1.0 / years) - 1.0) * 100.0 if cash > 0 else -100.0

    gross_wins = sum(t.gross_pnl_usd for t in trades if t.gross_pnl_usd > 0)
    gross_losses = abs(sum(t.gross_pnl_usd for t in trades if t.gross_pnl_usd < 0))
    pf_gross = (gross_wins / gross_losses) if gross_losses > 0 else (99.0 if gross_wins > 0 else 0.0)

    net_wins = sum(t.net_pnl_usd for t in trades if t.net_pnl_usd > 0)
    net_losses = abs(sum(t.net_pnl_usd for t in trades if t.net_pnl_usd < 0))
    pf_net = (net_wins / net_losses) if net_losses > 0 else (99.0 if net_wins > 0 else 0.0)

    # Return series for Sharpe / Sortino
    trade_returns = [t.net_return_bps / 10000.0 for t in trades]
    if len(trade_returns) > 1 and np.std(trade_returns) > 1e-9:
        mean_ret = np.mean(trade_returns)
        std_ret = np.std(trade_returns, ddof=1)
        # Trades per year
        trades_per_yr = len(trades) / years
        sharpe = (mean_ret / std_ret) * math.sqrt(trades_per_yr)

        downside_diffs = [min(0.0, r) for r in trade_returns]
        downside_std = math.sqrt(sum(d**2 for d in downside_diffs) / len(downside_diffs))
        sortino = (mean_ret / downside_std * math.sqrt(trades_per_yr)) if downside_std > 1e-9 else 0.0
    else:
        sharpe = 0.0
        sortino = 0.0

    max_dd_pct = float(np.max(drawdowns_pct) * 100.0)
    max_dd_usd = float(peak_equity * (max_dd_pct / 100.0))
    calmar = (ann_return_pct / max_dd_pct) if max_dd_pct > 0 else 0.0

    # Consecutive losses
    max_consec_loss = 0
    cur_consec = 0
    for t in trades:
        if t.net_pnl_usd < 0:
            cur_consec += 1
            if cur_consec > max_consec_loss:
                max_consec_loss = cur_consec
        else:
            cur_consec = 0

    avg_bars = float(np.mean([t.bars_held for t in trades])) if trades else 0.0
    avg_bps = float(np.mean([t.net_return_bps for t in trades])) if trades else 0.0
    expectancy = (net_pnl_total / total_trades) if total_trades > 0 else 0.0

    summary = PerformanceSummary(
        strategy_id=strategy_id,
        strategy_family=strategy_family,
        timeframe=timeframe,
        dataset_split=dataset_split,
        cost_scenario=cost_model.name,
        start_utc=str(times[0]),
        end_utc=str(times[-1]),
        bars_count=n,
        initial_cash=initial_cash,
        final_cash=round(cash, 2),
        total_trades=total_trades,
        winning_trades=winning_trades,
        losing_trades=losing_trades,
        win_rate_pct=round(win_rate, 2),
        gross_pnl_usd=round(gross_pnl_total, 2),
        total_friction_usd=round(total_friction, 2),
        net_pnl_usd=round(net_pnl_total, 2),
        net_return_pct=round(net_ret_pct, 2),
        annualized_return_pct=round(ann_return_pct, 2),
        profit_factor_gross=round(pf_gross, 2),
        profit_factor_net=round(pf_net, 2),
        sharpe_ratio=round(sharpe, 2),
        sortino_ratio=round(sortino, 2),
        calmar_ratio=round(calmar, 2),
        max_drawdown_usd=round(max_dd_usd, 2),
        max_drawdown_pct=round(max_dd_pct, 2),
        max_consecutive_losses=max_consec_loss,
        avg_trade_bars=round(avg_bars, 1),
        avg_net_trade_bps=round(avg_bps, 2),
        expectancy_usd=round(expectancy, 2),
    )

    curve_df = pd.DataFrame({
        "timestamp_ms": df["timestamp_ms"],
        "dt_utc": df["dt_utc"],
        "equity": equity_series,
        "drawdown_pct": drawdowns_pct * 100.0,
    })

    return summary, trades, curve_df
