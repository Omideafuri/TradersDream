"""Bot Controller Service layer managing the CryptoTradingBot lifecycle and real-time state."""

import asyncio
from collections import deque
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import time
from typing import Dict, Any, List, Optional, Set
import uuid

import psutil
from starlette.websockets import WebSocket

from bot.config import BotConfig
from bot.main import CryptoTradingBot
from bot.decision import Action

logger = logging.getLogger("dashboard.service")


class WebSocketManager:
    """Manages active WebSocket client connections for real-time state streaming."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WebSocket client connected. Total clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket) -> None:
        self.active_connections.discard(websocket)
        logger.info(f"WebSocket client disconnected. Total clients: {len(self.active_connections)}")

    async def broadcast_json(self, data: Dict[str, Any]) -> None:
        """Broadcasts a JSON-serializable message to all active clients."""
        dead_connections = set()
        for connection in list(self.active_connections):
            try:
                await connection.send_json(data)
            except Exception:
                dead_connections.add(connection)
        for dead in dead_connections:
            self.active_connections.discard(dead)


class BotService:
    """Singleton service wrapping CryptoTradingBot with lifecycle control, caching, and telemetry."""

    _instance: Optional["BotService"] = None

    def __init__(self, config: Optional[BotConfig] = None):
        self.config = config or BotConfig.from_env()
        self.bot = CryptoTradingBot(self.config, allow_synthetic_fallback=False)
        
        self.status = "STOPPED"  # "STOPPED" | "RUNNING" | "PAUSED" | "ERROR"
        self._loop_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        
        self.ws_manager = WebSocketManager()
        
        # Telemetry & state caches
        self.start_time: Optional[float] = None
        self.last_heartbeat: float = time.time()
        self.last_market_fetch_time: Optional[float] = None
        self.error_count: int = 0
        
        self.latest_cycle: Optional[Dict[str, Any]] = None
        self.latest_candles: List[Dict[str, Any]] = []
        
        # In-memory activity log ring buffer (500 entries)
        self.activity_logs: deque = deque(maxlen=500)
        
        # System startup log
        self._record_log("INFO", "Bot Service initialized in PAPER_TRADING mode.", "SYSTEM")

    @classmethod
    def get_instance(cls) -> "BotService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _record_log(self, level: str, message: str, source: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Appends a structured log event to the in-memory ring buffer."""
        entry = {
            "id": str(uuid.uuid4())[:8],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "message": message,
            "source": source,
            "data": data,
        }
        self.activity_logs.appendleft(entry)
        return entry

    async def start(self) -> Dict[str, Any]:
        """Starts the autonomous trading loop."""
        async with self._lock:
            if self.status == "RUNNING":
                return {"success": False, "message": "Bot is already running.", "status": self.status}
            
            self.status = "RUNNING"
            self.start_time = time.time()
            self._record_log("INFO", f"Bot loop started for {self.config.symbol} (interval: {self.config.loop_interval_seconds}s).", "CONTROLLER")
            
            if self._loop_task is None or self._loop_task.done():
                self._loop_task = asyncio.create_task(self._run_loop())
            
            await self._broadcast_status()
            return {"success": True, "message": "Bot started successfully.", "status": self.status}

    async def pause(self) -> Dict[str, Any]:
        """Pauses autonomous cycle execution without clearing state."""
        async with self._lock:
            if self.status != "RUNNING":
                return {"success": False, "message": f"Cannot pause bot from status '{self.status}'.", "status": self.status}
            
            self.status = "PAUSED"
            self._record_log("WARNING", "Bot execution paused by user.", "CONTROLLER")
            await self._broadcast_status()
            return {"success": True, "message": "Bot execution paused.", "status": self.status}

    async def resume(self) -> Dict[str, Any]:
        """Resumes execution from paused state."""
        async with self._lock:
            if self.status != "PAUSED":
                return {"success": False, "message": f"Cannot resume bot from status '{self.status}'.", "status": self.status}
            
            self.status = "RUNNING"
            self._record_log("INFO", "Bot execution resumed by user.", "CONTROLLER")
            await self._broadcast_status()
            return {"success": True, "message": "Bot execution resumed.", "status": self.status}

    async def stop(self, confirmed: bool = False) -> Dict[str, Any]:
        """Stops the autonomous trading loop. Requires confirmation."""
        if not confirmed:
            return {"success": False, "message": "Stop command requires explicit confirmation.", "status": self.status}

        async with self._lock:
            self.status = "STOPPED"
            if self._loop_task and not self._loop_task.done():
                self._loop_task.cancel()
                try:
                    await self._loop_task
                except asyncio.CancelledError:
                    pass
                self._loop_task = None
            
            self._record_log("INFO", "Bot execution stopped.", "CONTROLLER")
            await self._broadcast_status()
            return {"success": True, "message": "Bot stopped successfully.", "status": self.status}

    async def emergency_stop(self, confirmed: bool = False) -> Dict[str, Any]:
        """Liquidates any open position at market, cancels the loop, and halts."""
        if not confirmed:
            return {"success": False, "message": "Emergency stop requires explicit confirmation.", "status": self.status}

        async with self._lock:
            self.status = "STOPPED"
            if self._loop_task and not self._loop_task.done():
                self._loop_task.cancel()
                self._loop_task = None

            # Liquidate open paper position if one exists
            current_price = self.latest_cycle.get("price", 0.0) if self.latest_cycle else 0.0
            if current_price <= 0 and self.latest_candles:
                current_price = self.latest_candles[-1].get("close", 0.0)
            
            liquidated_info = None
            if self.bot.paper_trader.has_open_position:
                try:
                    rec = self.bot.paper_trader.execute_sell(price=current_price, timestamp=int(time.time() * 1000))
                    self.bot.risk_engine.record_closed_trade(rec.net_pnl)
                    liquidated_info = rec.to_dict()
                    self._record_log("CRITICAL", f"EMERGENCY LIQUIDATION: Closed position at ${current_price:,.2f} | Net PnL: ${rec.net_pnl:,.2f}", "EMERGENCY_STOP", liquidated_info)
                except Exception as exc:
                    self._record_log("ERROR", f"Emergency liquidation failed: {exc}", "EMERGENCY_STOP")

            self._record_log("CRITICAL", "EMERGENCY STOP executed. Bot halted.", "CONTROLLER")
            await self._broadcast_status()
            return {
                "success": True,
                "message": "Emergency stop executed. Positions closed and bot halted.",
                "status": self.status,
                "liquidated_position": liquidated_info,
            }

    async def step(self) -> Dict[str, Any]:
        """Executes a single market analysis and paper trading cycle."""
        try:
            self.last_heartbeat = time.time()
            log_entry = await self.bot.step()
            self.last_market_fetch_time = time.time()
            self.latest_cycle = log_entry

            # Update cached candle history with computed indicators
            try:
                klines_df = await self.bot.market_data.fetch_klines(
                    symbol=self.config.symbol,
                    interval=self.config.candle_interval,
                    limit=100,
                )
                from bot.indicators import calculate_indicators
                enriched = calculate_indicators(klines_df)
                candles_list = []
                for _, row in enriched.iterrows():
                    candles_list.append({
                        "timestamp": int(row["timestamp"]),
                        "open": float(row["open"]),
                        "high": float(row["high"]),
                        "low": float(row["low"]),
                        "close": float(row["close"]),
                        "volume": float(row["volume"]),
                        "ema20": float(row["ema20"]) if "ema20" in row and not pd_isna(row["ema20"]) else None,
                        "ema50": float(row["ema50"]) if "ema50" in row and not pd_isna(row["ema50"]) else None,
                        "ema200": float(row["ema200"]) if "ema200" in row and not pd_isna(row["ema200"]) else None,
                        "rsi14": float(row["rsi14"]) if "rsi14" in row and not pd_isna(row["rsi14"]) else None,
                        "atr14": float(row["atr14"]) if "atr14" in row and not pd_isna(row["atr14"]) else None,
                        "volume_ratio": float(row["volume_ratio"]) if "volume_ratio" in row and not pd_isna(row["volume_ratio"]) else None,
                    })
                self.latest_candles = candles_list
            except Exception as e:
                logger.debug(f"Candle history enrichment error: {e}")

            # Record activity log
            action = log_entry.get("executed_action", "HOLD")
            jev_action = log_entry.get("jev_action", "HOLD")
            conf = log_entry.get("jev_confidence", 0.0)
            reason = log_entry.get("jev_reason_code", "UNKNOWN")
            price = log_entry.get("price", 0.0)
            
            msg = f"Cycle finished @ ${price:,.2f}. Jev: {jev_action} ({conf*100:.1f}% - {reason}). Executed: {action}."
            self._record_log("INFO", msg, "TRADING_ENGINE", log_entry)

            # Broadcast update via WebSocket
            await self.ws_manager.broadcast_json({
                "type": "CYCLE_UPDATE",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "cycle": log_entry,
                "status": self.get_status_dict(),
            })

            return log_entry
        except Exception as exc:
            self.error_count += 1
            self._record_log("ERROR", f"Error during bot step: {type(exc).__name__}: {exc}", "TRADING_ENGINE")
            raise

    async def _run_loop(self) -> None:
        """Internal asynchronous loop driving autonomous cycles."""
        while self.status in ("RUNNING", "PAUSED"):
            try:
                self.last_heartbeat = time.time()
                if self.status == "RUNNING":
                    await self.step()
                await asyncio.sleep(self.config.loop_interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                self.error_count += 1
                logger.error(f"Loop error: {exc}", exc_info=True)
                await asyncio.sleep(5.0)

    async def _broadcast_status(self) -> None:
        """Broadcasts current bot status to all WebSocket clients."""
        await self.ws_manager.broadcast_json({
            "type": "STATUS_UPDATE",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": self.get_status_dict(),
        })

    def get_status_dict(self) -> Dict[str, Any]:
        """Generates comprehensive status dictionary."""
        current_price = self.latest_cycle.get("price", 0.0) if self.latest_cycle else 0.0
        snap = self.bot.paper_trader.get_snapshot(current_price)
        
        pos = self.bot.paper_trader.current_position
        pos_dict = None
        if pos:
            now_ms = int(time.time() * 1000)
            duration_sec = max(0.0, (now_ms - pos.entry_time) / 1000.0)
            unreal_pnl = snap["unrealized_pnl"]
            entry_val = pos.entry_price * pos.quantity
            unreal_pct = (unreal_pnl / entry_val * 100.0) if entry_val > 0 else 0.0
            pos_dict = {
                "symbol": pos.symbol,
                "side": pos.side,
                "entry_price": pos.entry_price,
                "current_price": current_price,
                "quantity": pos.quantity,
                "notional": pos.quantity * current_price,
                "unrealized_pnl": unreal_pnl,
                "unrealized_pnl_pct": unreal_pct,
                "entry_time": pos.entry_time,
                "duration_seconds": duration_sec,
                "status": "OPEN",
            }

        history = self.bot.paper_trader.trade_history
        total_trades = len(history)
        winning_trades = sum(1 for t in history if t.net_pnl > 0)
        win_rate = (winning_trades / total_trades * 100.0) if total_trades > 0 else 0.0
        
        exposure = 0.0
        if pos and snap["portfolio_value"] > 0:
            exposure = (pos.quantity * current_price) / snap["portfolio_value"] * 100.0

        uptime = (time.time() - self.start_time) if self.start_time and self.status == "RUNNING" else 0.0

        return {
            "status": self.status,
            "paper_trading_only": True,
            "symbol": self.config.symbol,
            "price": current_price,
            "portfolio_value": snap["portfolio_value"],
            "cash_balance": snap["cash_balance"],
            "realized_pnl": snap["realized_pnl"],
            "unrealized_pnl": snap["unrealized_pnl"],
            "max_drawdown_pct": snap["max_drawdown_pct"],
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "win_rate": win_rate,
            "exposure_pct": exposure,
            "has_open_position": self.bot.paper_trader.has_open_position,
            "active_position": pos_dict,
            "current_signal": self.latest_cycle.get("jev_action", "HOLD") if self.latest_cycle else "HOLD",
            "signal_confidence": self.latest_cycle.get("jev_confidence", 0.0) if self.latest_cycle else 0.0,
            "signal_reason": self.latest_cycle.get("jev_reason_code", "INITIALIZING") if self.latest_cycle else "INITIALIZING",
            "last_action": self.latest_cycle.get("executed_action", "HOLD") if self.latest_cycle else "NONE",
            "last_update": self.latest_cycle.get("timestamp", datetime.now(timezone.utc).isoformat()) if self.latest_cycle else datetime.now(timezone.utc).isoformat(),
            "uptime_seconds": uptime,
            "loop_interval_seconds": self.config.loop_interval_seconds,
        }

    def get_trades_list(self) -> List[Dict[str, Any]]:
        """Returns the list of closed paper trades."""
        results = []
        for t in reversed(self.bot.paper_trader.trade_history):
            duration = max(0.0, (t.exit_time - t.entry_time) / 1000.0)
            results.append({
                "trade_id": str(uuid.uuid4())[:8],
                "symbol": t.symbol,
                "side": t.side,
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "quantity": t.quantity,
                "notional": t.entry_price * t.quantity,
                "gross_pnl": t.gross_pnl,
                "net_pnl": t.net_pnl,
                "fee_paid": t.fee_paid,
                "slippage_cost": t.slippage_cost,
                "entry_time": t.entry_time,
                "exit_time": t.exit_time,
                "duration_seconds": duration,
                "exit_reason": t.exit_reason,
                "is_winner": t.net_pnl > 0,
            })
        return results

    def get_strategy_config_dict(self) -> Dict[str, Any]:
        """Returns read-only strategy parameters."""
        return {
            "symbol": self.config.symbol,
            "candle_interval": self.config.candle_interval,
            "candle_limit": self.config.candle_limit,
            "initial_balance": self.config.initial_balance,
            "maker_fee_bps": self.config.maker_fee * 10000.0,
            "taker_fee_bps": self.config.taker_fee * 10000.0,
            "max_risk_per_trade_pct": self.config.max_risk_per_trade * 100.0,
            "max_daily_loss_pct": self.config.max_daily_loss * 100.0,
            "max_position_size_pct": self.config.max_position_size * 100.0,
            "max_open_positions": self.config.max_open_positions,
            "leverage": self.config.leverage,
            "confidence_threshold": self.config.jev_confidence_threshold,
            "loop_interval_seconds": self.config.loop_interval_seconds,
            "paper_trading_only": True,
            "use_live_jev": self.config.use_live_jev,
            "decision_provider": "JevApiProvider (Live)" if self.config.use_live_jev else "RuleBasedJev (Offline)",
            "jev_endpoint": self.config.jev_endpoint,
            "jev_model": self.config.jev_model,
        }

    def get_system_health_dict(self) -> Dict[str, Any]:
        """Calculates system resource health and connectivity indicators."""
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
        
        market_status = "CONNECTED" if (self.last_market_fetch_time and (time.time() - self.last_market_fetch_time < 300)) else "STANDBY"
        
        return {
            "bot_status": self.status,
            "market_data_status": market_status,
            "api_status": "HEALTHY",
            "websocket_status": "CONNECTED" if len(self.ws_manager.active_connections) > 0 else "STANDBY",
            "last_heartbeat": datetime.fromtimestamp(self.last_heartbeat, timezone.utc).isoformat(),
            "last_market_fetch": datetime.fromtimestamp(self.last_market_fetch_time, timezone.utc).isoformat() if self.last_market_fetch_time else None,
            "error_count": self.error_count,
            "cpu_percent": cpu,
            "memory_mb": round(mem, 2),
            "active_connections": len(self.ws_manager.active_connections),
            "paper_trading_invariant": True,
        }


def pd_isna(val: Any) -> bool:
    """Helper to detect NaN values without crashing."""
    try:
        import numpy as np
        return bool(np.isnan(val))
    except Exception:
        return False
