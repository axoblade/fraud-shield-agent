"""
actions.py — Day 4 Actions & Alerts
Executes allow / flag / block decisions and sends SMS alerts.

Usage:
    from agent.actions import ActionExecutor

    executor = ActionExecutor(mcp_client)
    result = await executor.execute(transaction, decision)
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from loguru import logger

from agent.mongo_mcp import MCPConnectionError, MongoDBMCPClient

load_dotenv()

RISK_BLOCK_THRESHOLD = int(os.getenv("RISK_BLOCK_THRESHOLD", "61"))
RISK_FLAG_THRESHOLD = int(os.getenv("RISK_FLAG_THRESHOLD", "31"))

# ── SMS helper (generic — plug in your own provider) ──────────────

def send_sms(message: str, recipients: Optional[list] = None) -> bool:
    """Send an SMS alert.  Logs to console by default.

    Replace the body of this function with your own SMS provider
    integration (Africa's Talking, Twilio, Vonage, etc.).

    Returns True if the message was sent successfully.
    """
    logger.info(f"📱 SMS | recipients={recipients} | {message[:120]}")
    # TODO: plug in your SMS provider here, e.g.:
    #
    #   import africastalking
    #   africastalking.initialize(username=..., api_key=...)
    #   africastalking.SMS.send(message, recipients, sender_id=...)
    #
    return True


# ── Action Executor ───────────────────────────────────────────────

class ActionExecutor:
    """Executes risk decisions: allow, flag, or block.

    - Block: log alert, update risk profile, send SMS
    - Flag:  log alert, update risk profile
    - Allow: update risk profile with normal activity
    """

    def __init__(self, mcp: MongoDBMCPClient) -> None:
        self._mcp = mcp

    # ── Public API ────────────────────────────────────────────────

    async def execute(
        self, transaction: Dict[str, Any], decision: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Route to the correct action based on risk_score."""
        score = decision.get("risk_score", 0)

        if score >= RISK_BLOCK_THRESHOLD:
            return await self._block(transaction, decision)
        elif score >= RISK_FLAG_THRESHOLD:
            return await self._flag(transaction, decision)
        else:
            return await self._allow(transaction, decision)

    # ── Action methods ────────────────────────────────────────────

    async def _block(
        self, transaction: Dict[str, Any], decision: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Full enforcement: alert, risk update, SMS."""
        alert_id = await self._insert_alert(transaction, decision, priority="high")
        await self._upsert_risk_score(transaction, decision, blocked=True)
        sms_sent = False

        if alert_id:
            txn_type = transaction.get("type", "UNKNOWN")
            amount = transaction.get("amount", 0)
            score = decision.get("risk_score", 0)
            message = (
                f"FraudShield Alert: A {txn_type} of ${amount:,.2f} on "
                f"your account has been BLOCKED due to suspicious activity "
                f"(Risk Score: {score}/100). "
                f"If this was you, contact support immediately. Ref: {alert_id}"
            )
            sms_sent = send_sms(message)

        return {
            "action": "block",
            "alert_id": alert_id,
            "sms_sent": sms_sent,
        }

    async def _flag(
        self, transaction: Dict[str, Any], decision: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Elevate for human review: alert + risk update, no SMS."""
        alert_id = await self._insert_alert(transaction, decision, priority="medium")
        await self._upsert_risk_score(transaction, decision, blocked=False)

        return {
            "action": "flag",
            "alert_id": alert_id,
        }

    async def _allow(
        self, transaction: Dict[str, Any], decision: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Normal transaction: update risk profile only."""
        await self._upsert_risk_score(transaction, decision, blocked=False)

        return {"action": "allow"}

    # ── Database helpers ──────────────────────────────────────────

    async def _insert_alert(
        self,
        transaction: Dict[str, Any],
        decision: Dict[str, Any],
        priority: str = "medium",
    ) -> str:
        """Insert an alert document into fraudshield.alerts."""
        now = datetime.now(timezone.utc).isoformat()
        doc = {
            "transaction": transaction,
            "risk_score": decision.get("risk_score", 0),
            "risk_level": decision.get("risk_level", "unknown"),
            "action": decision.get("action", "unknown"),
            "reasoning": decision.get("reasoning", ""),
            "key_signals": decision.get("key_signals", []),
            "priority": priority,
            "timestamp": now,
            "resolved": False,
            "false_positive": None,
        }
        try:
            doc_id = await self._mcp.insert_one("alerts", doc)
            logger.debug(f"Alert logged → {doc_id}")
            return doc_id
        except MCPConnectionError:
            logger.error("Failed to insert alert document")
            return ""

    async def _upsert_risk_score(
        self,
        transaction: Dict[str, Any],
        decision: Dict[str, Any],
        blocked: bool = False,
    ) -> None:
        """Update (or create) the per-account risk profile.

        Uses update-many with upsert-like semantics: if the account doc
        doesn't exist in fraudshield.risk_scores, the first update does
        nothing, but we follow up with a separate insert.
        """
        name_orig = transaction.get("nameOrig", "")
        if not name_orig:
            return

        score = decision.get("risk_score", 0)
        now = datetime.now(timezone.utc).isoformat()

        try:
            # Try to update an existing risk_score document
            await self._mcp.update_one(
                "risk_scores",
                {"nameOrig": name_orig},
                {
                    "$set": {
                        "nameOrig": name_orig,
                        "last_seen": now,
                        "last_risk_score": score,
                    },
                    "$inc": {
                        "total_transactions": 1,
                        "total_blocked": 1 if blocked else 0,
                        "total_flagged": 0 if blocked else 1 if score >= RISK_FLAG_THRESHOLD else 0,
                    },
                    "$push": {
                        "score_history": {
                            "$each": [score],
                            "$slice": -20,
                        },
                    },
                },
            )
        except MCPConnectionError:
            logger.warning(f"risk_scores update failed for {name_orig}, trying insert")
            try:
                await self._mcp.insert_one(
                    "risk_scores",
                    {
                        "nameOrig": name_orig,
                        "last_seen": now,
                        "last_risk_score": score,
                        "total_transactions": 1,
                        "total_blocked": 1 if blocked else 0,
                        "total_flagged": 0 if blocked else 1 if score >= RISK_FLAG_THRESHOLD else 0,
                        "score_history": [score],
                    },
                )
            except MCPConnectionError:
                logger.error(f"Failed to create risk_scores doc for {name_orig}")
