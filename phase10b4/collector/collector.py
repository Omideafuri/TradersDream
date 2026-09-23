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
from phase10b4.collector.buffer_writer import EventBufferWriter

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

    collector = BinanceUSStreamCollector(config=config)

    # Initialize depth and trades buffer writers for each configured symbol
    for symbol in config.symbols:
        depth_writer = EventBufferWriter(
            output_dir=output_dir,
            symbol=symbol,
            stream_type="incremental_book_L2",
            gzip_compress=config.enable_gzip_compression,
        )
        trades_writer = EventBufferWriter(
            output_dir=output_dir,
            symbol=symbol,
            stream_type="trades",
            gzip_compress=config.enable_gzip_compression,
        )
        collector.register_writer(f"{symbol.upper()}_depth", depth_writer)
        collector.register_writer(f"{symbol.upper()}_trades", trades_writer)

    # Run collector
    await collector.run(max_seconds=max_seconds)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    default_config = CollectorConfig()

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
        loop.run_until_complete(main(default_config))
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Collector process stopped.")
    finally:
        loop.close()
