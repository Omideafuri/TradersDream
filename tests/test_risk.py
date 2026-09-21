"""Automated tests for deterministic Risk Engine rules."""

import pytest
from bot.decision import Action, Decision
from bot.risk import RiskEngine


def test_max_position_size_limit():
    """Verifies that position size never exceeds 10% of portfolio value."""
    engine = RiskEngine(
        max_risk_per_trade=0.005,
        max_daily_loss=0.02,
        max_position_size=0.10,  # 10%
    )
    portfolio_val = 10000.0
    cash = 10000.0
    price = 50000.0

    decision = Decision(action=Action.LONG, confidence=0.9, reason_code="STRONG_SIGNAL")
    assessment = engine.evaluate(
        decision=decision,
        current_price=price,
        portfolio_value=portfolio_val,
        available_cash=cash,
        has_open_position=False,
    )

    assert assessment.approved is True
    assert assessment.final_action == Action.LONG
    # Max notional allowed is 10% of $10,000 = $1,000
    assert assessment.target_notional <= 1000.0
    assert assessment.target_quantity <= (1000.0 / price)


def test_daily_loss_limit_rejection():
    """Verifies that daily loss >= 2% rejects any new trade attempts."""
    engine = RiskEngine(
        max_risk_per_trade=0.005,
        max_daily_loss=0.02,  # 2% of $10,000 is $200
    )
    portfolio_val = 9800.0
    cash = 9800.0
    price = 50000.0
    daily_pnl = -201.0  # Loss exceeded 2%

    decision = Decision(action=Action.LONG, confidence=0.95, reason_code="BULLISH")
    assessment = engine.evaluate(
        decision=decision,
        current_price=price,
        portfolio_value=portfolio_val,
        available_cash=cash,
        has_open_position=False,
        daily_realized_pnl=daily_pnl,
    )

    assert assessment.approved is False
    assert assessment.final_action == Action.HOLD
    assert assessment.rejection_reason == "REJECT_DAILY_LOSS_LIMIT_REACHED"


def test_single_open_position_rule():
    """Verifies that maximum one open position is strictly enforced."""
    engine = RiskEngine()
    portfolio_val = 10000.0
    cash = 9000.0
    price = 50000.0

    decision = Decision(action=Action.LONG, confidence=0.8, reason_code="ADD_SIGNAL")
    assessment = engine.evaluate(
        decision=decision,
        current_price=price,
        portfolio_value=portfolio_val,
        available_cash=cash,
        has_open_position=True,  # Already in position
        current_position_side="LONG",
        current_position_entry_price=49000.0,
    )

    assert assessment.approved is False
    assert assessment.final_action == Action.HOLD
    assert "REJECT" in assessment.rejection_reason


def test_no_averaging_down_rule():
    """Verifies that averaging down into an existing losing position is rejected."""
    engine = RiskEngine()
    portfolio_val = 10000.0
    cash = 9000.0
    price = 48000.0  # Below entry price of 50000

    decision = Decision(action=Action.LONG, confidence=0.85, reason_code="DIP_BUY")
    assessment = engine.evaluate(
        decision=decision,
        current_price=price,
        portfolio_value=portfolio_val,
        available_cash=cash,
        has_open_position=True,
        current_position_side="LONG",
        current_position_entry_price=50000.0,  # Position in loss
    )

    assert assessment.approved is False
    assert assessment.final_action == Action.HOLD
    assert assessment.rejection_reason == "REJECT_NO_AVERAGING_DOWN"


def test_rejected_trade_flow():
    """Verifies full rejection flow: Jev -> LONG, Risk -> REJECT, Final -> HOLD."""
    engine = RiskEngine()
    decision = Decision(action=Action.LONG, confidence=0.99, reason_code="HYPER_BULLISH")

    # Force rejection via daily loss
    assessment = engine.evaluate(
        decision=decision,
        current_price=60000.0,
        portfolio_value=10000.0,
        available_cash=10000.0,
        has_open_position=False,
        daily_realized_pnl=-300.0,  # 3% daily loss
    )

    # Core requirement: Jev -> LONG, Risk -> REJECT, Final -> HOLD
    assert decision.action == Action.LONG
    assert assessment.approved is False
    assert assessment.final_action == Action.HOLD
    assert assessment.rejection_reason is not None
