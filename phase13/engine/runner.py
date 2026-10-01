"""
Phase 13: Prospective Forward Paper Capture Daemon & CLI Runner.
Provides robust process lifecycle, exception isolation, and graceful shutdown.
Strictly Paper-Trading Only: Zero Live Orders, Zero Wallet Connections, Zero Private Keys.
"""

import argparse
import json
import logging
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from phase13.engine.forward_monitor import ForwardMonitor
from phase13.engine.integrity_monitor import IntegrityMonitor
from phase13.engine.state_manager import StateManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [Phase13Runner] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("Phase13Runner")


class ForwardRunner:
    def __init__(self, interval_seconds: int = 60):
        self.interval_seconds = interval_seconds
        self.running = False

        # Hardcoded Code-Level Safety Invariants
        self.PAPER_TRADING_ONLY = True
        self.LIVE_ORDERS = 0
        self.WALLET_CONNECTIONS = 0
        self.PRIVATE_KEYS = 0
        self.LEVERAGE = 1.0

        assert self.PAPER_TRADING_ONLY is True
        assert self.LIVE_ORDERS == 0
        assert self.WALLET_CONNECTIONS == 0
        assert self.PRIVATE_KEYS == 0
        assert self.LEVERAGE == 1.0

        self.monitor = ForwardMonitor()
        self.integrity_mon = IntegrityMonitor(self.monitor.sm)

        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    def _handle_signal(self, signum, frame):
        logger.info(f"Received termination signal ({signum}). Initiating graceful shutdown...")
        self.running = False
        st = self.monitor.sm.state
        st.daemon_running = False
        st.daemon_pid = None
        st.feed_status = "STOPPED"
        self.monitor.sm.log_event("SHUTDOWN_SIGNAL", "INFO", f"Process received signal {signum}")
        self.monitor.sm.save_state()

    def run_single_poll(self) -> dict:
        """
        Executes a single polling cycle:
        1. Pre-flight integrity verification.
        2. Fetch authentic live spot quote.
        3. Ingest quote and aggregate candle if completed.
        4. Execute any pending orders or process overnight financing.
        5. Verify state consistency.
        """
        self.monitor.sm.log_event("POLL_START", "INFO", "Single poll execution initiated")
        
        # 1. Integrity check
        int_ok, int_errs = self.integrity_mon.verify_strategy_hashes()
        if not int_ok:
            err_msg = "; ".join(int_errs)
            logger.error(f"Integrity check failed: {err_msg}")
            self.monitor.sm.state.feed_status = "INTEGRITY_BREACH"
            self.monitor.sm.log_event("INTEGRITY_BREACH", "CRITICAL", err_msg)
            self.monitor.sm.save_state()
            return {"status": "HALTED", "reason": err_msg}

        # 2. Fetch quote
        quote = self.monitor.fetch_live_quote()
        st = self.monitor.sm.state
        if not quote:
            logger.warning("No quote received in poll cycle")
            st.feed_status = "RUNNING_API_FAILURE"
            self.monitor.sm.save_state()
            return {"status": "NO_QUOTE", "time": datetime.now(timezone.utc).isoformat()}

        # 3. Process quote
        candle_completed, candle_dt = self.monitor.process_quote(quote)

        # 4. Check feed freshness
        if st.last_successful_quote_utc:
            try:
                last_dt = datetime.fromisoformat(st.last_successful_quote_utc)
                age_secs = (datetime.now(timezone.utc) - last_dt).total_seconds()
                if age_secs > 900:  # Older than 15 mins
                    st.feed_status = "RUNNING_STALE_FEED"
                else:
                    st.feed_status = "RUNNING_HEALTHY"
            except Exception:
                st.feed_status = "RUNNING_HEALTHY"
        else:
            st.feed_status = "RUNNING_HEALTHY"

        # 5. Save and return summary
        self.monitor.sm.save_state()

        result = {
            "status": "OK",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "latest_price": st.last_quote_bid,
            "ask_data_available": st.ask_data_available,
            "position": st.current_state,
            "position_units": st.position_units,
            "equity": st.current_equity,
            "sma50": st.latest_sma50,
            "sma200": st.latest_sma200,
            "candle_completed": candle_completed,
            "candle_dt": candle_dt,
            "feed_status": st.feed_status,
        }
        logger.info(
            f"Poll complete | Price: ${st.last_quote_bid:.2f} | Pos: {st.current_state} | "
            f"Equity: ${st.current_equity:.2f} | SMA50: ${st.latest_sma50:.2f} | SMA200: ${st.latest_sma200:.2f}"
        )
        return result

    def run_daemon(self):
        """
        Runs continuous loop until interrupted.
        """
        import os
        st = self.monitor.sm.state
        st.daemon_pid = os.getpid()
        st.daemon_running = True
        st.restart_count += 1
        st.daemon_start_time_utc = datetime.now(timezone.utc).isoformat()
        st.feed_status = "RUNNING_HEALTHY"
        self.monitor.sm.save_state()

        logger.info(f"Starting Phase 13 daemon (PID: {st.daemon_pid}). Polling interval: {self.interval_seconds}s")
        self.monitor.sm.log_event(
            "DAEMON_START",
            "INFO",
            f"Phase 13 daemon started (PID: {st.daemon_pid}). Interval: {self.interval_seconds}s, Mode: PAPER_TRADING_ONLY"
        )
        self.running = True

        try:
            while self.running:
                try:
                    self.run_single_poll()
                except Exception as e:
                    logger.error(f"Unhandled error in polling cycle: {e}", exc_info=True)
                    self.monitor.sm.state.failed_polls += 1
                    self.monitor.sm.state.feed_status = "RUNNING_API_FAILURE"
                    self.monitor.sm.log_event("CYCLE_EXCEPTION", "ERROR", str(e))
                    self.monitor.sm.save_state()

                # Sleep in 1-second chunks to respond quickly to signals
                for _ in range(self.interval_seconds):
                    if not self.running:
                        break
                    time.sleep(1)
        finally:
            st.daemon_running = False
            st.daemon_pid = None
            st.feed_status = "STOPPED"
            self.monitor.sm.save_state()
            logger.info("Daemon gracefully stopped.")
            self.monitor.sm.log_event("DAEMON_STOPPED", "INFO", "Phase 13 daemon stopped gracefully")
            self.monitor.sm.save_state()


def main():
    parser = argparse.ArgumentParser(description="Phase 13 Prospective Forward Paper Capture Runner")
    parser.add_argument(
        "--mode",
        choices=["poll", "daemon", "check-integrity"],
        default="poll",
        help="Execution mode (default: poll)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Polling interval in seconds for daemon mode (default: 60)",
    )
    args = parser.parse_args()

    runner = ForwardRunner(interval_seconds=args.interval)

    if args.mode == "poll":
        res = runner.run_single_poll()
        print(f"Poll Result: {res}")
    elif args.mode == "daemon":
        runner.run_daemon()
    elif args.mode == "check-integrity":
        report = runner.integrity_mon.run_daily_integrity_check()
        print(f"Daily Integrity Checklist Report:\n{json.dumps(report, indent=2)}")


if __name__ == "__main__":
    main()
