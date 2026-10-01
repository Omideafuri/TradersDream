"""Pydantic schemas for the Web Dashboard API."""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class ActivePositionSchema(BaseModel):
    symbol: str
    side: str
    entry_price: float
    current_price: float
    quantity: float
    notional: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    entry_time: int
    duration_seconds: float
    status: str = "OPEN"


class BotStatusResponse(BaseModel):
    status: str = Field(..., description="RUNNING | PAUSED | STOPPED | ERROR")
    paper_trading_only: bool = True
    symbol: str
    price: float
    portfolio_value: float
    cash_balance: float
    realized_pnl: float
    unrealized_pnl: float
    max_drawdown_pct: float
    total_trades: int
    winning_trades: int
    win_rate: float
    exposure_pct: float
    has_open_position: bool
    active_position: Optional[ActivePositionSchema] = None
    current_signal: str
    signal_confidence: float
    signal_reason: str
    last_action: str
    last_update: str
    uptime_seconds: float
    loop_interval_seconds: int


class MarketDataPoint(BaseModel):
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    ema20: Optional[float] = None
    ema50: Optional[float] = None
    ema200: Optional[float] = None
    rsi14: Optional[float] = None
    atr14: Optional[float] = None
    volume_ratio: Optional[float] = None


class MarketDataResponse(BaseModel):
    symbol: str
    interval: str
    current_price: float
    price_change_pct_5m: float
    candles: List[MarketDataPoint]


class SignalInfoResponse(BaseModel):
    symbol: str
    timestamp: str
    price: float
    action: str
    confidence: float
    reason_code: str
    risk_approved: bool
    rejection_reason: Optional[str] = None
    indicators: Dict[str, Any]


class PaperTradeRecordSchema(BaseModel):
    trade_id: str
    symbol: str
    side: str
    entry_price: float
    exit_price: float
    quantity: float
    notional: float
    gross_pnl: float
    net_pnl: float
    fee_paid: float
    slippage_cost: float
    entry_time: int
    exit_time: int
    duration_seconds: float
    exit_reason: str
    is_winner: bool


class StrategyConfigResponse(BaseModel):
    symbol: str
    candle_interval: str
    candle_limit: int
    initial_balance: float
    maker_fee_bps: float
    taker_fee_bps: float
    max_risk_per_trade_pct: float
    max_daily_loss_pct: float
    max_position_size_pct: float
    max_open_positions: int
    leverage: float
    confidence_threshold: float
    loop_interval_seconds: int
    paper_trading_only: bool
    use_live_jev: bool
    decision_provider: str
    jev_endpoint: str
    jev_model: str


class ResearchSummaryResponse(BaseModel):
    research_scope: str
    final_classification: str
    reproducibility_status: str
    sampling_frequency: str
    best_gross_edge_bps: float
    best_net_edge_bps: float
    average_dynamic_hurdle_bps: float
    holdout_gross_edge_bps: float
    holdout_net_edge_bps: float
    incremental_auc: float
    incremental_auc_p_value: float
    incremental_auc_ci: List[float]
    hypothesis_statuses: Dict[str, str]
    datasets: Dict[str, Any]
    next_permitted_research_direction: str


class LogEntrySchema(BaseModel):
    id: str
    timestamp: str
    level: str  # INFO | WARNING | ERROR | CRITICAL
    message: str
    source: str
    data: Optional[Dict[str, Any]] = None


class SystemHealthResponse(BaseModel):
    bot_status: str
    market_data_status: str
    api_status: str
    websocket_status: str
    last_heartbeat: str
    last_market_fetch: Optional[str] = None
    error_count: int
    cpu_percent: float
    memory_mb: float
    active_connections: int
    paper_trading_invariant: bool


class CommandRequest(BaseModel):
    command: str  # "start" | "pause" | "resume" | "stop" | "emergency-stop" | "step"
    confirmed: bool = False
    params: Optional[Dict[str, Any]] = None


class CommandResponse(BaseModel):
    success: bool
    message: str
    new_status: str
    timestamp: str
