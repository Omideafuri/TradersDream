"""Binance.US public market data adapter for Phase 9."""

from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import httpx
import pandas as pd

from phase9.ingestion.base import (
    DataSourceAdapter,
    SourceDiscoveryResult,
    NormalizedMarketData,
)


class BinanceUSAdapter(DataSourceAdapter):
    """Ingestion adapter for Binance.US public v3 REST API."""

    BASE_URL = "https://api.binance.us/api/v3"

    def get_source_name(self) -> str:
        return "BINANCE_US"

    async def discover(self) -> SourceDiscoveryResult:
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                resp = await client.get(f"{self.BASE_URL}/ping")
                if resp.status_code == 200:
                    status = "AVAILABLE"
                else:
                    status = f"HTTP_{resp.status_code}"
        except Exception as e:
            status = f"ERROR_{type(e).__name__}"

        return SourceDiscoveryResult(
            source=self.get_source_name(),
            status=status,
            available_assets=["BTCUSDT", "ETHUSDT", "SOLUSDT", "BTCUSD", "ETHUSD"],
            available_time_range="Multi-year public history accessible via paginated klines endpoint",
            available_timeframes=["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "1d"],
            microstructure_available={
                "orderbook_l2": True,
                "orderbook_l3": False,
                "trade_flow": True,
                "funding_rate": False,  # Spot only
                "open_interest": False,
            },
            rate_limit="Binance US IP limit: 1200 weight/minute",
            data_format="JSON REST (Unix ms timestamp)",
            license_access_notes="Public API access without auth keys. Regulated US spot exchange.",
        )

    async def download_candles(
        self,
        symbol: str = "BTCUSDT",
        interval: str = "5m",
        limit: int = 300,
        start_ts: Optional[int] = None,
        end_ts: Optional[int] = None,
    ) -> NormalizedMarketData:
        sym = symbol.upper().replace("-", "").replace("/", "")
        url = f"{self.BASE_URL}/klines"

        params: Dict[str, Any] = {"symbol": sym, "interval": interval, "limit": min(limit, 1000)}
        if start_ts:
            params["startTime"] = start_ts
        if end_ts:
            params["endTime"] = end_ts

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            raw_candles = resp.json()

        rows = []
        for c in raw_candles:
            # [open_time, open, high, low, close, volume, close_time, ...]
            rows.append({
                "timestamp": int(c[0]),
                "open": float(c[1]),
                "high": float(c[2]),
                "low": float(c[3]),
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
            symbol=sym,
            instrument_type="CANDLE",
            timeframe=interval,
            df=df,
            raw_payload=raw_candles[:5] if raw_candles else [],
            row_count=len(df),
            sha256=sha256_hash,
            is_valid=is_valid,
            validation_notes=notes,
        )

    async def download_orderbook(self, symbol: str = "BTCUSDT", depth: int = 50) -> NormalizedMarketData:
        sym = symbol.upper().replace("-", "").replace("/", "")
        url = f"{self.BASE_URL}/depth"
        params = {"symbol": sym, "limit": min(depth, 100)}

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            book = resp.json()

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
            symbol=sym,
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
        sym = symbol.upper().replace("-", "").replace("/", "")
        url = f"{self.BASE_URL}/trades"
        params = {"symbol": sym, "limit": min(limit, 1000)}

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            trades = resp.json()

        rows = []
        for t in trades[:limit]:
            # isBuyerMaker: if True, buyer is maker -> aggressor was seller (SELL)
            # if False, buyer is taker -> aggressor was buyer (BUY)
            aggressor_side = "SELL" if t.get("isBuyerMaker", False) else "BUY"
            rows.append({
                "timestamp": int(t["time"]),
                "price": float(t["price"]),
                "quantity": float(t["qty"]),
                "side": aggressor_side,
                "trade_id": str(t["id"]),
            })

        df = pd.DataFrame(rows)
        if not df.empty:
            df.sort_values("timestamp", inplace=True)
            df.reset_index(drop=True, inplace=True)

        is_valid, notes = self.validate_normalized_data(df, "TRADE_FLOW")
        sha256_hash = self.compute_df_sha256(df) if not df.empty else ""

        return NormalizedMarketData(
            symbol=sym,
            instrument_type="TRADE_FLOW",
            timeframe="tick",
            df=df,
            raw_payload=trades[:3] if trades else [],
            row_count=len(df),
            sha256=sha256_hash,
            is_valid=is_valid,
            validation_notes=notes,
        )
