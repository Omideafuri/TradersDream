"""OKX public market data adapter for Phase 9."""

from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import httpx
import pandas as pd

from phase9.ingestion.base import (
    DataSourceAdapter,
    SourceDiscoveryResult,
    NormalizedMarketData,
)


class OKXAdapter(DataSourceAdapter):
    """Ingestion adapter for OKX public v5 REST API."""

    BASE_URL = "https://www.okx.com/api/v5"

    SYMBOL_MAP = {
        "BTCUSDT": "BTC-USDT",
        "ETHUSDT": "ETH-USDT",
        "SOLUSDT": "SOL-USDT",
    }

    INTERVAL_MAP = {
        "1m": "1m",
        "5m": "5m",
        "15m": "15m",
        "30m": "30m",
        "1h": "1H",
        "4h": "4H",
        "1d": "1D",
    }

    def get_source_name(self) -> str:
        return "OKX"

    def _resolve_inst_id(self, symbol: str) -> str:
        cleaned = symbol.upper().replace("/", "").replace("-", "")
        if cleaned in self.SYMBOL_MAP:
            return self.SYMBOL_MAP[cleaned]
        if "-" in symbol:
            return symbol.upper()
        return f"{cleaned[:3]}-USDT"

    async def discover(self) -> SourceDiscoveryResult:
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                resp = await client.get(f"{self.BASE_URL}/public/time")
                if resp.status_code == 200 and resp.json().get("code") == "0":
                    status = "AVAILABLE"
                else:
                    status = f"HTTP_{resp.status_code}"
        except Exception as e:
            status = f"ERROR_{type(e).__name__}"

        return SourceDiscoveryResult(
            source=self.get_source_name(),
            status=status,
            available_assets=["BTC-USDT", "ETH-USDT", "SOL-USDT", "BTC-USDT-SWAP"],
            available_time_range="Multi-month history accessible via paginated klines/history-candles",
            available_timeframes=["1m", "5m", "15m", "30m", "1h", "4h", "1d"],
            microstructure_available={
                "orderbook_l2": True,
                "orderbook_l3": False,
                "trade_flow": True,
                "funding_rate": True,  # Via perpetual SWAP endpoint
                "open_interest": True,
            },
            rate_limit="OKX public tier: 20 requests / 2 seconds",
            data_format="JSON REST (Unix ms timestamp)",
            license_access_notes="Public API access without API keys. Governed by OKX open API terms.",
        )

    async def download_candles(
        self,
        symbol: str = "BTCUSDT",
        interval: str = "5m",
        limit: int = 300,
        start_ts: Optional[int] = None,
        end_ts: Optional[int] = None,
    ) -> NormalizedMarketData:
        inst_id = self._resolve_inst_id(symbol)
        bar_param = self.INTERVAL_MAP.get(interval, "5m")
        url = f"{self.BASE_URL}/market/candles"

        params: Dict[str, Any] = {"instId": inst_id, "bar": bar_param, "limit": min(limit, 300)}
        if end_ts:
            params["after"] = str(end_ts)  # OKX uses 'after' for pagination back in time

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

        raw_candles = data.get("data", [])
        rows = []
        for c in raw_candles:
            # OKX format: [ts, o, h, l, c, vol, volCcy, volCcyQuote, confirm]
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
            symbol=inst_id,
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
        inst_id = self._resolve_inst_id(symbol)
        url = f"{self.BASE_URL}/market/books"
        params = {"instId": inst_id, "sz": min(depth, 50)}

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

        book_data = data.get("data", [{}])[0]
        ts_now = int(book_data.get("ts", datetime.now(timezone.utc).timestamp() * 1000))
        rows = []

        bids = book_data.get("bids", [])[:depth]
        for i, b in enumerate(bids):
            rows.append({
                "timestamp": ts_now,
                "side": "BID",
                "price": float(b[0]),
                "quantity": float(b[1]),
                "level": i + 1,
            })

        asks = book_data.get("asks", [])[:depth]
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
            symbol=inst_id,
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
        inst_id = self._resolve_inst_id(symbol)
        url = f"{self.BASE_URL}/market/trades"
        params = {"instId": inst_id, "limit": min(limit, 100)}

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

        raw_trades = data.get("data", [])
        rows = []
        for t in raw_trades[:limit]:
            rows.append({
                "timestamp": int(t["ts"]),
                "price": float(t["px"]),
                "quantity": float(t["sz"]),
                "side": t["side"].upper(),  # buy or sell
                "trade_id": str(t["tradeId"]),
            })

        df = pd.DataFrame(rows)
        if not df.empty:
            df.sort_values("timestamp", inplace=True)
            df.reset_index(drop=True, inplace=True)

        is_valid, notes = self.validate_normalized_data(df, "TRADE_FLOW")
        sha256_hash = self.compute_df_sha256(df) if not df.empty else ""

        return NormalizedMarketData(
            symbol=inst_id,
            instrument_type="TRADE_FLOW",
            timeframe="tick",
            df=df,
            raw_payload=raw_trades[:3] if raw_trades else [],
            row_count=len(df),
            sha256=sha256_hash,
            is_valid=is_valid,
            validation_notes=notes,
        )

    async def download_funding_rate(self, symbol: str = "BTCUSDT") -> NormalizedMarketData:
        inst_id = self._resolve_inst_id(symbol)
        swap_id = f"{inst_id}-SWAP"
        url = f"{self.BASE_URL}/public/funding-rate"
        params = {"instId": swap_id}

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

        rates = data.get("data", [])
        rows = []
        for r in rates:
            rows.append({
                "timestamp": int(r.get("fundingTime", 0)),
                "funding_rate": float(r.get("fundingRate", 0.0)),
            })

        df = pd.DataFrame(rows)
        is_valid, notes = self.validate_normalized_data(df, "FUNDING")
        sha256_hash = self.compute_df_sha256(df) if not df.empty else ""

        return NormalizedMarketData(
            symbol=swap_id,
            instrument_type="FUNDING",
            timeframe="8h",
            df=df,
            raw_payload=rates,
            row_count=len(df),
            sha256=sha256_hash,
            is_valid=is_valid,
            validation_notes=notes,
        )
