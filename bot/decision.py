"""Jev Decision Layer for Crypto Trading Bot - Phase 1.1.

Integrates with TypeSafe AI's Jev "System One" decision model via public HTTP endpoint.
Restricts the decision space strictly to LONG, SHORT, HOLD.
Never allows arbitrary text commands.
Applies confidence thresholds and failsafe HOLD fallbacks for timeouts, auth errors, or malformed data.
Keeps API credentials strictly confidential (never logs or prints tokens).
"""

from dataclasses import dataclass
from enum import Enum
import json
import logging
from typing import Any, Dict, Optional, Protocol
import asyncio
import httpx

from bot.indicators import MarketState

logger = logging.getLogger("crypto_bot.decision")


class Action(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    HOLD = "HOLD"


@dataclass(frozen=True)
class Decision:
    action: Action
    confidence: float
    reason_code: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action.value,
            "confidence": round(self.confidence, 4),
            "reason_code": self.reason_code,
        }


class DecisionProvider(Protocol):
    """Protocol for Jev decision implementations."""
    async def decide_raw(self, state_dict: Dict[str, Any]) -> Any:
        ...


class RuleBasedJev:
    """Deterministic baseline provider kept for unit testing and offline simulation."""
    async def decide_raw(self, state_dict: Dict[str, Any]) -> Dict[str, Any]:
        price = state_dict.get("price", 0.0)
        ema20 = state_dict.get("ema20", 0.0)
        ema50 = state_dict.get("ema50", 0.0)
        rsi14 = state_dict.get("rsi14", 50.0)
        vol_ratio = state_dict.get("volume_ratio", 1.0)

        # Baseline deterministic trend check
        if price > ema20 > ema50 and rsi14 < 70 and vol_ratio > 1.0:
            return {
                "action": "LONG",
                "confidence": 0.75,
                "reason_code": "TREND_CONFIRMATION",
            }
        elif price < ema20 < ema50 and rsi14 > 30 and vol_ratio > 1.0:
            return {
                "action": "SHORT",
                "confidence": 0.70,
                "reason_code": "DOWNTREND_CONFIRMATION",
            }
        else:
            return {
                "action": "HOLD",
                "confidence": 0.50,
                "reason_code": "NO_CLEAR_SIGNAL",
            }


class JevApiProvider:
    """Production provider connecting directly to TypeSafe AI's Jev System One API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        endpoint: str = "https://api.typesafe.ai/v1/systemone",
        model: str = "jev-latest",
        timeout_seconds: float = 5.0,
    ):
        self._api_key = api_key
        self.endpoint = endpoint
        self.model = model
        self.timeout_seconds = timeout_seconds

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key and self._api_key.strip())

    async def decide_raw(self, state_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatches structured questions to Jev API."""
        if not self.is_configured:
            return {
                "action": "HOLD",
                "confidence": 0.0,
                "reason_code": "MISSING_CREDENTIALS",
            }

        # Build structured systemone request payload
        payload = {
            "model": self.model,
            "state": json.dumps(state_dict),
            "questions": {
                "action": {
                    "type": "choice",
                    "instructions": "Determine the cryptocurrency trading action for BTC/USDT based strictly on the provided technical indicator state.",
                    "criteria": {
                        "LONG": "Bullish momentum, upward trend confirmation, or oversold bounce; buy signal.",
                        "SHORT": "Bearish momentum, downward trend confirmation, or overbought decline; sell signal.",
                        "HOLD": "Neutral market, consolidation, low volume, chop, or unclear conviction; do not trade.",
                    },
                },
                "reason_code": {
                    "type": "choice",
                    "instructions": "Select the primary technical rationale for this decision.",
                    "criteria": {
                        "TREND_CONFIRMATION": "Moving average alignment and trend continuation.",
                        "MOMENTUM_EXTREME": "RSI extreme levels indicating exhaustion or momentum shift.",
                        "VOLUME_EXPANSION": "Significant volume expansion confirming price movement.",
                        "NO_CLEAR_SIGNAL": "Market is rangebound, consolidation, or lacks conviction.",
                    },
                },
            },
        }

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(self.endpoint, json=payload, headers=headers)

                if response.status_code in (401, 403):
                    return {
                        "action": "HOLD",
                        "confidence": 0.0,
                        "reason_code": "AUTH_FAILURE",
                    }
                elif response.status_code == 429:
                    return {
                        "action": "HOLD",
                        "confidence": 0.0,
                        "reason_code": "RATE_LIMITED",
                    }
                elif response.status_code >= 400:
                    return {
                        "action": "HOLD",
                        "confidence": 0.0,
                        "reason_code": f"HTTP_ERROR_{response.status_code}",
                    }

                data = response.json()
                return self._parse_systemone_response(data)

        except httpx.TimeoutException:
            raise asyncio.TimeoutError()
        except Exception as exc:
            # Re-raise to let engine map it to PROVIDER_EXCEPTION safely without printing secrets
            raise RuntimeError(f"Network error: {type(exc).__name__}")

    @staticmethod
    def _parse_systemone_response(data: Dict[str, Any]) -> Dict[str, Any]:
        """Parses TypeSafe SystemOne response format into standard decision dict."""
        # Check standard answers structure
        if "answers" in data and isinstance(data["answers"], dict):
            answers = data["answers"]
            action_ans = answers.get("action", {})
            reason_ans = answers.get("reason_code", {})

            choice = action_ans.get("choice", "HOLD")
            confidence = action_ans.get("confidence", 0.0)
            reason_code = reason_ans.get("choice", "AI_DECISION")

            return {
                "action": choice,
                "confidence": confidence,
                "reason_code": reason_code,
            }

        # Check flat format if returned directly
        if "action" in data:
            return {
                "action": data.get("action", "HOLD"),
                "confidence": data.get("confidence", 0.0),
                "reason_code": data.get("reason_code", "AI_DECISION"),
            }

        return {
            "action": "HOLD",
            "confidence": 0.0,
            "reason_code": "MALFORMED_RESPONSE",
        }


