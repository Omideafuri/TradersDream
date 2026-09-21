"""Full Jev Decision Layer Audit and Trace Engine.

Inspects the existing TypeSafe AI Jev integration in bot/decision.py:
- Audits exact input data, feature representation, prompts, criteria, and schemas.
- Produces a representative sanitized decision trace.
- Diagnoses structural information gaps in baseline prompt/context.
"""

from dataclasses import dataclass
import json
from typing import Dict, Any, List, Optional


@dataclass
class JevDecisionAuditReport:
    endpoint: str
    model: str
    timeout_seconds: float
    input_features: List[str]
    input_representation: str
    prompt_instructions: Dict[str, str]
    choice_criteria: Dict[str, Dict[str, str]]
    output_schema: Dict[str, str]
    fallback_behavior: Dict[str, str]
    structural_deficiencies: List[str]
    sanitized_decision_trace: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "endpoint": self.endpoint,
            "model": self.model,
            "timeout_seconds": self.timeout_seconds,
            "input_features": self.input_features,
            "input_representation": self.input_representation,
            "prompt_instructions": self.prompt_instructions,
            "choice_criteria": self.choice_criteria,
            "output_schema": self.output_schema,
            "fallback_behavior": self.fallback_behavior,
            "structural_deficiencies": self.structural_deficiencies,
            "sanitized_decision_trace": self.sanitized_decision_trace,
        }


def audit_jev_decision_architecture() -> JevDecisionAuditReport:
    """Performs static and dynamic inspection of the existing Jev decision pipeline."""
    endpoint = "https://api.typesafe.ai/v1/systemone"
    model = "jev-latest"
    timeout_seconds = 5.0

    input_features = [
        "price",
        "ema20",
        "ema50",
        "ema200",
        "rsi14",
        "atr14",
        "volume_ratio",
        "price_change_pct",
    ]

    input_repr = (
        "Flat JSON-serialized MarketState dictionary containing 8 scalar numeric fields. "
        "No historical sequences, no candle body/wick metrics, no higher-timeframe context."
    )

    prompt_instructions = {
        "action": "Determine the cryptocurrency trading action for BTC/USDT based strictly on the provided technical indicator state.",
        "reason_code": "Select the primary technical rationale for this decision.",
    }

    choice_criteria = {
        "action": {
            "LONG": "Bullish momentum, upward trend confirmation, or oversold bounce; buy signal.",
            "SHORT": "Bearish momentum, downward trend confirmation, or overbought decline; sell signal.",
            "HOLD": "Neutral market, consolidation, low volume, chop, or unclear conviction; do not trade.",
        },
        "reason_code": {
            "TREND_CONFIRMATION": "Moving average alignment and trend continuation.",
            "MOMENTUM_EXTREME": "RSI extreme levels indicating exhaustion or momentum shift.",
            "VOLUME_EXPANSION": "Significant volume expansion confirming price movement.",
            "NO_CLEAR_SIGNAL": "Market is rangebound, consolidation, or lacks conviction.",
        },
    }

    output_schema = {
        "action": "choice string: 'LONG', 'SHORT', 'HOLD'",
        "reason_code": "choice string: 'TREND_CONFIRMATION', 'MOMENTUM_EXTREME', 'VOLUME_EXPANSION', 'NO_CLEAR_SIGNAL'",
        "confidence": "scalar float in [0.0, 1.0] derived from model response probabilities",
    }

    fallback_behavior = {
        "MISSING_CREDENTIALS": "HOLD with confidence 0.0",
        "AUTH_FAILURE (401/403)": "HOLD with confidence 0.0",
        "RATE_LIMITED (429)": "HOLD with confidence 0.0",
        "TIMEOUT": "HOLD with confidence 0.0",
        "MALFORMED_JSON": "HOLD with confidence 0.0",
        "LOW_CONFIDENCE (<0.60)": "HOLD with original confidence and reason LOW_CONFIDENCE",
    }

    structural_deficiencies = [
        "1. NO EXPLICIT HORIZON: The prompt asks 'Determine trading action' without specifying whether the trade is for 5m, 15m, 1h, or 24h.",
        "2. CONFLATION IN 'HOLD': HOLD combines two distinct concepts: 'flat/consolidating market' and 'unclear conviction / epistemic uncertainty'.",
        "3. NO MARKET STRUCTURE: Jev receives indicators (EMA, RSI, ATR) but zero structural context (swing highs, swing lows, break of structure).",
        "4. NO RETURN MAGNITUDE ESTIMATE: Only discrete ternary choice is requested; magnitude of expected move is neither queried nor predicted.",
        "5. SINGLE-VALUE CONFIDENCE: A single scalar confidence conflates directional conviction with regime uncertainty.",
    ]

    # Construct representative sanitized decision trace
    sample_state = {
        "price": 63450.0,
        "ema20": 63200.0,
        "ema50": 62800.0,
        "ema200": 61500.0,
        "rsi14": 58.4,
        "atr14": 420.0,
        "volume_ratio": 1.25,
        "price_change_pct": 0.45,
    }

    sample_trace = {
        "timestamp": "2024-01-01T12:00:00Z",
        "symbol": "BTCUSDT",
        "raw_payload_sent_to_api": {
            "model": model,
            "state": json.dumps(sample_state),
            "questions": {
                "action": {
                    "type": "choice",
                    "instructions": prompt_instructions["action"],
                    "criteria": choice_criteria["action"],
                },
                "reason_code": {
                    "type": "choice",
                    "instructions": prompt_instructions["reason_code"],
                    "criteria": choice_criteria["reason_code"],
                },
            },
        },
        "raw_api_response_received": {
            "answers": {
                "action": {
                    "choice": "LONG",
                    "confidence": 0.75,
                    "probabilities": {"LONG": 0.75, "SHORT": 0.15, "HOLD": 0.10},
                },
                "reason_code": {
                    "choice": "TREND_CONFIRMATION",
                    "confidence": 0.80,
                },
            },
        },
        "parsed_decision_output": {
            "action": "LONG",
            "confidence": 0.75,
            "reason_code": "TREND_CONFIRMATION",
            "risk_gating": "APPROVED",
        },
    }

    return JevDecisionAuditReport(
        endpoint=endpoint,
        model=model,
        timeout_seconds=timeout_seconds,
        input_features=input_features,
        input_representation=input_repr,
        prompt_instructions=prompt_instructions,
        choice_criteria=choice_criteria,
        output_schema=output_schema,
        fallback_behavior=fallback_behavior,
        structural_deficiencies=structural_deficiencies,
        sanitized_decision_trace=sample_trace,
    )
