"""Processes raw CryptoDataDownload 1m data into validated 1m and aggregated 5m datasets."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Dict, Any, List, Tuple
import numpy as np
import pandas as pd


def audit_and_process():
    root = Path(__file__).resolve().parent.parent
    raw_dir = root / "phase10cx1" / "data" / "raw" / "cryptodatadownload" / "binance_btcusdt_1m"
    proc_dir = root / "phase10cx1" / "data" / "processed"
    proc_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("PHASE 10C.X.1 — DATA PROCESSOR & INTEGRITY AUDITOR")
    print("=" * 70)

    # 1. Load and normalize raw files
    dfs = []
    file_stats = {}

    for fname in ["Binance_BTCUSDT_2023_minute.csv", "Binance_BTCUSDT_2024_minute.csv"]:
        fpath = raw_dir / fname
        print(f"\nProcessing {fname}...")
        df = pd.read_csv(fpath, skiprows=1)
        raw_count = len(df)
        print(f"  Raw rows: {raw_count}")

        # Column normalization
        col_map = {}
        for c in df.columns:
            cl = c.strip().lower()
            if cl == "unix":
                col_map[c] = "unix_raw"
            elif cl == "date":
                col_map[c] = "date_str"
            elif cl == "symbol":
                col_map[c] = "symbol"
            elif cl == "open":
                col_map[c] = "open"
            elif cl == "high":
                col_map[c] = "high"
            elif cl == "low":
                col_map[c] = "low"
            elif cl == "close":
                col_map[c] = "close"
            elif cl in ("volume", "volume btc"):
                col_map[c] = "volume_btc"
            elif cl in ("volume_from", "volume usdt"):
                col_map[c] = "volume_usdt"
            elif cl == "tradecount":
                col_map[c] = "trade_count"
        df = df.rename(columns=col_map)

        # Standardize unix timestamp to milliseconds
        # Values > 1e14 are microseconds; divide by 1000
        unix_ms = df["unix_raw"].apply(lambda x: int(x // 1000) if x > 1e14 else int(x))
        df["timestamp_ms"] = unix_ms

        file_stats[fname] = {
            "raw_rows": raw_count,
            "min_ts_ms": int(unix_ms.min()),
            "max_ts_ms": int(unix_ms.max()),
            "min_date_utc": datetime.fromtimestamp(unix_ms.min()/1000, tz=timezone.utc).isoformat(),
            "max_date_utc": datetime.fromtimestamp(unix_ms.max()/1000, tz=timezone.utc).isoformat(),
        }
        dfs.append(df)

    # Combine datasets
    combined_1m = pd.concat(dfs, ignore_index=True)
    total_raw_rows = len(combined_1m)
    print(f"\nTotal combined 1m rows: {total_raw_rows}")

    # Check duplicates before sorting
    dup_mask = combined_1m.duplicated(subset=["timestamp_ms"], keep="first")
    dup_count = int(dup_mask.sum())
    print(f"Duplicate timestamp rows: {dup_count}")

    # Remove duplicates if any (keeping first) and sort chronologically
    combined_1m = combined_1m.drop_duplicates(subset=["timestamp_ms"], keep="first")
    combined_1m = combined_1m.sort_values(by="timestamp_ms", ascending=True).reset_index(drop=True)

    # 2. OHLC Integrity Audit
    print("\nAuditing OHLC Candle Invariants...")
    v_high_low = (combined_1m["high"] < combined_1m["low"]).sum()
    v_high_open = (combined_1m["high"] < combined_1m["open"]).sum()
    v_high_close = (combined_1m["high"] < combined_1m["close"]).sum()
    v_low_open = (combined_1m["low"] > combined_1m["open"]).sum()
    v_low_close = (combined_1m["low"] > combined_1m["close"]).sum()
    v_pos_open = (combined_1m["open"] <= 0).sum()
    v_pos_high = (combined_1m["high"] <= 0).sum()
    v_pos_low = (combined_1m["low"] <= 0).sum()
    v_pos_close = (combined_1m["close"] <= 0).sum()
    v_nonneg_vol = (combined_1m["volume_btc"] < 0).sum()

    print(f"  high < low violations: {v_high_low}")
    print(f"  high < open violations: {v_high_open}")
    print(f"  high < close violations: {v_high_close}")
    print(f"  low > open violations: {v_low_open}")
    print(f"  low > close violations: {v_low_close}")
    print(f"  non-positive prices: {v_pos_open + v_pos_high + v_pos_low + v_pos_close}")
    print(f"  negative volume: {v_nonneg_vol}")

    # 3. Continuity and Gap Analysis
    print("\nAuditing Timestamp Continuity...")
    ts_diffs = combined_1m["timestamp_ms"].diff().dropna()
    expected_diff_ms = 60000  # 60s
    gap_mask = ts_diffs > expected_diff_ms
    gap_count = int(gap_mask.sum())
    total_missing_minutes = int(((ts_diffs[gap_mask] - expected_diff_ms) // expected_diff_ms).sum())
    max_gap_ms = int(ts_diffs.max()) if len(ts_diffs) > 0 else 0
    max_gap_min = max_gap_ms // 60000

    min_ts = int(combined_1m["timestamp_ms"].min())
    max_ts = int(combined_1m["timestamp_ms"].max())
    total_expected_minutes = ((max_ts - min_ts) // 60000) + 1
    completeness_pct = (len(combined_1m) / total_expected_minutes) * 100.0

    print(f"  Start UTC: {datetime.fromtimestamp(min_ts/1000, tz=timezone.utc).isoformat()}")
    print(f"  End UTC:   {datetime.fromtimestamp(max_ts/1000, tz=timezone.utc).isoformat()}")
    print(f"  Total theoretical 1m bars: {total_expected_minutes}")
    print(f"  Actual observed 1m bars:    {len(combined_1m)}")
    print(f"  Missing 1m intervals:       {total_missing_minutes}")
    print(f"  Discrete gap episodes:      {gap_count}")
    print(f"  Longest gap:                {max_gap_min} minutes ({max_gap_min/60:.1f} hours)")
    print(f"  Completeness:               {completeness_pct:.4f}%")

    # 4. Construct Deterministic 5-Minute Candles
    print("\nAggregating 1-Minute Bars into Deterministic 5-Minute Candles...")
    # Align bucket boundaries to UTC: bucket_ts = (timestamp_ms // 300000) * 300000
    combined_1m["bucket_5m_ms"] = (combined_1m["timestamp_ms"] // 300000) * 300000

    # Group by bucket_5m_ms
    agg_funcs = {
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume_btc": "sum",
        "volume_usdt": "sum",
        "trade_count": "sum",
    }
    df_5m = combined_1m.groupby("bucket_5m_ms").agg(agg_funcs).reset_index()
    df_5m = df_5m.rename(columns={"bucket_5m_ms": "timestamp_ms", "volume_btc": "volume"})

    # Verify 5m OHLC invariants
    v5_hl = (df_5m["high"] < df_5m["low"]).sum()
    v5_ho = (df_5m["high"] < df_5m["open"]).sum()
    v5_hc = (df_5m["high"] < df_5m["close"]).sum()
    v5_lo = (df_5m["low"] > df_5m["open"]).sum()
    v5_lc = (df_5m["low"] > df_5m["close"]).sum()
    assert (v5_hl + v5_ho + v5_hc + v5_lo + v5_lc) == 0, "5m invariant violation detected"

    # Save processed 5m dataset
    out_5m_path = proc_dir / "BINANCE_BTCUSDT_5m_FROM_CDD.csv"
    df_5m.to_csv(out_5m_path, index=False)
    print(f"Saved 5m aggregated dataset: {len(df_5m)} bars -> {out_5m_path}")

    # Compute SHA-256 of processed 5m file
    h5m = hashlib.sha256()
    with open(out_5m_path, "rb") as f:
        while chunk := f.read(65536):
            h5m.update(chunk)
    sha256_5m = h5m.hexdigest()
    print(f"SHA-256 of 5m dataset: {sha256_5m}")

    quality_report = {
        "dataset": "CryptoDataDownload Binance Spot BTCUSDT",
        "total_raw_rows": total_raw_rows,
        "deduplicated_1m_rows": len(combined_1m),
        "total_5m_bars": len(df_5m),
        "start_utc": datetime.fromtimestamp(min_ts/1000, tz=timezone.utc).isoformat(),
        "end_utc": datetime.fromtimestamp(max_ts/1000, tz=timezone.utc).isoformat(),
        "total_calendar_days": round((max_ts - min_ts) / 86400000.0, 2),
        "total_expected_1m_intervals": total_expected_minutes,
        "missing_1m_intervals": total_missing_minutes,
        "completeness_pct": round(completeness_pct, 4),
        "longest_gap_minutes": int(max_gap_min),
        "ohlc_violations": {
            "high_less_than_low": int(v_high_low),
            "high_less_than_open": int(v_high_open),
            "high_less_than_close": int(v_high_close),
            "low_greater_than_open": int(v_low_open),
            "low_greater_than_close": int(v_low_close),
            "non_positive_prices": int(v_pos_open + v_pos_high + v_pos_low + v_pos_close),
            "negative_volume": int(v_nonneg_vol),
        },
        "processed_5m_file": {
            "path": str(out_5m_path.relative_to(root)),
            "bars_count": len(df_5m),
            "sha256": sha256_5m,
        },
        "file_stats": file_stats,
    }

    return quality_report


if __name__ == "__main__":
    rep = audit_and_process()
    print("\nSummary Quality Dict:")
    print(json.dumps(rep, indent=2))
