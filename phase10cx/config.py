"""Phase 10C.X Frozen Configuration and Reproducibility Specification."""

from dataclasses import dataclass, field
import hashlib
import json
from typing import Dict, Any


@dataclass(frozen=True)
class ExecutionScenario:
    name: str
    fee_rate: float            # e.g. 0.0002 (2 bps), 0.0010 (10 bps)
    slippage_rate: float       # e.g. 0.0001 (1 bps), 0.0005 (5 bps)
    latency_ms: float          # e.g. 10ms, 50ms, 100ms
    adverse_selection_bps: float = 0.0  # additional adverse price movement during fill


@dataclass(frozen=True)
class FrozenStrategyConfig:
    """Immutable strategy parameters frozen before historical blind testing."""
    git_commit: str = "9e720c54bf856976e001c3d3257a20cc9514f754"
    git_commit_hash: str = "9e720c54bf856976e001c3d3257a20cc9514f754"
    strategy_version: str = "v10c.x-frozen-baseline"
    symbol: str = "BTCUSDT"
    venue: str = "binance-us"
    
    # Capital & Portfolio
    initial_balance: float = 10000.0
    leverage: float = 1.0
    
    # Risk Limits
    max_risk_per_trade: float = 0.005    # 0.5% max equity risk
    max_position_size: float = 0.10      # 10.0% max position
    max_daily_loss: float = 0.02         # 2.0% daily circuit breaker
    max_open_positions: int = 1          # strictly 1 position
    
    # Exits
    stop_loss_pct: float = 0.015         # 1.5% stop loss
    take_profit_pct: float = 0.030       # 3.0% take profit
    max_holding_bars: int = 24           # 24 periods (e.g. 2 hours on 5m)
    confidence_threshold: float = 0.60
    
    # Indicators
    ema_fast: int = 20
    ema_medium: int = 50
    ema_slow: int = 200
    rsi_period: int = 14
    rsi_upper_thresh: float = 70.0
    rsi_lower_thresh: float = 30.0
    volume_ratio_thresh: float = 1.0
    
    # Microstructure Features
    depth_levels: int = 10
    imbalance_lookback_ms: int = 300000  # 5 minutes
    
    # Safety Invariants
    paper_trading_only: bool = True
    use_live_jev: bool = False
    live_orders: int = 0
    wallet_connections: int = 0
    private_keys: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "git_commit": self.git_commit,
            "strategy_version": self.strategy_version,
            "symbol": self.symbol,
            "venue": self.venue,
            "initial_balance": self.initial_balance,
            "leverage": self.leverage,
            "max_risk_per_trade": self.max_risk_per_trade,
            "max_position_size": self.max_position_size,
            "max_daily_loss": self.max_daily_loss,
            "max_open_positions": self.max_open_positions,
            "stop_loss_pct": self.stop_loss_pct,
            "take_profit_pct": self.take_profit_pct,
            "max_holding_bars": self.max_holding_bars,
            "confidence_threshold": self.confidence_threshold,
            "ema_fast": self.ema_fast,
            "ema_medium": self.ema_medium,
            "ema_slow": self.ema_slow,
            "rsi_period": self.rsi_period,
            "paper_trading_only": self.paper_trading_only,
            "use_live_jev": self.use_live_jev,
        }

    def compute_hash(self) -> str:
        s = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(s.encode("utf-8")).hexdigest()


# The 3 Mandatory Execution Scenarios
SCENARIOS = {
    "optimistic": ExecutionScenario(
        name="Scenario A — Optimistic",
        fee_rate=0.0002,           # 2 bps maker/low taker
        slippage_rate=0.0001,      # 1 bps slippage
        latency_ms=10.0,
        adverse_selection_bps=0.0,
    ),
    "base": ExecutionScenario(
        name="Scenario B — Base",
        fee_rate=0.0010,           # 10 bps standard taker
        slippage_rate=0.0005,      # 5 bps slippage
        latency_ms=50.0,
        adverse_selection_bps=1.0, # 1 bps adverse selection
    ),
    "conservative": ExecutionScenario(
        name="Scenario C — Conservative",
        fee_rate=0.0010,           # 10 bps standard taker
        slippage_rate=0.0010,      # 10 bps slippage
        latency_ms=100.0,
        adverse_selection_bps=2.0, # 2 bps adverse selection (43.7 bps total hurdle)
    ),
}
