"""CryptoDataDownload raw dataset downloader and provenance hasher."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import ssl
import sys
import time
import urllib.request
from typing import Dict, Any, List


URLS = [
    ("Binance_BTCUSDT_2023_minute.csv", "https://www.cryptodatadownload.com/cdd/Binance_BTCUSDT_2023_minute.csv"),
    ("Binance_BTCUSDT_2024_minute.csv", "https://www.cryptodatadownload.com/cdd/Binance_BTCUSDT_2024_minute.csv"),
]


def download_file(url: str, dest_path: Path) -> Dict[str, Any]:
    """Downloads a file with streaming SHA-256 calculation and records metadata."""
    print(f"Downloading {url} -> {dest_path.name}...")
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    )

    t0 = time.time()
    sha256 = hashlib.sha256()
    total_bytes = 0

    with urllib.request.urlopen(req, context=ctx, timeout=60) as resp:
        http_status = resp.status
        content_length = int(resp.headers.get("Content-Length", 0))

        with open(dest_path, "wb") as f_out:
            while chunk := resp.read(131072):  # 128KB chunks
                f_out.write(chunk)
                sha256.update(chunk)
                total_bytes += len(chunk)
                if content_length > 0 and total_bytes % (5 * 1024 * 1024) < 131072:
                    pct = (total_bytes / content_length) * 100.0
                    print(f"  [{dest_path.name}] {total_bytes / (1024*1024):.1f} MB / {content_length / (1024*1024):.1f} MB ({pct:.1f}%)")

    elapsed = time.time() - t0
    digest = sha256.hexdigest()
    print(f"Completed {dest_path.name}: {total_bytes} bytes in {elapsed:.2f}s, SHA-256: {digest[:16]}...")

    return {
        "filename": dest_path.name,
        "source_url": url,
        "download_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "file_size_bytes": total_bytes,
        "sha256": digest,
        "http_status": http_status,
        "download_time_sec": round(elapsed, 2),
    }


def main():
    root = Path(__file__).resolve().parent.parent
    raw_dir = root / "phase10cx1" / "data" / "raw" / "cryptodatadownload" / "binance_btcusdt_1m"
    raw_dir.mkdir(parents=True, exist_ok=True)

    manifest_entries = []
    for fname, url in URLS:
        dest = raw_dir / fname
        if dest.exists() and dest.stat().st_size > 0:
            print(f"File {fname} already exists ({dest.stat().st_size} bytes). Verifying SHA-256...")
            h = hashlib.sha256()
            with open(dest, "rb") as f:
                while chunk := f.read(65536):
                    h.update(chunk)
            manifest_entries.append({
                "filename": fname,
                "source_url": url,
                "download_timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "file_size_bytes": dest.stat().st_size,
                "sha256": h.hexdigest(),
                "http_status": 200,
            })
        else:
            meta = download_file(url, dest)
            manifest_entries.append(meta)

    # Save raw manifest
    manifest_path = root / "PHASE_10CX1_RAW_MANIFEST.json"
    manifest_data = {
        "manifest_version": "1.0",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source": "CryptoDataDownload",
        "exchange": "Binance Spot",
        "symbol": "BTCUSDT",
        "granularity": "1m",
        "files": manifest_entries,
    }
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)
    print(f"Saved manifest to {manifest_path}")


if __name__ == "__main__":
    main()
