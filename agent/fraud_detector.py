"""
fraud_detector.py — Day 3 Core Agent Workflow
Orchestrates the 7-step fraud detection pipeline:
  validate → history → velocity → mule check → baseline → Gemini → action

Usage:
    from agent.fraud_detector import FraudDetectorAgent

    agent = FraudDetectorAgent()
    result = await agent.evaluate_transaction(txn_dict)
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List

from dotenv import load_dotenv
from loguru import logger

from agent.gemini_client import GeminiClient
from agent.mongo_mcp import MCPConnectionError, MongoDBMCPClient

load_dotenv()

# ── Thresholds ────────────────────────────────────────────────────
RISK_BLOCK_THRESHOLD = int(os.getenv("RISK_BLOCK_THRESHOLD", "61"))
RISK_FLAG_THRESHOLD = int(os.getenv("RISK_FLAG_THRESHOLD", "31"))


class FraudDetectorAgent:
    """Autonomous agent that evaluates a transaction and returns a risk decision.

    Orchestrates 7 steps using the MCP client (MongoDB) and Gemini.
    """

    def __init__(
        self,
        mcp: MongoDBMCPClient | None = None,
        gemini: GeminiClient | None = None,
    ) -> None:
        """
        Parameters
        ----------
        mcp : MongoDBMCPClient | None
            Pre-configured MCP client; created automatically if omitted.
        gemini : GeminiClient | None
            Pre-configured Gemini client; created automatically if omitted.
        """
        self._mcp = mcp  # set externally or created lazily
        self._gemini = gemini
        self._own_mcp = mcp is None

    async def _get_mcp(self) -> MongoDBMCPClient:
        if self._mcp is None:
            self._mcp = MongoDBMCPClient()
            await self._mcp.connect()
        return self._mcp

    def _get_gemini(self) -> GeminiClient:
        if self._gemini is None:
            self._gemini = GeminiClient()
        return self._gemini

    # ── Main entry point ──────────────────────────────────────────

    async def evaluate_transaction(self, transaction: Dict[str, Any]) -> Dict[str, Any]:
        """Run the full 7-step fraud detection pipeline.

        Returns a dict with ``transaction``, ``decision``, ``steps``,
        and ``elapsed_ms``.
        """
        t0 = time.time()
        mcp = await self._get_mcp()
        gemini = self._get_gemini()

        # ── Step 1: Validate input ─────────────────────────────────
        self._validate(transaction)
        name_orig = transaction["nameOrig"]
        name_dest = transaction["nameDest"]
        txn_step = transaction["step"]
        txn_amount = transaction["amount"]

        # ── Step 2: Fetch 24h history ──────────────────────────────
        history_24h = await self._fetch_history(mcp, name_orig, txn_step)

        # ── Step 3: Calculate velocity score ───────────────────────
        velocity = await self._calculate_velocity(mcp, name_orig, txn_step, history_24h)

        # ── Step 4: Check if recipient is a known mule ─────────────
        recipient_flagged = await self._check_mule(mcp, name_dest)

        # ── Step 5: Get historical baseline ────────────────────────
        baseline = await self._get_baseline(mcp, name_orig)

        # ── Step 6: Assemble context & call Gemini ─────────────────
        context = {
            "transaction": {
                "nameOrig": name_orig,
                "type": transaction["type"],
                "amount": txn_amount,
                "step": txn_step,
                "nameDest": name_dest,
                "oldbalanceOrg": transaction.get("oldbalanceOrg", 0),
                "newbalanceOrig": transaction.get("newbalanceOrig", 0),
            },
            "history_24h": history_24h,
            "baseline": baseline,
            "recipient_flagged": recipient_flagged,
            "velocity_score": velocity,
        }
        decision = gemini.reason_about_transaction(context)

        # ── Step 7: Route action ───────────────────────────────────
        action_result = await self._execute_action(mcp, transaction, decision)

        elapsed = (time.time() - t0) * 1000
        logger.info(
            f"evaluate_transaction | {name_orig} | "
            f"${txn_amount:,.0f} | risk={decision['risk_score']} | "
            f"action={decision['action'].upper()} | {elapsed:.0f}ms"
        )

        return {
            "transaction": transaction,
            "decision": decision,
            "action_result": action_result,
            "steps": {
                "history_count": history_24h.get("transaction_count", 0),
                "velocity_score": velocity,
                "recipient_flagged": recipient_flagged,
                "baseline": baseline,
            },
            "elapsed_ms": round(elapsed),
        }

    # ── Step helpers ───────────────────────────────────────────────

    @staticmethod
    def _validate(txn: Dict[str, Any]) -> None:
        required = {"step", "type", "amount", "nameOrig", "nameDest"}
        missing = required - set(txn.keys())
        if missing:
            raise ValueError(f"Transaction missing required fields: {missing}")

    async def _fetch_history(
        self, mcp: MongoDBMCPClient, name_orig: str, step: int
    ) -> Dict[str, Any]:
        """Fetch the account's last 24 hours of transactions."""
        try:
            docs = await mcp.find(
                "transactions",
                {"nameOrig": name_orig, "step": {"$gte": max(0, step - 24)}},
                limit=500,
            )
        except MCPConnectionError:
            logger.warning(f"History lookup failed for {name_orig}, using empty history")
            docs = []

        if not docs:
            return {"transaction_count": 0, "total_amount": 0, "types": [], "avg_amount": 0}

        amounts = [d.get("amount", 0) for d in docs]
        types = [d.get("type", "?") for d in docs]
        total = sum(amounts)
        count = len(docs)

        return {
            "transaction_count": count,
            "total_amount": total,
            "types": types,
            "avg_amount": round(total / count, 2) if count else 0,
        }

    async def _calculate_velocity(
        self,
        mcp: MongoDBMCPClient,
        name_orig: str,
        step: int,
        history: Dict[str, Any],
    ) -> float:
        """Calculate a velocity score (1-10) from recent activity."""
        count = history.get("transaction_count", 0)
        if count == 0:
            return 1.0

        # Base score: more transactions → higher velocity
        # Scale: 0-5 txns → 1-3, 5-10 → 3-6, 10-20 → 6-8, 20+ → 8-10
        if count <= 5:
            base = 1.0 + (count / 5.0) * 2.0
        elif count <= 10:
            base = 3.0 + ((count - 5) / 5.0) * 3.0
        elif count <= 20:
            base = 6.0 + ((count - 10) / 10.0) * 2.0
        else:
            base = 8.0 + min(2.0, (count - 20) / 20.0 * 2.0)

        # Bonus for CASH_OUT or TRANSFER dominance
        types = history.get("types", [])
        high_risk_count = sum(1 for t in types if t in ("CASH_OUT", "TRANSFER"))
        if count > 0:
            high_risk_ratio = high_risk_count / count
            if high_risk_ratio > 0.8:
                base += 1.5
            elif high_risk_ratio > 0.5:
                base += 0.5

        # Try aggregation for additional signals
        try:
            agg_result = await mcp.aggregate(
                "transactions",
                [
                    {"$match": {"nameOrig": name_orig, "step": {"$gte": max(0, step - 24)}}},
                    {
                        "$group": {
                            "_id": None,
                            "max_single": {"$max": "$amount"},
                            "count": {"$sum": 1},
                        },
                    },
                ],
            )
            if agg_result:
                r = agg_result[0]
                agg_count = r.get("count", 0)
                if agg_count > 10:
                    base += 1.0
        except MCPConnectionError:
            pass

        return round(min(10.0, max(1.0, base)), 1)

    async def _check_mule(self, mcp: MongoDBMCPClient, name_dest: str) -> bool:
        """Check whether the destination account is flagged as a mule."""
        try:
            results = await mcp.find(
                "flagged_accounts",
                {"accountId": name_dest},
                limit=1,
            )
            return len(results) > 0
        except MCPConnectionError:
            logger.warning(f"Mule check failed for {name_dest}, assuming not flagged")
            return False

    async def _get_baseline(
        self, mcp: MongoDBMCPClient, name_orig: str
    ) -> Dict[str, Any]:
        """Compute the account's historical weekly baseline.

        Falls back to conservative defaults for new accounts.
        """
        try:
            count_result = await mcp.count("transactions", {"nameOrig": name_orig})
            if count_result == 0:
                return {"avg_weekly_transactions": 0, "avg_weekly_amount": 0}

            # Get the full date range for this account
            agg_result = await mcp.aggregate(
                "transactions",
                [
                    {"$match": {"nameOrig": name_orig}},
                    {
                        "$group": {
                            "_id": None,
                            "total_txns": {"$sum": 1},
                            "total_amount": {"$sum": "$amount"},
                            "min_step": {"$min": "$step"},
                            "max_step": {"$max": "$step"},
                        },
                    },
                ],
            )
            if agg_result:
                r = agg_result[0]
                total_txns = r.get("total_txns", 0)
                total_amount = r.get("total_amount", 0)
                week_span = max(1, (r.get("max_step", 0) - r.get("min_step", 0)) / 168)
                return {
                    "avg_weekly_transactions": round(total_txns / week_span, 1),
                    "avg_weekly_amount": round(total_amount / week_span, 2),
                }
        except MCPConnectionError:
            logger.warning(f"Baseline lookup failed for {name_orig}")

        return {"avg_weekly_transactions": 0, "avg_weekly_amount": 0}

    async def _execute_action(
        self,
        mcp: MongoDBMCPClient,
        transaction: Dict[str, Any],
        decision: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Log the decision to MongoDB (action execution is Day 4)."""
        try:
            doc_id = await mcp.insert_one(
                "alerts",
                {
                    "transaction": transaction,
                    "risk_score": decision["risk_score"],
                    "risk_level": decision.get("risk_level", "unknown"),
                    "action": decision.get("action", "unknown"),
                    "reasoning": decision.get("reasoning", ""),
                    "key_signals": decision.get("key_signals", []),
                    "timestamp": f"2026-06-05T00:00:00Z",
                    "resolved": False,
                    "false_positive": None,
                },
            )
            return {"alert_id": doc_id, "logged": True}
        except MCPConnectionError:
            logger.error("Failed to log decision to MongoDB")
            return {"alert_id": "", "logged": False}

    async def close(self) -> None:
        """Release the MCP session if we own it."""
        if self._own_mcp and self._mcp is not None:
            await self._mcp.close()
            self._mcp = None
