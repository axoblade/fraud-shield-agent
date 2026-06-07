"""
gemini_client.py - Day 3 Gemini Agent Core
Wraps Google Gemini 3 (gemini-2.0-flash) for fraud risk reasoning.

Usage:
    from agent.gemini_client import GeminiClient

    gemini = GeminiClient()
    decision = gemini.reason_about_transaction(context_dict)
    # → {"risk_score": 87, "risk_level": "high", "action": "block", ...}
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict

import google.generativeai as genai
from dotenv import load_dotenv
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_fixed

load_dotenv()

# ── The exact prompt template from the FraudShield spec ───────────
PROMPT_TEMPLATE = """You are FraudShield, an expert fraud detection AI for a mobile money platform.

Analyze the following transaction and context, then return a fraud risk assessment.

CURRENT TRANSACTION:
- Account: {nameOrig}
- Type: {type}
- Amount: ${amount:,.2f}
- Time Step: {step}
- Destination: {nameDest}
- Old Balance (origin): ${oldbalanceOrg:,.2f}
- New Balance (origin): ${newbalanceOrig:,.2f}

ACCOUNT ACTIVITY (last 24 hours):
- Transactions: {transaction_count}
- Total Amount: ${total_amount:,.2f}
- Average per transaction: ${avg_amount:,.2f}
- Transaction types seen: {types}

HISTORICAL BASELINE (normal behavior):
- Typical weekly transactions: {avg_weekly_transactions}
- Typical weekly spend: ${avg_weekly_amount:,.2f}

RISK SIGNALS:
- Recipient account flagged as mule: {recipient_flagged}
- Velocity score (1-10, higher = more suspicious): {velocity_score}

INSTRUCTIONS:
1. Compare the current transaction against the historical baseline
2. Assess whether the 24h activity pattern is unusual
3. Consider the transaction type (CASH_OUT and TRANSFER are highest risk)
4. Factor in whether the recipient is a known mule account
5. Produce a risk score from 0 to 100 where:
   - 0-30 = Normal, allow the transaction
   - 31-60 = Suspicious, flag for human review
   - 61-100 = High risk, block the transaction immediately

Respond with ONLY a valid JSON object. No explanation outside the JSON. No markdown.

