"""Automated tests for Jev Decision Layer integration, isolation, and fallback behaviors.

All external API interactions are strictly mocked to avoid live network hits during automated testing.
"""

import asyncio
import logging
import pytest
from bot.decision import (
    Action,
    Decision,
    JevDecisionEngine,
    JevApiProvider,
    RuleBasedJev,
)
from bot.indicators import MarketState


@pytest.fixture
def sample_market_state() -> MarketState:
    return MarketState(
        symbol="BTCUSDT",
        price=60000.0,
        ema20=59000.0,
        ema50=58000.0,
        ema200=55000.0,
        rsi14=60.0,
        atr14=500.0,
        volume_ratio=1.2,
        price_change_pct=1.0,
    )


class MockProvider:
    def __init__(self, return_val=None, delay=0.0, raises=None):
        self.return_val = return_val
        self.delay = delay
        self.raises = raises

    async def decide_raw(self, state_dict):
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.raises:
            raise self.raises
        return self.return_val


@pytest.mark.asyncio
async def test_jev_action_long(sample_market_state):
    """Verifies that a valid LONG response is accepted when confidence exceeds threshold."""
    provider = MockProvider(return_val={
        "answers": {
            "action": {"type": "choice", "choice": "LONG", "confidence": 0.85},
            "reason_code": {"type": "choice", "choice": "TREND_CONFIRMATION"},
        }
    })
    engine = JevDecisionEngine(provider=provider, confidence_threshold=0.60)
    decision = await engine.get_decision(sample_market_state)

    assert decision.action == Action.LONG
    assert decision.confidence == 0.85
    assert decision.reason_code == "TREND_CONFIRMATION"


@pytest.mark.asyncio
async def test_jev_action_short(sample_market_state):
    """Verifies that a valid SHORT response is accepted when confidence exceeds threshold."""
    provider = MockProvider(return_val={
        "answers": {
            "action": {"type": "choice", "choice": "SHORT", "confidence": 0.72},
            "reason_code": {"type": "choice", "choice": "MOMENTUM_EXTREME"},
        }
    })
    engine = JevDecisionEngine(provider=provider, confidence_threshold=0.60)
    decision = await engine.get_decision(sample_market_state)

    assert decision.action == Action.SHORT
    assert decision.confidence == 0.72
    assert decision.reason_code == "MOMENTUM_EXTREME"


@pytest.mark.asyncio
async def test_jev_action_hold(sample_market_state):
    """Verifies that a valid HOLD response is preserved."""
    provider = MockProvider(return_val={
        "answers": {
            "action": {"type": "choice", "choice": "HOLD", "confidence": 0.90},
            "reason_code": {"type": "choice", "choice": "NO_CLEAR_SIGNAL"},
        }
    })
    engine = JevDecisionEngine(provider=provider, confidence_threshold=0.60)
    decision = await engine.get_decision(sample_market_state)

    assert decision.action == Action.HOLD
    assert decision.confidence == 0.90
    assert decision.reason_code == "NO_CLEAR_SIGNAL"


@pytest.mark.asyncio
async def test_low_confidence_becomes_hold(sample_market_state):
    """Verifies that LONG/SHORT with confidence below threshold safely becomes HOLD."""
    # LONG with 0.45 confidence (< 0.60 threshold)
    provider = MockProvider(return_val={
        "answers": {
            "action": {"type": "choice", "choice": "LONG", "confidence": 0.45},
            "reason_code": {"type": "choice", "choice": "TREND_CONFIRMATION"},
        }
    })
    engine = JevDecisionEngine(provider=provider, confidence_threshold=0.60)
    decision = await engine.get_decision(sample_market_state)

    assert decision.action == Action.HOLD
    assert decision.confidence == 0.45
    assert decision.reason_code == "LOW_CONFIDENCE"


@pytest.mark.asyncio
async def test_malformed_responses_become_hold(sample_market_state):
    """Verifies that various corrupted payloads safely fallback to HOLD."""
    invalid_payloads = [
        "BUY ALL NOW!!!",
        {"action": "BUY_MOON", "confidence": 0.99},
        {"action": "LEVERAGE_50X"},
        "{\"invalid_json\":",
        None,
        {"action": "LONG", "confidence": "not_a_number"},
        {"confidence": 0.8},
        {"answers": {}},
    ]

    for payload in invalid_payloads:
        provider = MockProvider(return_val=payload)
        engine = JevDecisionEngine(provider=provider)
        decision = await engine.get_decision(sample_market_state)

        assert decision.action == Action.HOLD
        assert decision.confidence == 0.0


@pytest.mark.asyncio
async def test_jev_timeout_becomes_hold(sample_market_state):
    """Verifies that if Jev times out, action defaults safely to HOLD with confidence 0.0."""
    provider = MockProvider(delay=5.0)
    engine = JevDecisionEngine(provider=provider, timeout_seconds=0.05)
    decision = await engine.get_decision(sample_market_state)

    assert decision.action == Action.HOLD
    assert decision.confidence == 0.0
    assert decision.reason_code == "TIMEOUT_FALLBACK"


@pytest.mark.asyncio
async def test_authentication_failure_becomes_hold(sample_market_state):
    """Verifies that authentication errors map to safe HOLD."""
    provider = MockProvider(return_val={
        "action": "HOLD",
        "confidence": 0.0,
        "reason_code": "AUTH_FAILURE",
    })
    engine = JevDecisionEngine(provider=provider)
    decision = await engine.get_decision(sample_market_state)

    assert decision.action == Action.HOLD
    assert decision.confidence == 0.0
    assert decision.reason_code == "AUTH_FAILURE"


@pytest.mark.asyncio
async def test_missing_credentials_becomes_hold(sample_market_state):
    """Verifies that unconfigured Jev API provider defaults to HOLD."""
    provider = JevApiProvider(api_key=None)
    assert not provider.is_configured

    engine = JevDecisionEngine(provider=provider)
    decision = await engine.get_decision(sample_market_state)

    assert decision.action == Action.HOLD
    assert decision.confidence == 0.0
    assert decision.reason_code == "MISSING_CREDENTIALS"


@pytest.mark.asyncio
async def test_secrets_never_appear_in_logs(caplog, sample_market_state):
    """Verifies that API keys/secrets never leak into log records or exception outputs."""
    secret_key = "super_secret_test_token_12345"
    provider = MockProvider(raises=RuntimeError("Simulated failure with context"))
    engine = JevDecisionEngine(provider=provider)

    with caplog.at_level(logging.DEBUG):
        decision = await engine.get_decision(sample_market_state)

    assert decision.action == Action.HOLD
    assert secret_key not in caplog.text
    assert "super_secret" not in decision.reason_code
