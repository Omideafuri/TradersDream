"""Event buffer, raw message capture, and file rotation writer with crash safety and disk monitoring."""

import csv
import gzip
import hashlib
from io import StringIO
import json
import os
from pathlib import Path
import shutil
import threading
import time
from typing import Dict, Any, List, Optional


class DiskCapacityExceededError(Exception):
    """Raised when available disk capacity drops below the safety threshold."""
    pass


class SyntheticDataForbiddenError(Exception):
    """Raised when synthetic or generated data is detected in a live collection pipeline."""
    pass


class EventBufferWriter:
    """Manages normalized event persistence, periodic flushing, rotation, and cryptographic hashing."""

    def __init__(
        self,
        output_dir: Path,
        symbol: str,
        stream_type: str,
        gzip_compress: bool = True,
        min_disk_free_bytes: int = 2 * 1024 * 1024 * 1024,  # 2 GB default
        allow_synthetic: bool = False,
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.symbol = symbol.upper()
        self.stream_type = stream_type.lower()
        self.gzip_compress = gzip_compress
        self.min_disk_free_bytes = min_disk_free_bytes
        self.allow_synthetic = allow_synthetic
        self._lock = threading.Lock()

        self.buffer: List[Dict[str, Any]] = []
        self.current_file_path: Optional[Path] = None
        self.events_written: int = 0
        self.current_date_str: Optional[str] = None

    def _check_disk_space(self):
        """Verifies available disk space exceeds minimum threshold."""
        try:
            _, _, free = shutil.disk_usage(self.output_dir)
            if free < self.min_disk_free_bytes:
                raise DiskCapacityExceededError(
                    f"Available disk space ({free / (1024**3):.2f} GB) is below "
                    f"safety threshold ({self.min_disk_free_bytes / (1024**3):.2f} GB)."
                )
        except OSError:
            pass

    def _get_filename(self, date_str: str) -> str:
        ext = ".csv.gz" if self.gzip_compress else ".csv"
        return f"binance-us_{self.stream_type}_{date_str}_{self.symbol}{ext}"

    def write_event(self, event: Dict[str, Any]):
        """Append a normalized event to the buffer and flush if batch size is reached."""
        if not self.allow_synthetic:
            # Reject any synthetic markers or generated events
            if event.get("is_synthetic") or event.get("simulated") or "synthetic" in str(event.get("source", "")).lower():
                raise SyntheticDataForbiddenError("Synthetic event rejected: allow_synthetic_fallback is False.")

        with self._lock:
            self.buffer.append(event)
            if len(self.buffer) >= 1000:
                self._flush_unlocked()

    def flush(self):
        """Flushes buffered records to the active output file with fsync."""
        with self._lock:
            self._flush_unlocked()

    def _flush_unlocked(self):
        if not self.buffer:
            return

        self._check_disk_space()

        date_str = time.strftime("%Y-%m-%d", time.gmtime(self.buffer[0]["local_timestamp"] / 1000000))
        if date_str != self.current_date_str:
            self._rotate_unlocked(date_str)

        file_exists = self.current_file_path.is_file() and self.current_file_path.stat().st_size > 0
        fieldnames = list(self.buffer[0].keys())

        out_str = StringIO()
        writer = csv.DictWriter(out_str, fieldnames=fieldnames)
        # Only write header if file is newly created or empty
        if not file_exists and self.events_written == 0:
            writer.writeheader()
        writer.writerows(self.buffer)
        data_bytes = out_str.getvalue().encode("utf-8")

        # Crash-safe write with explicit fsync
        if self.gzip_compress:
            with gzip.open(self.current_file_path, "ab") as f:
                f.write(data_bytes)
                f.flush()
                if hasattr(f.fileobj, "fileno"):
                    os.fsync(f.fileobj.fileno())
        else:
            with open(self.current_file_path, "ab") as f:
                f.write(data_bytes)
                f.flush()
                os.fsync(f.fileno())

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


class RawMessageWriter:
    """Preserves unaltered raw exchange WebSocket message payloads (RAW stage).

    Guarantees strict separation: RAW -> NORMALIZED -> QUALIFIED.
    """

    def __init__(
        self,
        output_dir: Path,
        symbol: str,
        gzip_compress: bool = True,
        min_disk_free_bytes: int = 2 * 1024 * 1024 * 1024,
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.symbol = symbol.upper()
        self.gzip_compress = gzip_compress
        self.min_disk_free_bytes = min_disk_free_bytes
        self._lock = threading.Lock()

        self.buffer: List[Dict[str, Any]] = []
        self.current_file_path: Optional[Path] = None
        self.current_date_str: Optional[str] = None
        self.messages_written: int = 0

    def _get_filename(self, date_str: str) -> str:
        ext = ".jsonl.gz" if self.gzip_compress else ".jsonl"
        return f"binance-us_raw_{date_str}_{self.symbol}{ext}"

    def write_raw(self, raw_str: str, local_timestamp_us: Optional[int] = None):
        """Append raw JSON message string to buffer."""
        ts = local_timestamp_us or int(time.time() * 1000000)
        entry = {"local_timestamp": ts, "raw": raw_str}
        with self._lock:
            self.buffer.append(entry)
            if len(self.buffer) >= 500:
                self._flush_unlocked()

    def flush(self):
        """Flushes buffered raw messages with fsync."""
        with self._lock:
            self._flush_unlocked()

    def _flush_unlocked(self):
        if not self.buffer:
            return

        # Disk space safety check
        try:
            _, _, free = shutil.disk_usage(self.output_dir)
            if free < self.min_disk_free_bytes:
                raise DiskCapacityExceededError(
                    f"Raw writer: available disk space ({free / (1024**3):.2f} GB) "
                    f"below threshold ({self.min_disk_free_bytes / (1024**3):.2f} GB)."
                )
        except OSError:
            pass

        date_str = time.strftime("%Y-%m-%d", time.gmtime(self.buffer[0]["local_timestamp"] / 1000000))
        if date_str != self.current_date_str:
            self.current_date_str = date_str
            self.current_file_path = self.output_dir / self._get_filename(date_str)
            self.messages_written = 0

        lines = [json.dumps(item) + "\n" for item in self.buffer]
        data_bytes = "".join(lines).encode("utf-8")

        if self.gzip_compress:
            with gzip.open(self.current_file_path, "ab") as f:
                f.write(data_bytes)
                f.flush()
                if hasattr(f.fileobj, "fileno"):
                    os.fsync(f.fileobj.fileno())
        else:
            with open(self.current_file_path, "ab") as f:
                f.write(data_bytes)
                f.flush()
                os.fsync(f.fileno())

        self.messages_written += len(self.buffer)
        self.buffer.clear()

    def close(self) -> Optional[Dict[str, Any]]:
        """Closes and hashes current raw message archive."""
        with self._lock:
            self._flush_unlocked()
            if self.current_file_path and self.current_file_path.is_file():
                raw_bytes = self.current_file_path.read_bytes()
                return {
                    "filename": self.current_file_path.name,
                    "file_size_bytes": len(raw_bytes),
                    "sha256": hashlib.sha256(raw_bytes).hexdigest(),
                    "messages_count": self.messages_written,
                    "date": self.current_date_str,
                }
            return None
