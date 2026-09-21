"""Historical Dataset Acquisition, Caching, and Metadata Loader.

Acquires and caches multi-month historical 5-minute candle datasets from public exchange endpoints:
- Target Assets: BTCUSDT, ETHUSDT, SOLUSDT.
- Endpoint: Binance Public REST API (unauthenticated).
- Handles pagination, rate-limit politeness, local disk caching, and SHA256 dataset integrity hashing.
- Fallback to existing historical data if network is unavailable.
"""

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Dict, Any, List, Optional, Tuple
import httpx
import pandas as pd
import numpy as np


@dataclass
class DatasetMetadata:
    symbol: str
    timeframe: str
    source: str
    acquisition_date: str
    start_timestamp: int
    end_timestamp: int
    start_iso: str
    end_iso: str
    candle_count: int
    sha256_hash: str
    file_path: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DatasetLoader:
    """Acquires, caches, and verifies multi-asset historical market data."""

    BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"

    def __init__(self, data_dir: str = "data/historical"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def compute_sha256(df: pd.DataFrame) -> str:
        """Computes a deterministic SHA256 hash of the DataFrame records."""
        content = df.to_csv(index=False).encode("utf-8")
        return hashlib.sha256(content).hexdigest()

    def fetch_paginated_klines(
        self,
        symbol: str = "BTCUSDT",
        interval: str = "5m",
        target_candles: int = 10000,
        batch_limit: int = 1000,
    ) -> pd.DataFrame:
        """Fetches historical candles backwards or sequentially using public Binance endpoints."""
        all_candles = []
        end_time = None
        fetched_count = 0

        with httpx.Client(timeout=15.0) as client:
            while fetched_count < target_candles:
                fetch_limit = min(batch_limit, target_candles - fetched_count)
                params: Dict[str, Any] = {
                    "symbol": symbol.upper(),
                    "interval": interval,
                    "limit": fetch_limit,
                }
                if end_time is not None:
                    params["endTime"] = end_time

                try:
                    response = client.get(self.BINANCE_KLINES_URL, params=params)
                    if response.status_code == 429:
                        # Back off on rate limit
                        time.sleep(2.0)
                        continue
                    response.raise_for_status()
                    batch = response.json()
                except Exception as e:
                    # If network fails midway, break and use what we have
                    break

                if not batch:
                    break

                # Binance returns ascending order in batch
                all_candles = batch + all_candles
                fetched_count += len(batch)
                # Next batch ends right before the first candle's open time
                first_open_time = int(batch[0][0])
                end_time = first_open_time - 1

                # Polite pause to respect exchange limits
                time.sleep(0.1)

        if not all_candles:
            raise RuntimeError(f"Failed to fetch any candles for {symbol}")

        # Parse into standard DataFrame
        rows = []
        seen_timestamps = set()
        for c in all_candles:
            ts = int(c[0])
            if ts in seen_timestamps:
                continue
            seen_timestamps.add(ts)
            rows.append({
                "timestamp": ts,
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

    def load_or_fetch_dataset(
        self,
        symbol: str = "BTCUSDT",
        timeframe: str = "5m",
        target_candles: int = 10000,
        force_fetch: bool = False,
    ) -> Tuple[pd.DataFrame, DatasetMetadata]:
        """Loads dataset from local cache if present, otherwise attempts acquisition."""
        expanded_file = self.data_dir / f"{symbol}_{timeframe}_expanded.csv"
        baseline_file = self.data_dir / f"{symbol}_{timeframe}_candles.csv"

        df: Optional[pd.DataFrame] = None
        source_name = "LOCAL_CACHE"

        if not force_fetch:
            if expanded_file.exists():
                df = pd.read_csv(expanded_file)
                source_name = "LOCAL_EXPANDED_CACHE"
            elif baseline_file.exists():
                df = pd.read_csv(baseline_file)
                source_name = "LOCAL_BASELINE_CACHE"

        # If data not present or target not met and force_fetch enabled, fetch from network
        if df is None or (force_fetch and len(df) < target_candles):
            try:
                df = self.fetch_paginated_klines(
                    symbol=symbol,
                    interval=timeframe,
                    target_candles=target_candles,
                )
                source_name = "BINANCE_PUBLIC_REST_API"
                # Cache to expanded_file
                df.to_csv(expanded_file, index=False)
            except Exception:
                # Fallback to baseline if fetch failed
                if baseline_file.exists():
                    df = pd.read_csv(baseline_file)
                    source_name = "LOCAL_BASELINE_CACHE_FALLBACK"
                else:
                    raise

        # Ensure correct column types
        df["timestamp"] = df["timestamp"].astype(int)
        df["open"] = df["open"].astype(float)
        df["high"] = df["high"].astype(float)
        df["low"] = df["low"].astype(float)
        df["close"] = df["close"].astype(float)
        df["volume"] = df["volume"].astype(float)
        df.sort_values("timestamp", inplace=True)
        df.reset_index(drop=True, inplace=True)

        start_ts = int(df["timestamp"].iloc[0])
        end_ts = int(df["timestamp"].iloc[-1])
        start_iso = datetime.fromtimestamp(start_ts / 1000, tz=timezone.utc).isoformat()
        end_iso = datetime.fromtimestamp(end_ts / 1000, tz=timezone.utc).isoformat()
        sha256 = self.compute_sha256(df)

        meta = DatasetMetadata(
            symbol=symbol.upper(),
            timeframe=timeframe,
            source=source_name,
            acquisition_date=datetime.now(timezone.utc).isoformat(),
            start_timestamp=start_ts,
            end_timestamp=end_ts,
            start_iso=start_iso,
            end_iso=end_iso,
            candle_count=len(df),
            sha256_hash=sha256,
            file_path=str(expanded_file if expanded_file.exists() else baseline_file),
        )

        return df, meta