class JevDecisionEngine:
    """Isolated decision coordinator with strict schema validation, threshold gating, and timeout protection."""

    def __init__(
        self,
        provider: Optional[DecisionProvider] = None,
        timeout_seconds: float = 5.0,
        confidence_threshold: float = 0.60,
    ):
        self.provider = provider or JevApiProvider()
        self.timeout_seconds = timeout_seconds
        self.confidence_threshold = confidence_threshold

    @staticmethod
    def fallback_hold(reason_code: str = "ERROR_FALLBACK") -> Decision:
        """Safe invariant fallback: always returns HOLD with 0.0 confidence."""
        return Decision(
            action=Action.HOLD,
            confidence=0.0,
            reason_code=reason_code,
        )

    def validate_and_sanitize(self, raw_data: Any) -> Decision:
        """Strictly validates raw decision output.
        
        Rejects arbitrary strings, missing fields, or out-of-bounds confidence.
        Any unexpected format immediately maps to HOLD.
        """
        if isinstance(raw_data, str):
            try:
                raw_data = json.loads(raw_data)
            except Exception:
                return self.fallback_hold("INVALID_JSON_RESPONSE")

        if not isinstance(raw_data, dict):
            return self.fallback_hold("NON_DICT_RESPONSE")

        # Normalize TypeSafe SystemOne format if provided
        if "answers" in raw_data and isinstance(raw_data["answers"], dict):
            raw_data = JevApiProvider._parse_systemone_response(raw_data)

        raw_action = str(raw_data.get("action", "")).strip().upper()
        if raw_action not in {a.value for a in Action}:
            return self.fallback_hold(f"INVALID_ACTION_{raw_action}")

        # Validate confidence
        try:
            confidence = float(raw_data.get("confidence", 0.0))
            if not (0.0 <= confidence <= 1.0):
                confidence = max(0.0, min(1.0, confidence))
        except (ValueError, TypeError):
            return self.fallback_hold("INVALID_CONFIDENCE_VALUE")

        reason_code = str(raw_data.get("reason_code", "UNKNOWN")).strip().upper()
        if not reason_code:
            reason_code = "UNSPECIFIED"

        # Apply confidence threshold gating
        # If action is LONG or SHORT but confidence is below required threshold, force HOLD
        if Action(raw_action) != Action.HOLD and confidence < self.confidence_threshold:
            return Decision(
                action=Action.HOLD,
                confidence=confidence,
                reason_code="LOW_CONFIDENCE",
            )

        return Decision(
            action=Action(raw_action),
            confidence=confidence,
            reason_code=reason_code,
        )

    async def get_decision(self, market_state: MarketState) -> Decision:
        """Requests decision from provider with timeout protection.
        
        Feeds ONLY structured dictionary to the provider.
        Never allows unhandled exceptions or timeouts to initiate trades.
        """
        state_payload = market_state.to_dict()

        try:
            raw_result = await asyncio.wait_for(
                self.provider.decide_raw(state_payload),
                timeout=self.timeout_seconds,
            )
            return self.validate_and_sanitize(raw_result)
        except asyncio.TimeoutError:
            return self.fallback_hold("TIMEOUT_FALLBACK")
        except Exception as exc:
            # Safely report error name without secret exposure
            return self.fallback_hold(f"PROVIDER_EXCEPTION_{type(exc).__name__}")
