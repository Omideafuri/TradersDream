"""Paginated Backfill Engine for Phase 9 independent data acquisition.

Provides deterministic, resilient historical market data downloads with:
- Checkpointing and resumability.
- Rate-limit handling and exponential backoff.
- Per-batch OHLC and timestamp validation.
- Duplicate elimination and chronological sorting.
- Detailed audit logging of every HTTP request.
"""

import asyncio
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import time
from typing import Dict, List, Optional, Any, Callable
import pandas as pd
import numpy as np

from phase9.data_quality import audit_timestamps, audit_ohlc
from phase9.ingestion.base import DataSourceAdapter, NormalizedMarketData
from phase9.provenance import compute_file_sha256

logger = logging.getLogger(__name__)


class BackfillError(Exception):
    """Raised when backfill encounters an unrecoverable error."""
    pass


class PaginatedBackfillEngine:
    """Orchestrates paginated downloads of historical candle series."""

    def __init__(
        self,
        adapter: DataSourceAdapter,
        checkpoint_dir: Path | str = "phase9/manifests/backfill_checkpoints",
        batch_limit: int = 1000,
        rate_limit_delay_seconds: float = 0.08,
        max_retries: int = 4,
    ):
        self.adapter = adapter
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.batch_limit = batch_limit
        self.rate_limit_delay_seconds = rate_limit_delay_seconds
        self.max_retries = max_retries
        self.request_logs: List[Dict[str, Any]] = []

    def _get_checkpoint_path(self, symbol: str, interval: str) -> Path:
        clean_sym = symbol.upper().replace("/", "").replace("-", "")
        return self.checkpoint_dir / f"checkpoint_{clean_sym}_{interval}.json"

    def load_checkpoint(self, symbol: str, interval: str) -> Dict[str, Any]:
        path = self._get_checkpoint_path(symbol, interval)
        if path.is_file():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"symbol": symbol, "interval": interval, "oldest_ts": None, "total_downloaded": 0}

    def save_checkpoint(self, symbol: str, interval: str, oldest_ts: int, total_downloaded: int) -> None:
        path = self._get_checkpoint_path(symbol, interval)
        data = {
            "symbol": symbol,
            "interval": interval,
            "oldest_ts": oldest_ts,
            "total_downloaded": total_downloaded,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    async def fetch_batch_with_retry(
        self,
        symbol: str,
        interval: str,
        limit: int,
        end_ts: Optional[int],
    ) -> NormalizedMarketData:
        """Fetches a single batch with exponential backoff on transient errors."""
        last_exception = None
        for attempt in range(1, self.max_retries + 1):
            start_time = time.time()
            try:
                data = await self.adapter.download_candles(
                    symbol=symbol,
                    interval=interval,
                    limit=limit,
                    end_ts=end_ts,
                )
                elapsed_ms = int((time.time() - start_time) * 1000)
                self.request_logs.append({
                    "symbol": symbol,
                    "interval": interval,
                    "end_ts": end_ts,
                    "attempt": attempt,
                    "rows_received": data.row_count,
                    "elapsed_ms": elapsed_ms,
                    "status": "SUCCESS" if data.is_valid else "VALIDATION_FAILED",
                })
                if not data.is_valid:
                    raise ValueError(f"Batch validation failed: {data.validation_notes}")
                return data
            except Exception as e:
                last_exception = e
                elapsed_ms = int((time.time() - start_time) * 1000)
                self.request_logs.append({
                    "symbol": symbol,
                    "interval": interval,
                    "end_ts": end_ts,
                    "attempt": attempt,
                    "rows_received": 0,
                    "elapsed_ms": elapsed_ms,
                    "status": f"ERROR_{type(e).__name__}",
                })
                if attempt < self.max_retries:
                    backoff = (2 ** (attempt - 1)) * 0.25
                    await asyncio.sleep(backoff)

        raise BackfillError(f"Failed to fetch batch for {symbol} after {self.max_retries} attempts: {last_exception}")

    async def backfill(
        self,
        symbol: str,
        interval: str = "5m",
        target_bars: int = 10000,
        output_file: Optional[Path | str] = None,
        resume: bool = True,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> pd.DataFrame:
        """Paginates backwards in time to acquire target_bars of candles."""
        collected_frames: List[pd.DataFrame] = []
        oldest_ts: Optional[int] = None
        total_collected = 0

        if resume:
            ckpt = self.load_checkpoint(symbol, interval)
            oldest_ts = ckpt.get("oldest_ts")
            # If an existing partial output exists, load it
            if output_file and Path(output_file).is_file():
                try:
                    existing_df = pd.read_csv(output_file)
                    if not existing_df.empty and "timestamp" in existing_df.columns:
                        collected_frames.append(existing_df)
                        total_collected = len(existing_df)
                        oldest_ts = int(existing_df["timestamp"].min()) - 1
                except Exception:
                    pass

        while total_collected < target_bars:
            needed = target_bars - total_collected
            batch_size = min(self.batch_limit, needed)

            batch_data = await self.fetch_batch_with_retry(
                symbol=symbol,
                interval=interval,
                limit=batch_size,
                end_ts=oldest_ts,
            )

            if batch_data.df.empty:
                logger.info(f"No more historical bars available from adapter for {symbol}.")
                break

            collected_frames.append(batch_data.df)
            new_oldest = int(batch_data.df["timestamp"].min())

            # Guard against infinite pagination loop
            if oldest_ts is not None and new_oldest >= oldest_ts:
                logger.warning(f"Pagination did not advance (oldest={oldest_ts}, new_oldest={new_oldest}). Stopping.")
                break

            oldest_ts = new_oldest - 1
            total_collected += len(batch_data.df)

            self.save_checkpoint(symbol, interval, oldest_ts=oldest_ts, total_downloaded=total_collected)

            if progress_callback:
                progress_callback(total_collected, target_bars)

            await asyncio.sleep(self.rate_limit_delay_seconds)

        if not collected_frames:
            return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

        full_df = pd.concat(collected_frames, ignore_index=True)
        # Sort and deduplicate
        full_df.drop_duplicates(subset=["timestamp"], inplace=True)
        full_df.sort_values("timestamp", inplace=True)
        full_df.reset_index(drop=True, inplace=True)

        # Truncate to target_bars if we over-fetched
        if len(full_df) > target_bars:
            full_df = full_df.iloc[-target_bars:].reset_index(drop=True)

        if output_file:
            out_p = Path(output_file)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            full_df.to_csv(out_p, index=False)

        return full_df
