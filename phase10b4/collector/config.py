"""Configuration for free direct exchange event-data collector."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List


@dataclass
class CollectorConfig:
    """Configuration parameters for Binance.US public streaming collector."""
    
    venue: str = "binance-us"
    symbols: List[str] = field(default_factory=lambda: ["BTCUSDT", "ETHUSDT", "SOLUSDT"])
    ws_endpoint: str = "wss://stream.binance.us:9443/stream"
    rest_depth_endpoint: str = "https://api.binance.us/api/v3/depth"
    depth_limit: int = 1000
    depth_frequency: str = "100ms"  # @depth@100ms
    output_dir: Path = field(default_factory=lambda: Path("data/collected_events"))
    rotation_seconds: int = 86400  # Daily file rotation
    max_reconnect_attempts: int = 5
    reconnect_backoff_seconds: float = 2.0
    buffer_flush_size: int = 5000
    enable_gzip_compression: bool = True
    raw_output_dir: Path = field(default_factory=lambda: Path("data/raw_collected_events"))
    checkpoint_dir: Path = field(default_factory=lambda: Path("data/checkpoints"))
    min_disk_free_bytes: int = 2 * 1024 * 1024 * 1024  # 2 GB minimum free disk space threshold
    watchdog_timeout_seconds: float = 60.0  # Max seconds without messages before flagging silent failure
    ws_ping_interval: float = 20.0  # WebSocket ping frequency
    ws_ping_timeout: float = 10.0  # WebSocket ping response deadline
    collector_version: str = "v10c.1"
    schema_version: str = "1.0.0"

    # Absolute safety & data integrity invariants
    allow_synthetic_fallback: bool = False  # NEVER substitute synthetic/simulated data on failure
    cost_usd: float = 0.0
    requires_api_key: bool = False
    requires_payment: bool = False
    paper_trading_only: bool = True
    use_live_jev: bool = False
    leverage: float = 1.0
    live_orders: int = 0
