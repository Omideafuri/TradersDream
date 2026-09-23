"""Event buffer and file rotation writer with SHA-256 hashing and thread safety."""

import csv
import gzip
import hashlib
from io import StringIO
from pathlib import Path
import threading
import time
from typing import Dict, Any, List, Optional


class EventBufferWriter:
    """Manages event persistence, periodic flushing, rotation, and cryptographic hashing."""

    def __init__(self, output_dir: Path, symbol: str, stream_type: str, gzip_compress: bool = True):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.symbol = symbol.upper()
        self.stream_type = stream_type.lower()
        self.gzip_compress = gzip_compress
        self._lock = threading.Lock()

        self.buffer: List[Dict[str, Any]] = []
        self.current_file_path: Optional[Path] = None
        self.current_file_handle = None
        self.current_csv_writer = None
        self.events_written: int = 0
        self.current_date_str: Optional[str] = None

    def _get_filename(self, date_str: str) -> str:
        ext = ".csv.gz" if self.gzip_compress else ".csv"
        return f"binance-us_{self.stream_type}_{date_str}_{self.symbol}{ext}"

    def write_event(self, event: Dict[str, Any]):
        """Append an event to the buffer and flush if needed."""
        with self._lock:
            self.buffer.append(event)
            if len(self.buffer) >= 1000:
                self._flush_unlocked()

    def flush(self):
        """Flushes buffered records to the active output file."""
        with self._lock:
            self._flush_unlocked()

    def _flush_unlocked(self):
        if not self.buffer:
            return

        date_str = time.strftime("%Y-%m-%d", time.gmtime(self.buffer[0]["local_timestamp"] / 1000000))
        if date_str != self.current_date_str:
            self._rotate_unlocked(date_str)

        fieldnames = list(self.buffer[0].keys())
        out_str = StringIO()
        writer = csv.DictWriter(out_str, fieldnames=fieldnames)
        if self.events_written == 0:
            writer.writeheader()
        writer.writerows(self.buffer)
        data_bytes = out_str.getvalue().encode("utf-8")

        if self.gzip_compress:
            with gzip.open(self.current_file_path, "ab") as f:
                f.write(data_bytes)
        else:
            with open(self.current_file_path, "ab") as f:
                f.write(data_bytes)

        self.events_written += len(self.buffer)
        self.buffer.clear()

    def rotate(self, new_date_str: str) -> Optional[Dict[str, Any]]:
        """Closes previous file, hashes it, and initializes a new file."""
        with self._lock:
            return self._rotate_unlocked(new_date_str)

    def _rotate_unlocked(self, new_date_str: str) -> Optional[Dict[str, Any]]:
        closed_manifest = None
        if self.current_file_path and self.current_file_path.is_file():
            raw_bytes = self.current_file_path.read_bytes()
            sha256 = hashlib.sha256(raw_bytes).hexdigest()
            closed_manifest = {
                "filename": self.current_file_path.name,
                "file_size_bytes": len(raw_bytes),
                "sha256": sha256,
                "events_count": self.events_written,
                "date": self.current_date_str,
            }

        self.current_date_str = new_date_str
        self.current_file_path = self.output_dir / self._get_filename(new_date_str)
        self.events_written = 0
        return closed_manifest

    def close(self) -> Optional[Dict[str, Any]]:
        """Flushes remaining records and computes final file SHA-256."""
        with self._lock:
            self._flush_unlocked()
            if self.current_file_path and self.current_file_path.is_file():
                raw_bytes = self.current_file_path.read_bytes()
                sha256 = hashlib.sha256(raw_bytes).hexdigest()
                return {
                    "filename": self.current_file_path.name,
                    "file_size_bytes": len(raw_bytes),
                    "sha256": sha256,
                    "events_count": self.events_written,
                    "date": self.current_date_str,
                }
            return None
        return None
