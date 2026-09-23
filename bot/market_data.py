"""Market data collection module for Crypto Trading Bot - Phase 1.

Collects public OHLCV candle data without requiring authenticated API keys.
Default target: BTC/USDT 5-minute candles.
"""

from typing import Optional
import httpx
import pandas as pd
import numpy as np


class MarketDataFetcher:
    """Fetches public market candle data from cryptocurrency exchange public endpoints."""

    BINANCE_GLOBAL_KLINES_URL = "https://api.binance.com/api/v3/klines"
    BINANCE_US_KLINES_URL = "https://api.binance.us/api/v3/klines"
    BINANCE_KLINES_URL = BINANCE_US_KLINES_URL  # Default to US endpoint to prevent HTTP 451 geo-restrictions

    def __init__(self, timeout_seconds: float = 10.0, use_binance_us: bool = True):
        self.timeout_seconds = timeout_seconds
        self.use_binance_us = use_binance_us
        self.endpoint_url = self.BINANCE_US_KLINES_URL if use_binance_us else self.BINANCE_GLOBAL_KLINES_URL

    async def fetch_klines(
        self,
        symbol: str = "BTCUSDT",
        interval: str = "5m",
        limit: int = 250,
    ) -> pd.DataFrame:
        """Asynchronously fetches kline/candlestick data from public endpoint.
        
        Args:
            symbol: Trading pair symbol, e.g. "BTCUSDT".
            interval: Kline interval, e.g. "5m".
            limit: Number of candles (default 250 to allow sufficient EMA200 warmup).
            
        Returns:
            pd.DataFrame with columns: ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        """
        params = {
            "symbol": symbol.upper(),
            "interval": interval,
            "limit": limit,
        }

        # Use unauthenticated public request
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.get(self.endpoint_url, params=params)
            response.raise_for_status()
            raw_candles = response.json()

        return self.parse_klines(raw_candles)

    @staticmethod
    def parse_klines(raw_candles: list) -> pd.DataFrame:
        """Parses raw exchange candle array into a standardized DataFrame.
        
        Binance Kline format:
        [
          0: Open time,
          1: Open,
          2: High,
          3: Low,
          4: Close,
          5: Volume,
          6: Close time,
          ...
        ]
        """
        if not raw_candles:
            raise ValueError("Received empty candle dataset")

        rows = []
        for c in raw_candles:
            rows.append({
                "timestamp": int(c[0]),
                "open": float(c[1]),
                "high": float(c[2]),
                "low": float(c[3]),
                "close": float(c[4]),
                "volume": float(c[5]),
            })

        df = pd.DataFrame(rows)
        df.sort_values("timestamp", inplace=True)
        df.reset_index(drop=True, inplace=True)
        return df

    @staticmethod
    def generate_synthetic_klines(
        count: int = 250,
        start_price: float = 65000.0,
        interval_ms: int = 300_000,
        seed: Optional[int] = 42,
    ) -> pd.DataFrame:
        """Generates deterministic synthetic OHLCV candles for offline testing and simulations."""
        rng = np.random.default_rng(seed)
        base_time = 1700000000000

        rows = []
        current_close = start_price
        for i in range(count):
            ret = rng.normal(0.0002, 0.003)
            open_p = current_close
            close_p = open_p * (1.0 + ret)
            high_p = max(open_p, close_p) * (1.0 + abs(rng.normal(0.001, 0.001)))
            low_p = min(open_p, close_p) * (1.0 - abs(rng.normal(0.001, 0.001)))
            vol = float(rng.uniform(10.0, 50.0))
            rows.append({
                "timestamp": base_time + i * interval_ms,
                "open": round(open_p, 2),
                "high": round(high_p, 2),
                "low": round(low_p, 2),
                "close": round(close_p, 2),
                "volume": round(vol, 4),
            })
            current_close = close_p

        return pd.DataFrame(rows)
