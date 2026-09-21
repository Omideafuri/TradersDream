"""Base class and common data models for Phase 9 market data ingestion adapters."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import pandas as pd

from phase9.data_quality import audit_timestamps, audit_ohlc


@dataclass
class SourceDiscoveryResult:
    """Standardized discovery outcome for an external market data provider."""
    source: str
    status: str  # AVAILABLE, GEO_RESTRICTED, UNAVAILABLE, RATE_LIMITED
    available_assets: List[str]
    available_time_range: str
    available_timeframes: List[str]
    microstructure_available: Dict[str, bool]
    rate_limit: str
    data_format: str
    license_access_notes: str
    checked_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class NormalizedMarketData:
    """Canonical representation of ingested market data with both raw and normalized forms."""
    symbol: str
    instrument_type: str  # CANDLE, ORDERBOOK_L2, TRADE_FLOW, FUNDING
    timeframe: str
    df: pd.DataFrame
    raw_payload: Any
    row_count: int
    sha256: str
    is_valid: bool
    validation_notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "instrument_type": self.instrument_type,
            "timeframe": self.timeframe,
            "row_count": self.row_count,
            "sha256": self.sha256,
            "is_valid": self.is_valid,
            "validation_notes": self.validation_notes,
        }


class DataSourceAdapter(ABC):
    """Abstract base class for independent market data ingestion adapters."""

    def __init__(self, timeout_seconds: float = 10.0):
        self.timeout_seconds = timeout_seconds

    @abstractmethod
    def get_source_name(self) -> str:
        """Returns the canonical name of the data source."""
        pass

    @abstractmethod
    async def discover(self) -> SourceDiscoveryResult:
        """Probes exchange endpoint connectivity, supported assets, and capabilities."""
        pass

    @abstractmethod
    async def download_candles(
        self,
        symbol: str,
        interval: str = "5m",
        limit: int = 300,
        start_ts: Optional[int] = None,
        end_ts: Optional[int] = None,
    ) -> NormalizedMarketData:
        """Downloads historical candlestick data and returns normalized DataFrame."""
        pass

    @abstractmethod
    async def download_orderbook(
        self,
        symbol: str,
        depth: int = 50,
    ) -> NormalizedMarketData:
        """Downloads current L2 order book depth snapshot."""
        pass

    @abstractmethod
    async def download_trades(
        self,
        symbol: str,
        limit: int = 100,
    ) -> NormalizedMarketData:
        """Downloads recent tick/trade flow with aggressor classification."""
        pass

    def validate_normalized_data(self, df: pd.DataFrame, instrument_type: str) -> Tuple[bool, str]:
        """Validates canonical schema and basic integrity."""
        if df.empty:
            return False, "Empty dataset received"

        if instrument_type == "CANDLE":
            required = ["timestamp", "open", "high", "low", "close", "volume"]
            for col in required:
                if col not in df.columns:
                    return False, f"Missing column '{col}' in candle dataset"
            ts_res = audit_timestamps(df)
            ohlc_res = audit_ohlc(df)
            if not ts_res.is_monotonic:
                return False, "Timestamps are not strictly monotonic"
            if not ohlc_res.is_valid:
                return False, f"OHLC bounds violation: H={ohlc_res.violations_high}, L={ohlc_res.violations_low}"
            return True, "Valid candle dataset"

        elif instrument_type == "ORDERBOOK_L2":
            required = ["timestamp", "side", "price", "quantity", "level"]
            for col in required:
                if col not in df.columns:
                    return False, f"Missing column '{col}' in orderbook dataset"
            return True, "Valid orderbook L2 dataset"

        elif instrument_type == "TRADE_FLOW":
            required = ["timestamp", "price", "quantity", "side", "trade_id"]
            for col in required:
                if col not in df.columns:
                    return False, f"Missing column '{col}' in trade flow dataset"
            return True, "Valid trade flow dataset"

        elif instrument_type == "FUNDING":
            required = ["timestamp", "funding_rate"]
            for col in required:
                if col not in df.columns:
                    return False, f"Missing column '{col}' in funding dataset"
            return True, "Valid funding dataset"

        return True, "Valid dataset"

    @staticmethod
    def compute_df_sha256(df: pd.DataFrame) -> str:
        """Computes deterministic SHA256 of DataFrame contents."""
        csv_bytes = df.to_csv(index=False).encode("utf-8")
        return hashlib.sha256(csv_bytes).hexdigest()

