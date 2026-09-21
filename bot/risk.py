"""Deterministic Risk Engine for Crypto Trading Bot - Phase 1.

Operates completely independently of the Jev decision layer.
Enforces hard rules:
- Max risk per trade: 0.5%
- Max daily loss: 2.0%
- Max position size: 10.0% of portfolio
- Maximum 1 open position
- No leverage (strictly 1.0x)
- No averaging down
- No martingale
- Independent trade rejection capability (Jev -> LONG, Risk -> REJECT, Final -> HOLD)
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any
from bot.decision import Action, Decision


@dataclass(frozen=True)
class RiskAssessment:
    approved: bool
    final_action: Action
    rejection_reason: Optional[str]
    target_quantity: float = 0.0
    target_notional: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "approved": self.approved,
            "final_action": self.final_action.value,
            "rejection_reason": self.rejection_reason,
            "target_quantity": round(self.target_quantity, 6),
            "target_notional": round(self.target_notional, 2),
        }


class RiskEngine:
    """Independent deterministic risk management engine."""

    def __init__(
        self,
        max_risk_per_trade: float = 0.005,  # 0.5%
        max_daily_loss: float = 0.02,       # 2.0%
        max_position_size: float = 0.10,    # 10.0%
        max_open_positions: int = 1,
        leverage: float = 1.0,
    ):
        self.max_risk_per_trade = max_risk_per_trade
        self.max_daily_loss = max_daily_loss
        self.max_position_size = max_position_size
        self.max_open_positions = max_open_positions
        self.leverage = leverage
        
        # State tracking for safety rules
        self.last_trade_pnl: float = 0.0
        self.base_position_size_usd: Optional[float] = None

    def evaluate(
        self,
        decision: Decision,
        current_price: float,
        portfolio_value: float,
        available_cash: float,
        has_open_position: bool,
        current_position_side: Optional[str] = None,
        current_position_entry_price: float = 0.0,
        daily_realized_pnl: float = 0.0,
        atr14: float = 0.0,
    ) -> RiskAssessment:
        """Evaluates Jev decision against all risk rules.
        
        Returns RiskAssessment with approved flag and final action.
        """
        # If Jev decided HOLD, Risk approves HOLD
        if decision.action == Action.HOLD:
            return RiskAssessment(
                approved=True,
                final_action=Action.HOLD,
                rejection_reason=None,
                target_quantity=0.0,
                target_notional=0.0,
            )

        # 1. Check Maximum Daily Loss Limit (2.0%)
        # If cumulative daily realized PnL is negative and >= 2% of portfolio value:
        max_allowed_daily_loss = portfolio_value * self.max_daily_loss
        if daily_realized_pnl < 0 and abs(daily_realized_pnl) >= max_allowed_daily_loss:
            return RiskAssessment(
                approved=False,
                final_action=Action.HOLD,
                rejection_reason="REJECT_DAILY_LOSS_LIMIT_REACHED",
            )

        # 2. Check Closing / Exiting Open Position
        if has_open_position:
            # If in LONG and decision is SHORT -> allowed to close/exit
            if (current_position_side == "LONG" and decision.action == Action.SHORT) or \
               (current_position_side == "SHORT" and decision.action == Action.LONG):
                # Valid exit signal
                return RiskAssessment(
                    approved=True,
                    final_action=decision.action,
                    rejection_reason=None,
                    target_quantity=0.0,
                )

            # If attempting to add in same direction:
            # Check No Averaging Down
            if current_position_side == decision.action.value:
                if (current_position_side == "LONG" and current_price < current_position_entry_price) or \
                   (current_position_side == "SHORT" and current_price > current_position_entry_price):
                    return RiskAssessment(
                        approved=False,
                        final_action=Action.HOLD,
                        rejection_reason="REJECT_NO_AVERAGING_DOWN",
                    )

            # Check Maximum 1 Open Position Rule
            return RiskAssessment(
                approved=False,
                final_action=Action.HOLD,
                rejection_reason="REJECT_MAX_OPEN_POSITIONS_REACHED",
            )

        # 3. Strictly No Leverage Enforced (leverage == 1.0)
        if self.leverage > 1.0:
            return RiskAssessment(
                approved=False,
                final_action=Action.HOLD,
                rejection_reason="REJECT_LEVERAGE_NOT_ALLOWED",
            )

        # 4. Position Sizing & Max Risk Calculation
        # Max position notional = 10% of portfolio
        max_notional_cap = portfolio_value * self.max_position_size

        # Max dollar risk per trade = 0.5% of portfolio
        max_risk_dollars = portfolio_value * self.max_risk_per_trade

        # Stop loss distance calculation using ATR (fallback to 1.5% if ATR invalid)
        stop_distance = atr14 * 1.5 if atr14 > 0 else current_price * 0.015

        # Risk-based notional: (max_risk_dollars / (stop_distance / current_price))
        risk_based_notional = max_risk_dollars / (stop_distance / current_price) if stop_distance > 0 else max_notional_cap

        # Target notional is minimum of:
        # a) Max 10% portfolio cap
        # b) Risk-based notional (0.5% max risk)
        # c) Available cash (no leverage)
        target_notional = min(max_notional_cap, risk_based_notional, available_cash)

        # 5. Check Anti-Martingale / Revenge Trading Sizing Rule:
        # If the last trade was a loss, target_notional must not exceed previous base sizing
        if self.last_trade_pnl < 0 and self.base_position_size_usd is not None:
            if target_notional > self.base_position_size_usd:
                target_notional = self.base_position_size_usd

        if target_notional <= 0 or current_price <= 0:
            return RiskAssessment(
                approved=False,
                final_action=Action.HOLD,
                rejection_reason="REJECT_INSUFFICIENT_FUNDS_OR_ZERO_PRICE",
            )

        # Calculate coin quantity
        target_quantity = target_notional / current_price

        # Record base size
        self.base_position_size_usd = target_notional

        return RiskAssessment(
            approved=True,
            final_action=decision.action,
            rejection_reason=None,
            target_quantity=target_quantity,
            target_notional=target_notional,
        )

    def record_closed_trade(self, pnl: float) -> None:
        """Updates internal state following a completed trade."""
        self.last_trade_pnl = pnl
