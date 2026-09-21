"""Configuration module for Crypto Trading Bot - Phase 1.

Enforces strict safety tripwires: PAPER_TRADING_ONLY must be True.
Refuses to start if real-trading or unsafe options are configured.
"""

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()


@dataclass(frozen=True)
class BotConfig:
    # Safety invariant
    paper_trading_only: bool
    
    # Market data settings
    symbol: str
    candle_interval: str
    candle_limit: int
    
    # Paper portfolio
    initial_balance: float
    maker_fee: float
    taker_fee: float
    
    # Risk engine limits
    max_risk_per_trade: float   # e.g. 0.005 (0.5%)
    max_daily_loss: float        # e.g. 0.02 (2.0%)
    max_position_size: float     # e.g. 0.10 (10.0%)
    max_open_positions: int      # strictly 1
    leverage: float              # strictly 1.0 (no leverage)
    
    # Execution
    loop_interval_seconds: int

    # Jev AI Agent settings (secrets kept safe, never printed)
    jev_agent_key: Optional[str] = None
    jev_endpoint: str = "https://api.typesafe.ai/v1/systemone"
    jev_model: str = "jev-latest"
    jev_confidence_threshold: float = 0.60
    jev_timeout_seconds: float = 5.0

    @classmethod
    def from_env(cls) -> "BotConfig":
        raw_paper_only = os.getenv("PAPER_TRADING_ONLY", "true").strip().lower()
        paper_trading_only = raw_paper_only in ("true", "1", "yes")

        jev_key = os.getenv("JEV_AGENT_KEY")
        if jev_key:
            jev_key = jev_key.strip()
            if not jev_key:
                jev_key = None

        config = cls(
            paper_trading_only=paper_trading_only,
            symbol=os.getenv("TRADING_SYMBOL", "BTCUSDT").upper(),
            candle_interval=os.getenv("CANDLE_INTERVAL", "5m"),
            candle_limit=int(os.getenv("MARKET_DATA_LIMIT", "250")),
            initial_balance=float(os.getenv("INITIAL_BALANCE", "10000.0")),
            maker_fee=float(os.getenv("MAKER_FEE", "0.0002")),
            taker_fee=float(os.getenv("TAKER_FEE", "0.00075")),
            max_risk_per_trade=float(os.getenv("MAX_RISK_PER_TRADE", "0.005")),
            max_daily_loss=float(os.getenv("MAX_DAILY_LOSS", "0.02")),
            max_position_size=float(os.getenv("MAX_POSITION_SIZE", "0.10")),
            max_open_positions=int(os.getenv("MAX_OPEN_POSITIONS", "1")),
            leverage=float(os.getenv("LEVERAGE", "1.0")),
            loop_interval_seconds=int(os.getenv("LOOP_INTERVAL_SECONDS", "60")),
            jev_agent_key=jev_key,
            jev_endpoint=os.getenv("JEV_ENDPOINT", "https://api.typesafe.ai/v1/systemone"),
            jev_model=os.getenv("JEV_MODEL", "jev-latest"),
            jev_confidence_threshold=float(os.getenv("JEV_CONFIDENCE_THRESHOLD", "0.60")),
            jev_timeout_seconds=float(os.getenv("JEV_TIMEOUT_SECONDS", "5.0")),
        )

        config.validate_safety()
        return config

    def validate_safety(self) -> None:
        """Enforces critical Phase 1 safety tripwires.
        
        Refuses execution if paper trading is disabled or leverage is attempted.
        """
        if not self.paper_trading_only:
            raise RuntimeError(
                "CRITICAL SAFETY VIOLATION: PAPER_TRADING_ONLY is not True! "
                "Phase 1 is strictly paper-trading-only. Real execution is prohibited."
            )
        if self.leverage != 1.0:
            raise RuntimeError(
                f"CRITICAL SAFETY VIOLATION: Leverage is set to {self.leverage}x. "
                "Phase 1 strictly prohibits leverage (must be 1.0x)."
            )
        if self.max_open_positions > 1:
            raise RuntimeError(
                f"SAFETY VIOLATION: max_open_positions is {self.max_open_positions}. "
                "Phase 1 strictly enforces a maximum of 1 open position."
            )


# Default module-level configuration instance
def get_config() -> BotConfig:
    return BotConfig.from_env()
