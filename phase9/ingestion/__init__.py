"""Phase 9 Ingestion subsystem.

Provides standardized, rate-limited, and validated market data source adapters
for public cryptocurrency exchanges without requiring authenticated trading credentials.
"""

from phase9.ingestion.base import DataSourceAdapter, SourceDiscoveryResult, NormalizedMarketData
from phase9.ingestion.coinbase import CoinbaseAdapter
from phase9.ingestion.kraken import KrakenAdapter
from phase9.ingestion.okx import OKXAdapter
from phase9.ingestion.binance_us import BinanceUSAdapter

__all__ = [
    "DataSourceAdapter",
    "SourceDiscoveryResult",
    "NormalizedMarketData",
    "CoinbaseAdapter",
    "KrakenAdapter",
    "OKXAdapter",
    "BinanceUSAdapter",
]
