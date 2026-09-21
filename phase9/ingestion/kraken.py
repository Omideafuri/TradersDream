"""Kraken public market data adapter for Phase 9."""

from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import httpx
import pandas as pd

from phase9.ingestion.base import (
    DataSourceAdapter,
    SourceDiscoveryResult,
    NormalizedMarketData,
)


class KrakenAdapter(DataSourceAdapter):
    """Ingestion adapter for Kraken public REST API."""

    BASE_URL = "https://api.kraken.com/0/public"

    SYMBOL_MAP = {
        "BTCUSDT": "XBTUSDT",
        "BTCUSD": "XXBTZUSD",
        "ETHUSDT": "ETHUSDT",
        "ETHUSD": "XETHZUSD",
        "SOLUSDT": "SOLUSDT",
        "SOLUSD": "SOLUSD",
    }

    INTERVAL_MAP = {
        "1m": 1,
        "5m": 5,
        "15m": 15,
        "30m": 30,
        "1h": 60,
        "4h": 240,
        "1d": 1440,
    }

    def get_source_name(self) -> str:
        return "KRAKEN"

    def _resolve_pair(self, symbol: str) -> str:
        cleaned = symbol.upper().replace("/", "").replace("-", "")
        return self.SYMBOL_MAP.get(cleaned, cleaned)

    async def discover(self) -> SourceDiscoveryResult:
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                resp = await client.get(f"{self.BASE_URL}/SystemStatus")
                if resp.status_code == 200 and resp.json().get("result", {}).get("status") == "online":
                    status = "AVAILABLE"
                else:
                    status = f"HTTP_{resp.status_code}"
        except Exception as e:
            status = f"ERROR_{type(e).__name__}"

        return SourceDiscoveryResult(
            source=self.get_source_name(),
            status=status,
            available_assets=["XXBTZUSD", "XBTUSDT", "XETHZUSD", "ETHUSDT", "SOLUSD", "SOLUSDT"],
            available_time_range="Rolling 720 bars accessible via standard public OHLC endpoint",
            available_timeframes=["1m", "5m", "15m", "30m", "1h", "4h", "1d"],
            microstructure_available={
                "orderbook_l2": True,
                "orderbook_l3": False,
                "trade_flow": True,
                "funding_rate": False,  # Spot only
                "open_interest": False,
            },
            rate_limit="Kraken tier: 15-20 calls counter decay",
            data_format="JSON REST (Unix float timestamp)",
            license_access_notes="Public API access. Subject to Kraken rate limits and API terms.",
        )

    async def download_candles(
        self,
        symbol: str = "BTCUSDT",
        interval: str = "5m",
        limit: int = 300,
        start_ts: Optional[int] = None,
        end_ts: Optional[int] = None,
    ) -> NormalizedMarketData:
        pair = self._resolve_pair(symbol)
        interval_val = self.INTERVAL_MAP.get(interval, 5)
        url = f"{self.BASE_URL}/OHLC"

        params: Dict[str, Any] = {"pair": pair, "interval": interval_val}
        if start_ts:
            params["since"] = int(start_ts / 1000.0)

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

        result = data.get("result", {})
        # Kraken returns key as pair name, excluding 'last'
        pair_key = next((k for k in result.keys() if k != "last"), None)
        raw_candles = result.get(pair_key, []) if pair_key else []

        rows = []
        for c in raw_candles:
            rows.append({
                "timestamp": int(float(c[0]) * 1000),
                "open": float(c[1]),
                "high": float(c[2]),
                "low": float(c[3]),
                "close": float(c[4]),
                "volume": float(c[6]),
            })

        df = pd.DataFrame(rows)
        if not df.empty:
            df.sort_values("timestamp", inplace=True)
            df.drop_duplicates(subset=["timestamp"], inplace=True)
            df.reset_index(drop=True, inplace=True)

        is_valid, notes = self.validate_normalized_data(df, "CANDLE")
        sha256_hash = self.compute_df_sha256(df) if not df.empty else ""

        return NormalizedMarketData(
            symbol=pair,
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
        pair = self._resolve_pair(symbol)
        url = f"{self.BASE_URL}/Depth"
        params = {"pair": pair, "count": depth}

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

        result = data.get("result", {})
        pair_key = next(iter(result.keys()), None)
        book = result.get(pair_key, {}) if pair_key else {}

        ts_now = int(datetime.now(timezone.utc).timestamp() * 1000)
        rows = []

        bids = book.get("bids", [])[:depth]
        for i, b in enumerate(bids):
            rows.append({
                "timestamp": int(float(b[2]) * 1000) if len(b) > 2 else ts_now,
                "side": "BID",
                "price": float(b[0]),
                "quantity": float(b[1]),
                "level": i + 1,
            })

        asks = book.get("asks", [])[:depth]
        for i, a in enumerate(asks):
            rows.append({
                "timestamp": int(float(a[2]) * 1000) if len(a) > 2 else ts_now,
                "side": "ASK",
                "price": float(a[0]),
                "quantity": float(a[1]),
                "level": i + 1,
            })

        df = pd.DataFrame(rows)
        is_valid, notes = self.validate_normalized_data(df, "ORDERBOOK_L2")
        sha256_hash = self.compute_df_sha256(df) if not df.empty else ""

        return NormalizedMarketData(
            symbol=pair,
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
        pair = self._resolve_pair(symbol)
        url = f"{self.BASE_URL}/Trades"
        params = {"pair": pair}

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

        result = data.get("result", {})
        pair_key = next((k for k in result.keys() if k != "last"), None)
        trades = result.get(pair_key, []) if pair_key else []

        rows = []
        for i, t in enumerate(trades[:limit]):
            # Kraken format: [price, volume, time, buy_sell, market_limit, misc, trade_id]
            ts_ms = int(float(t[2]) * 1000)
            side = "BUY" if t[3] == "b" else "SELL"
            trade_id = str(t[6]) if len(t) > 6 else f"trade_{i}"
            rows.append({
                "timestamp": ts_ms,
                "price": float(t[0]),
                "quantity": float(t[1]),
                "side": side,
                "trade_id": trade_id,
            })

        df = pd.DataFrame(rows)
        if not df.empty:
            df.sort_values("timestamp", inplace=True)
            df.reset_index(drop=True, inplace=True)

        is_valid, notes = self.validate_normalized_data(df, "TRADE_FLOW")
        sha256_hash = self.compute_df_sha256(df) if not df.empty else ""

        return NormalizedMarketData(
            symbol=pair,
            instrument_type="TRADE_FLOW",
            timeframe="tick",
            df=df,
            raw_payload=trades[:3] if trades else [],
            row_count=len(df),
            sha256=sha256_hash,
            is_valid=is_valid,
            validation_notes=notes,
        )
