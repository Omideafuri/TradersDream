"""Main orchestration module for Crypto Trading Bot - Phase 1.

Enforces PAPER_TRADING_ONLY safety tripwire on startup.
Coordinates:
1. Public market data collection (BTC/USDT 5m)
2. Deterministic technical indicators & MarketState creation
3. Isolated Jev decision request
4. Independent deterministic risk evaluation
5. Simulated paper execution
6. Comprehensive structured logging
"""

import argparse
import asyncio
from datetime import datetime, timezone
import json
import logging
import sys
from typing import Optional, Dict, Any

from bot.config import BotConfig, get_config
from bot.market_data import MarketDataFetcher
from bot.indicators import calculate_indicators, build_market_state
from bot.decision import JevDecisionEngine, JevApiProvider, Action
from bot.risk import RiskEngine
from bot.paper_trader import PaperTradingEngine

# Configure root logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("crypto_bot")


class CryptoTradingBot:
    """Phase 1 Paper-Trading Cryptocurrency Bot."""

    def __init__(self, config: Optional[BotConfig] = None):
        self.config = config or get_config()
        # Enforce global safety invariant
        self.config.validate_safety()

        self.market_data = MarketDataFetcher()
        jev_provider = JevApiProvider(
            api_key=self.config.jev_agent_key,
            endpoint=self.config.jev_endpoint,
            model=self.config.jev_model,
            timeout_seconds=self.config.jev_timeout_seconds,
        )
        self.decision_engine = JevDecisionEngine(
            provider=jev_provider,
            timeout_seconds=self.config.jev_timeout_seconds,
            confidence_threshold=self.config.jev_confidence_threshold,
        )
        self.risk_engine = RiskEngine(
            max_risk_per_trade=self.config.max_risk_per_trade,
            max_daily_loss=self.config.max_daily_loss,
            max_position_size=self.config.max_position_size,
            max_open_positions=self.config.max_open_positions,
            leverage=self.config.leverage,
        )
        self.paper_trader = PaperTradingEngine(
            initial_balance=self.config.initial_balance,
            taker_fee=self.config.taker_fee,
            maker_fee=self.config.maker_fee,
        )

        logger.info(
            f"Initialized Crypto Trading Bot (Phase 1). "
            f"Symbol: {self.config.symbol}, Interval: {self.config.candle_interval}, "
            f"Paper Balance: ${self.config.initial_balance:,.2f}"
        )

    async def step(self) -> Dict[str, Any]:
        """Executes a single market analysis and paper trading decision cycle."""
        # 1. Fetch public klines
        try:
            klines_df = await self.market_data.fetch_klines(
                symbol=self.config.symbol,
                interval=self.config.candle_interval,
                limit=self.config.candle_limit,
            )
        except Exception as exc:
            logger.warning(
                f"Failed to fetch live market data ({exc}). Generating synthetic candles for resilience."
            )
            klines_df = self.market_data.generate_synthetic_klines(count=self.config.candle_limit)

        # 2. Calculate deterministic indicators & build MarketState
        enriched_df = calculate_indicators(klines_df)
        market_state = build_market_state(enriched_df, symbol=self.config.symbol)
        current_price = market_state.price

        # 3. Request isolated Jev decision
        jev_decision = await self.decision_engine.get_decision(market_state)

        # 4. Independent Risk Engine evaluation
        snap = self.paper_trader.get_snapshot(current_price)
        pos = self.paper_trader.current_position

        risk_assessment = self.risk_engine.evaluate(
            decision=jev_decision,
            current_price=current_price,
            portfolio_value=snap["portfolio_value"],
            available_cash=snap["cash_balance"],
            has_open_position=self.paper_trader.has_open_position,
            current_position_side=pos.side if pos else None,
            current_position_entry_price=pos.entry_price if pos else 0.0,
            daily_realized_pnl=snap["realized_pnl"],
            atr14=market_state.atr14,
        )

        final_action = risk_assessment.final_action

        # 5. Paper execution
        executed_action = "HOLD"
        trade_details = None

        if final_action == Action.LONG and not self.paper_trader.has_open_position:
            if risk_assessment.target_quantity > 0:
                try:
                    self.paper_trader.execute_buy(
                        symbol=self.config.symbol,
                        price=current_price,
                        quantity=risk_assessment.target_quantity,
                        timestamp=market_state.timestamp,
                    )
                    executed_action = "BUY_OPEN"
                except Exception as e:
                    logger.error(f"Paper buy execution failed: {e}")
        elif (final_action == Action.SHORT and self.paper_trader.has_open_position and pos.side == "LONG") or \
             (final_action == Action.HOLD and False):  # Can expand exit rules in future
            try:
                record = self.paper_trader.execute_sell(
                    price=current_price,
                    timestamp=market_state.timestamp,
                )
                self.risk_engine.record_closed_trade(record.net_pnl)
                executed_action = "SELL_CLOSE"
                trade_details = record.to_dict()
            except Exception as e:
                logger.error(f"Paper sell execution failed: {e}")
        else:
            # Update price for unrealized PnL
            self.paper_trader.update_market_price(current_price)

        # Refresh snapshot after execution
        updated_snap = self.paper_trader.get_snapshot(current_price)

        # 6. Structured decision log
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "symbol": self.config.symbol,
            "price": current_price,
            "indicators": {
                "ema20": market_state.ema20,
                "ema50": market_state.ema50,
                "ema200": market_state.ema200,
                "rsi14": market_state.rsi14,
                "atr14": market_state.atr14,
                "volume_ratio": market_state.volume_ratio,
                "price_change_pct": market_state.price_change_pct,
            },
            "jev_action": jev_decision.action.value,
            "jev_confidence": jev_decision.confidence,
            "jev_reason_code": jev_decision.reason_code,
            "risk_approved": risk_assessment.approved,
            "risk_rejection_reason": risk_assessment.rejection_reason,
            "final_action": final_action.value,
            "executed_action": executed_action,
            "position": updated_snap["position"],
            "realized_pnl": updated_snap["realized_pnl"],
            "unrealized_pnl": updated_snap["unrealized_pnl"],
            "portfolio_value": updated_snap["portfolio_value"],
            "max_drawdown_pct": updated_snap["max_drawdown_pct"],
        }

        # Emit structured log
        logger.info(f"CYCLE_LOG: {json.dumps(log_entry)}")
        return log_entry

    async def run_loop(self, interval_seconds: Optional[int] = None) -> None:
        """Runs the continuous paper trading loop."""
        interval = interval_seconds or self.config.loop_interval_seconds
        logger.info(f"Starting paper trading cycle loop (interval: {interval}s)...")
        try:
            while True:
                await self.step()
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            logger.info("Trading bot loop cancelled.")


async def async_main(once: bool = False) -> None:
    # Ensure safety check passes
    config = get_config()
    bot = CryptoTradingBot(config)

    if once:
        logger.info("Executing single test cycle (--once)...")
        result = await bot.step()
        print("\n=== SINGLE CYCLE RESULT ===")
        print(json.dumps(result, indent=2))
    else:
        await bot.run_loop()


def main() -> None:
    parser = argparse.ArgumentParser(description="Crypto Trading Bot - Phase 1 (Paper Trading Only)")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single decision and paper trading cycle, then exit.",
    )
    args = parser.parse_args()

    try:
        asyncio.run(async_main(once=args.once))
    except KeyboardInterrupt:
        logger.info("Bot gracefully terminated by user.")
    except Exception as exc:
        logger.critical(f"Bot failed with unhandled exception: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