{{
  "risk_score": <integer 0-100>,
  "risk_level": "<low|medium|high>",
  "action": "<allow|flag|block>",
  "reasoning": "<2-3 sentence explanation of the key signals that drove this score>",
  "key_signals": ["<signal 1>", "<signal 2>", "<signal 3>"]
}}"""


class GeminiClient:
    """Thin wrapper around Google Gemini for fraud risk assessment."""

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str = "gemini-2.5-flash",
    ) -> None:
        """
        Parameters
        ----------
        api_key : str | None
            Gemini API key.  Falls back to ``GEMINI_API_KEY`` env var.
        model_name : str
            Model to use (default ``gemini-2.0-flash`` for speed/cost).
        """
        key = api_key or os.getenv("GEMINI_API_KEY", "")
        if not key:
            raise ValueError(
                "GEMINI_API_KEY is not set.  "
                "Export it or pass api_key to the constructor."
            )

        genai.configure(api_key=key)
        self.model = genai.GenerativeModel(model_name)
        logger.debug(f"GeminiClient initialised with model={model_name}")

    # ── Public API ────────────────────────────────────────────────

    def reason_about_transaction(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyse a transaction + context and return a risk decision.

        Parameters
        ----------
        context : dict
            Pre-assembled context with keys:
            ``transaction``, ``history_24h``, ``baseline``,
            ``recipient_flagged``, ``velocity_score``.

        Returns
        -------
        dict
            ``{"risk_score": int, "risk_level": str, "action": str,
               "reasoning": str, "key_signals": list[str]}``
        """
        txn = context.get("transaction", {})
        hist = context.get("history_24h", {})
        baseline = context.get("baseline", {})

        types_list = hist.get("types", [])
        types_str = ", ".join(types_list[:10]) if types_list else "none"

        prompt = PROMPT_TEMPLATE.format(
            nameOrig=txn.get("nameOrig", "unknown"),
            type=txn.get("type", "unknown"),
            amount=txn.get("amount", 0),
            step=txn.get("step", 0),
            nameDest=txn.get("nameDest", "unknown"),
            oldbalanceOrg=txn.get("oldbalanceOrg", 0),
            newbalanceOrig=txn.get("newbalanceOrig", 0),
            transaction_count=hist.get("transaction_count", 0),
            total_amount=hist.get("total_amount", 0),
            avg_amount=hist.get("avg_amount", 0),
            types=types_str,
            avg_weekly_transactions=baseline.get("avg_weekly_transactions", 0),
            avg_weekly_amount=baseline.get("avg_weekly_amount", 0),
            recipient_flagged=context.get("recipient_flagged", False),
            velocity_score=context.get("velocity_score", 0),
        )

        logger.debug("Calling Gemini for risk assessment...")
        try:
            return self._call_with_retry(prompt)
        except Exception as exc:
            logger.warning(
                f"Gemini unreachable ({exc}), falling back to heuristic scoring"
            )
            return self.heuristic_decision(context)

    # ── Internal ──────────────────────────────────────────────────

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(1), reraise=True)
    def _call_with_retry(self, prompt: str) -> Dict[str, Any]:
        """Call Gemini with retry on malformed JSON or transient errors.

        Falls back to a heuristic score if the API is unreachable after
        all retries (e.g. quota / key issues during development).
        """
        try:
            response = self.model.generate_content(prompt)
        except Exception as api_exc:
            logger.error(f"Gemini API call failed: {api_exc}")
            raise

        text = response.text
        logger.debug(f"Gemini raw response ({len(text)} chars): {text[:120]}...")

        # ── Robust JSON extraction ────────────────────────────────
        # 1. Strip markdown code fences
        cleaned = text.strip()
        if cleaned.startswith("```"):
            # Split on ``` and take the middle block
            blocks = cleaned.split("```")
            # blocks = ["", "json\n{...}", ""]  or  ["", "{...}", ""]
            if len(blocks) >= 2:
                cleaned = blocks[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
            cleaned = cleaned.strip()

        # 2. Find the outermost JSON object
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            cleaned = cleaned[start : end + 1]

        # 3. Parse
        try:
            decision = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning(
                f"Gemini returned malformed JSON after cleaning; "
                f"raw starts: {text[:200]}"
            )
            raise

        # Validate required fields
        required = {"risk_score", "risk_level", "action", "reasoning", "key_signals"}
        missing = required - set(decision.keys())
        if missing:
            raise ValueError(f"Gemini response missing fields: {missing}")

        # Coerce risk_score to int
        try:
            decision["risk_score"] = int(decision["risk_score"])
        except (ValueError, TypeError):
            raise ValueError(
                f"Gemini returned non-integer risk_score: {decision.get('risk_score')}"
            )

        logger.debug(
            f"Gemini → risk_score={decision['risk_score']} "
            f"action={decision['action']}"
        )
        return decision

    @staticmethod
    def heuristic_decision(context: Dict[str, Any]) -> Dict[str, Any]:
        """Rule-based fallback when Gemini is unreachable.

        Produces a risk score from velocity, amount anomaly, and mule
        status so the 7-step pipeline still works during development.
        """
        txn = context.get("transaction", {})
        hist = context.get("history_24h", {})
        baseline = context.get("baseline", {})
        velocity = context.get("velocity_score", 1)
        recipient_flagged = context.get("recipient_flagged", False)

        score = 10.0  # base

        # Velocity contribution (0-30 points)
        score += min(30, velocity * 3)

        # Transaction type risk (0-20 points)
        txn_type = txn.get("type", "")
        if txn_type == "CASH_OUT":
            score += 20
        elif txn_type == "TRANSFER":
            score += 15
        elif txn_type == "DEBIT":
            score += 5

        # Amount anomaly vs baseline (0-20 points)
        avg_weekly = baseline.get("avg_weekly_amount", 0)
        amount = txn.get("amount", 0)
        if avg_weekly > 0 and amount > avg_weekly * 3:
            score += 20
        elif avg_weekly > 0 and amount > avg_weekly * 1.5:
            score += 10

        # 24h activity burst (0-15 points)
        hist_count = hist.get("transaction_count", 0)
        if hist_count > 20:
            score += 15
        elif hist_count > 10:
            score += 10
        elif hist_count > 5:
            score += 5

        # Mule recipient (0-15 points)
        if recipient_flagged:
            score += 15

        score = min(100, int(score))

        if score >= 61:
            level, action = "high", "block"
        elif score >= 31:
            level, action = "medium", "flag"
        else:
            level, action = "low", "allow"

        signals = []
        if velocity >= 6:
            signals.append("velocity_spike")
        if txn_type in ("CASH_OUT", "TRANSFER"):
            signals.append(f"high_risk_type_{txn_type.lower()}")
        if amount > 5000:
            signals.append("large_amount")
        if recipient_flagged:
            signals.append("mule_recipient")
        if hist_count > 10:
            signals.append("unusual_24h_activity")
        if not signals:
            signals.append("normal_pattern")

        return {
            "risk_score": score,
            "risk_level": level,
            "action": action,
            "reasoning": (
                f"Heuristic assessment: velocity={velocity}/10, "
                f"type={txn_type}, 24h_txns={hist_count}, "
                f"mule_recipient={recipient_flagged}. "
                f"Score={score}/100 → {action}."
            ),
            "key_signals": signals,
        }
