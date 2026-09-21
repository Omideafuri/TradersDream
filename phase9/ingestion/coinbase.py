"""Coinbase public market data adapter for Phase 9."""

from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import httpx
import pandas as pd

from phase9.ingestion.base import (
    DataSourceAdapter,
    SourceDiscoveryResult,
    NormalizedMarketData,
)


class CoinbaseAdapter(DataSourceAdapter):
    """Ingestion adapter for Coinbase Exchange public REST API."""

    BASE_URL = "https://api.exchange.coinbase.com"

    SYMBOL_MAP = {
        "BTCUSDT": "BTC-USDT",
        "BTCUSD": "BTC-USD",
        "ETHUSDT": "ETH-USDT",
        "ETHUSD": "ETH-USD",
        "SOLUSDT": "SOL-USDT",
        "SOLUSD": "SOL-USD",
    }

    GRANULARITY_MAP = {
        "1m": 60,
        "5m": 300,
        "15m": 900,
        "1h": 3600,
        "6h": 21600,
        "1d": 86400,
    }

    def get_source_name(self) -> str:
        return "COINBASE"

    def _resolve_product_id(self, symbol: str) -> str:
        cleaned = symbol.upper().replace("/", "").replace("-", "")
        if cleaned in self.SYMBOL_MAP:
            return self.SYMBOL_MAP[cleaned]
        if "-" in symbol:
            return symbol.upper()
        # Fallback to USD pair if USDT unavailable or vice-versa
        return f"{cleaned[:3]}-USD"

    async def discover(self) -> SourceDiscoveryResult:
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                resp = await client.get(f"{self.BASE_URL}/time")
                if resp.status_code == 200:
                    status = "AVAILABLE"
                else:
                    status = f"HTTP_{resp.status_code}"
        except Exception as e:
            status = f"ERROR_{type(e).__name__}"

        return SourceDiscoveryResult(
            source=self.get_source_name(),
            status=status,
            available_assets=["BTC-USD", "BTC-USDT", "ETH-USD", "ETH-USDT", "SOL-USD"],
            available_time_range="Multi-year public history accessible via paginated granularity requests",
            available_timeframes=["1m", "5m", "15m", "1h", "6h", "1d"],
            microstructure_available={
                "orderbook_l2": True,
                "orderbook_l3": True,
                "trade_flow": True,
                "funding_rate": False,  # Spot only
                "open_interest": False,
            },
            rate_limit="Up to 10-15 requests/second public",
            data_format="JSON REST (Unix seconds timestamp)",
            license_access_notes="Public API access without auth keys. Commercial usage governed by Coinbase API terms.",
        )

    async def download_candles(
        self,
        symbol: str = "BTCUSDT",
        interval: str = "5m",
        limit: int = 300,
        start_ts: Optional[int] = None,
        end_ts: Optional[int] = None,
    ) -> NormalizedMarketData:
        product_id = self._resolve_product_id(symbol)
        granularity = self.GRANULARITY_MAP.get(interval, 300)
        url = f"{self.BASE_URL}/products/{product_id}/candles"

        params: Dict[str, Any] = {"granularity": granularity}
        if start_ts:
            params["start"] = datetime.fromtimestamp(start_ts / 1000.0, timezone.utc).isoformat()
        if end_ts:
            params["end"] = datetime.fromtimestamp(end_ts / 1000.0, timezone.utc).isoformat()

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            raw_candles = resp.json()

        # Coinbase format: [ [ time, low, high, open, close, volume ], ... ] (newest first)
        rows = []
        for c in raw_candles:
            rows.append({
                "timestamp": int(c[0]) * 1000,
                "open": float(c[3]),
                "high": float(c[2]),
                "low": float(c[1]),
                "close": float(c[4]),
                "volume": float(c[5]),
            })

        df = pd.DataFrame(rows)
        if not df.empty:
            df.sort_values("timestamp", inplace=True)
            df.drop_duplicates(subset=["timestamp"], inplace=True)
            df.reset_index(drop=True, inplace=True)

        is_valid, notes = self.validate_normalized_data(df, "CANDLE")
        sha256_hash = self.compute_df_sha256(df) if not df.empty else ""

        return NormalizedMarketData(
            symbol=product_id,
            instrument_type="CANDLE",
            timeframe=interval,
            df=df,
            raw_payload=raw_candles[:5],
            row_count=len(df),
            sha256=sha256_hash,
            is_valid=is_valid,
            validation_notes=notes,
        )

    async def download_orderbook(self, symbol: str = "BTCUSDT", depth: int = 50) -> NormalizedMarketData:
        product_id = self._resolve_product_id(symbol)
        url = f"{self.BASE_URL}/products/{product_id}/book?level=2"

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            book = resp.json()

        # book has 'bids': [[price, size, num_orders], ...], 'asks': [...]
        ts_now = int(datetime.now(timezone.utc).timestamp() * 1000)
        rows = []

        bids = book.get("bids", [])[:depth]
        for i, b in enumerate(bids):
            rows.append({
                "timestamp": ts_now,
                "side": "BID",
                "price": float(b[0]),
                "quantity": float(b[1]),
                "level": i + 1,
            })

        asks = book.get("asks", [])[:depth]
        for i, a in enumerate(asks):
            rows.append({
                "timestamp": ts_now,
                "side": "ASK",
                "price": float(a[0]),
                "quantity": float(a[1]),
                "level": i + 1,
            })

        df = pd.DataFrame(rows)
        is_valid, notes = self.validate_normalized_data(df, "ORDERBOOK_L2")
        sha256_hash = self.compute_df_sha256(df) if not df.empty else ""

        return NormalizedMarketData(
            symbol=product_id,
            instrument_type="ORDERBOOK_L2",
            timeframe="snapshot",
            df=df,
            raw_payload={"bids_count": len(bids), "asks_count": len(asks)},
            row_count=len(df),
            sha256=sha256_hash,
            is_valid=is_valid,
            validation_notes=notes,
        )

    async def download_trades(self, symbol: str = "BTCUSDT", limit: int = 100) -> NormalizedMarketData:
        product_id = self._resolve_product_id(symbol)
        url = f"{self.BASE_URL}/products/{product_id}/trades"

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            trades = resp.json()

        rows = []
        for t in trades[:limit]:
            # parse ISO timestamp to epoch ms
            dt = datetime.fromisoformat(t["time"].replace("Z", "+00:00"))
            ts_ms = int(dt.timestamp() * 1000)
            rows.append({
                "timestamp": ts_ms,
                "price": float(t["price"]),
                "quantity": float(t["size"]),
                "side": t["side"].upper(),  # BUY or SELL
                "trade_id": str(t["trade_id"]),
            })

        df = pd.DataFrame(rows)
        if not df.empty:
            df.sort_values("timestamp", inplace=True)
            df.reset_index(drop=True, inplace=True)

        is_valid, notes = self.validate_normalized_data(df, "TRADE_FLOW")
        sha256_hash = self.compute_df_sha256(df) if not df.empty else ""

        return NormalizedMarketData(
            symbol=product_id,
            instrument_type="TRADE_FLOW",
            timeframe="tick",
            df=df,
            raw_payload=trades[:3],
            row_count=len(df),
            sha256=sha256_hash,
            is_valid=is_valid,
            validation_notes=notes,
        )
