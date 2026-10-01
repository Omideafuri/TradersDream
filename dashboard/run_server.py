"""Server entry point to launch the Jevo Trading System Web Dashboard."""

import argparse
import logging
from pathlib import Path
import sys
import uvicorn

# Ensure repository root is on sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("dashboard.launcher")


def main():
    parser = argparse.ArgumentParser(description="Jevo Quantitative Trading System - Web Dashboard Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host address to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default: 8000)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    args = parser.parse_args()

    print("\n" + "=" * 70)
    print("  JEVO QUANTITATIVE TRADING SYSTEM — WEB CONTROL DASHBOARD")
    print("  Paper Trading Only: ENABLED | Leverage: 1.0x (Spot Simulation)")
    print(f"  API & Dashboard URL: http://{args.host}:{args.port}")
    print(f"  Interactive OpenAPI Docs: http://{args.host}:{args.port}/docs")
    print("=" * 70 + "\n")

    uvicorn.run(
        "dashboard.backend.api:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
