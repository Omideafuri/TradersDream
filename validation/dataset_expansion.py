"""Multi-asset dataset discovery and expansion manager for Phase 3.

Supports BTCUSDT, ETHUSDT, SOLUSDT.
Detects available local datasets, audits coverage, and prepares multi-month historical feeds
while preserving strict causality invariants.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import pandas as pd

from backtest.dataset import DatasetManager, HistoricalDecision
from validation.data_quality import DatasetIntegrityChecker, DataQualityReport


@dataclass
class DatasetCoverage:
    symbol: str
    timeframe: str
    candle_count: int
    start_iso: str
    end_iso: str
    span_days: float
    is_valid: bool
    quality_report: DataQualityReport
    file_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "candle_count": self.candle_count,
            "start_iso": self.start_iso,
            "end_iso": self.end_iso,
            "span_days": round(self.span_days, 2),
            "is_valid": self.is_valid,
            "file_path": self.file_path,
        }


class MultiAssetDataManager:
    """Manages historical feeds across multiple cryptocurrency pairs."""

    SUPPORTED_ASSETS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

    DEFAULT_BASE_PRICES = {
        "BTCUSDT": 65000.0,
        "ETHUSDT": 3500.0,
        "SOLUSDT": 150.0,
    }

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or (Path("data") / "historical")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.base_mgr = DatasetManager(self.data_dir)

    def get_dataset_path(self, symbol: str, timeframe: str = "5m") -> Path:
        """Returns standard path to candle CSV for symbol and timeframe."""
        return self.data_dir / f"{symbol.upper()}_{timeframe}_candles.csv"

    def load_candles(self, symbol: str, timeframe: str = "5m") -> pd.DataFrame:
        """Loads candle CSV."""
        path = self.get_dataset_path(symbol, timeframe)
        if not path.exists():
            raise FileNotFoundError(f"Candles file not found at {path}")
        return pd.read_csv(path)

    def generate_standard_dataset(
        self,
        symbol: str,
        timeframe: str = "5m",
        count: int = 1500,
        seed: int = 42,
    ) -> pd.DataFrame:
        """Generates and persists standardized benchmark history."""
        sym = symbol.upper()
        base_p = self.DEFAULT_BASE_PRICES.get(sym, 1000.0)
        candles = DatasetManager.generate_synthetic_history(
            count=count,
            start_price=base_p,
            interval_minutes=5,
            seed=seed,
        )
        candle_file = self.get_dataset_path(sym, timeframe)
        candles.to_csv(candle_file, index=False)
        return candles

    def detect_coverage(self, symbol: str, timeframe: str = "5m") -> Optional[DatasetCoverage]:
        """Detects whether local historical candle data exists for the given asset and audits coverage."""
        candle_file = self.get_dataset_path(symbol, timeframe)
        if not candle_file.exists():
            return None

        df = pd.read_csv(candle_file)
        report = DatasetIntegrityChecker(df).run_all_checks()

        span_ms = report.end_timestamp - report.start_timestamp
        span_days = span_ms / (1000.0 * 86400.0) if span_ms > 0 else 0.0

        return DatasetCoverage(
            symbol=symbol.upper(),
            timeframe=timeframe,
            candle_count=report.total_candles,
            start_iso=report.start_iso,
            end_iso=report.end_iso,
            span_days=span_days,
            is_valid=report.is_valid,
            quality_report=report,
            file_path=str(candle_file),
        )

    def get_or_generate_dataset(
        self,
        symbol: str = "BTCUSDT",
        timeframe: str = "5m",
        target_candles: int = 1500,
        seed: int = 42,
    ) -> Tuple[pd.DataFrame, pd.DataFrame, List[HistoricalDecision]]:
        """Retrieves local historical data or generates deterministic multi-month history."""
        sym = symbol.upper()
        candle_file = self.get_dataset_path(sym, timeframe)
        decision_file = self.data_dir / f"{sym}_{timeframe}_decisions.csv"

        if candle_file.exists():
            candles = pd.read_csv(candle_file)
        else:
            candles = self.generate_standard_dataset(sym, timeframe, count=target_candles, seed=seed)

        enriched = DatasetManager.compute_causal_indicators(candles)

        if decision_file.exists():
            decisions = self.base_mgr.load_decisions_csv(decision_file)
        else:
            decisions = DatasetManager.generate_simulated_decisions(
                enriched,
                symbol=sym,
                timeframe=timeframe,
                seed=seed + 100,
            )
            self.base_mgr.save_decisions_csv(decisions, decision_file)

        return candles, enriched, decisions
