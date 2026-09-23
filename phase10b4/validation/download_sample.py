"""Acquire a bounded sample slice from Tardis.dev free 1st-of-month Binance.US sample for schema & reconstructor verification."""

import gzip
import hashlib
import io
from pathlib import Path
import urllib.request

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

SAMPLES = {
    "trades": {
        "url": "https://datasets.tardis.dev/v1/binance-us/trades/2024/03/01/BTCUSDT.csv.gz",
        "output_filename": "sample_binance-us_trades_2024-03-01_BTCUSDT.csv",
        "max_lines": 5000,
    },
    "incremental_book_L2": {
        "url": "https://datasets.tardis.dev/v1/binance-us/incremental_book_L2/2024/03/01/BTCUSDT.csv.gz",
        "output_filename": "sample_binance-us_incremental_book_L2_2024-03-01_BTCUSDT.csv",
        "max_lines": 10000,
    },
}


def acquire_sample(data_type: str) -> dict:
    spec = SAMPLES[data_type]
    url = spec["url"]
    out_path = DATA_DIR / spec["output_filename"]
    max_lines = spec["max_lines"]

    print(f"Acquiring {data_type} sample from {url}...")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})

    with urllib.request.urlopen(req, timeout=30) as resp:
        compressed_bytes = resp.read()

    decompressed_lines = []
    with gzip.GzipFile(fileobj=io.BytesIO(compressed_bytes)) as gz:
        for _ in range(max_lines):
            line = gz.readline()
            if not line:
                break
            decompressed_lines.append(line.decode("utf-8"))

    content = "".join(decompressed_lines)
    content_bytes = content.encode("utf-8")
    sha256 = hashlib.sha256(content_bytes).hexdigest()
    out_path.write_bytes(content_bytes)

    print(f"Saved {out_path.name} ({len(content_bytes)} bytes, SHA-256: {sha256})")

    return {
        "data_type": data_type,
        "source_url": url,
        "filename": spec["output_filename"],
        "lines_count": len(decompressed_lines),
        "file_size_bytes": len(content_bytes),
        "sha256": sha256,
        "remote_compressed_size": len(compressed_bytes),
    }


def main():
    results = {}
    for dt in ["trades", "incremental_book_L2"]:
        results[dt] = acquire_sample(dt)
    return results


if __name__ == "__main__":
    main()
