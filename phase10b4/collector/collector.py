import asyncio
import logging
from pathlib import Path
import platform
import signal
import sys
import os

# Adjust sys.path to allow running this script directly
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from phase10b4.collector.config import CollectorConfig
from phase10b4.collector.stream_client import BinanceUSStreamCollector
from phase10b4.collector.buffer_writer import EventBufferWriter, RawMessageWriter

logger = logging.getLogger("collector")


def _handle_sigterm(loop):
    """Gracefully shutdown on SIGTERM/SIGINT."""
    for task in asyncio.all_tasks(loop):
        task.cancel()


async def main(config: CollectorConfig, max_seconds: float = None):
    """Run the Binance.US stream collector for the configured symbols.

    The collector connects to the Binance.US websocket, fetches the initial
    order-book snapshot via the REST endpoint, then streams trade and depth
    updates, writing them to per-day CSV files via EventBufferWriter.
    """
    output_dir = Path(config.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_output_dir = Path(config.raw_output_dir).expanduser().resolve()
    raw_output_dir.mkdir(parents=True, exist_ok=True)

    collector = BinanceUSStreamCollector(config=config)

    # Initialize depth, trades, and raw message writers for each configured symbol
    for symbol in config.symbols:
        depth_writer = EventBufferWriter(
            output_dir=output_dir,
            symbol=symbol,
            stream_type="incremental_book_L2",
            gzip_compress=config.enable_gzip_compression,
            min_disk_free_bytes=config.min_disk_free_bytes,
            allow_synthetic=config.allow_synthetic_fallback,
        )
        trades_writer = EventBufferWriter(
            output_dir=output_dir,
            symbol=symbol,
            stream_type="trades",
            gzip_compress=config.enable_gzip_compression,
            min_disk_free_bytes=config.min_disk_free_bytes,
            allow_synthetic=config.allow_synthetic_fallback,
        )
        raw_writer = RawMessageWriter(
            output_dir=raw_output_dir,
            symbol=symbol,
            gzip_compress=config.enable_gzip_compression,
            min_disk_free_bytes=config.min_disk_free_bytes,
        )
        collector.register_writer(f"{symbol.upper()}_depth", depth_writer)
        collector.register_writer(f"{symbol.upper()}_trades", trades_writer)
        collector.register_raw_writer(symbol.upper(), raw_writer)

    # Run collector
    await collector.run(max_seconds=max_seconds)



if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Binance.US L2 & Trades Collector")
    parser.add_argument("--symbols", nargs="+", default=["BTCUSDT"], help="Symbols to collect (default: BTCUSDT)")
    parser.add_argument("--max-seconds", type=float, default=None, help="Max runtime in seconds")
    parser.add_argument("--output-dir", type=str, default="data/collected_events")
    parser.add_argument("--raw-output-dir", type=str, default="data/raw_collected_events")
    parser.add_argument("--checkpoint-dir", type=str, default="data/checkpoints")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    collector_config = CollectorConfig(
        symbols=args.symbols,
        output_dir=Path(args.output_dir),
        raw_output_dir=Path(args.raw_output_dir),
        checkpoint_dir=Path(args.checkpoint_dir),
    )

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Signal handlers on non-Windows platforms
    if platform.system() != "Windows":
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, lambda s=sig: _handle_sigterm(loop))
            except NotImplementedError:
                pass

    try:
        loop.run_until_complete(main(collector_config, max_seconds=args.max_seconds))
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Collector process stopped.")
    finally:
        loop.close()
