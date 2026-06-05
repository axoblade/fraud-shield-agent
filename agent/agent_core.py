"""
agent_core.py — True Fraud Detection Agent with Dynamic Tool Selection

Replaces the fixed 7-step pipeline with multi-turn Gemini reasoning.
The agent decides WHICH tools to call, WHEN to call them, and HOW DEEP
to investigate based on what it finds — like a real fraud analyst.

Architecture:
  Transaction → Gemini (decides what to check) → MCP tool execution
  → Gemini (analyses result, decides next step) → repeats until confident
  → submit_risk_decision → BLOCK / FLAG / ALLOW

Usage:
    from agent.agent_core import FraudShieldAgent

    agent = FraudShieldAgent()
    decision, trace = await agent.evaluate(transaction)
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from typing import Any, Dict, List, Optional

import google.generativeai as genai
from dotenv import load_dotenv
from loguru import logger

from agent.mongo_mcp import MCPConnectionError, MongoDBMCPClient

load_dotenv()

MAX_TURNS = 6
DATABASE = "fraudshield"

# ── Tool declarations (Gemini function-calling schema) ────────────

TOOLS = [
    {
        "name": "fetch_account_history",
        "description": "Get all transactions for an account in the last 24 hours (steps). Call this FIRST for any investigation.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "nameOrig": {"type": "STRING", "description": "Origin account ID"},
                "currentStep": {"type": "INTEGER", "description": "Current simulation step"},
            },
            "required": ["nameOrig", "currentStep"],
        },
    },
    {
        "name": "calculate_velocity",
        "description": "Calculate a velocity score (1-10) for the account based on recent transaction frequency and high-risk type ratio. Higher = more suspicious.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "nameOrig": {"type": "STRING"},
                "currentStep": {"type": "INTEGER"},
            },
            "required": ["nameOrig", "currentStep"],
        },
    },
    {
        "name": "check_mule_status",
        "description": "Check if the destination account is a known money mule. Also checks mule network patterns if not directly flagged.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "nameDest": {"type": "STRING", "description": "Destination account ID"},
            },
            "required": ["nameDest"],
        },
    },
    {
        "name": "get_baseline",
        "description": "Get the account's historical weekly average transactions and spending. Use to compare current behavior against normal patterns.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "nameOrig": {"type": "STRING"},
            },
            "required": ["nameOrig"],
        },
    },
    {
        "name": "check_risk_history",
        "description": "Check if this account has been flagged or blocked before. Returns recent risk scores and total blocked count.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "nameOrig": {"type": "STRING"},
            },
            "required": ["nameOrig"],
        },
    },
    {
        "name": "check_balance_mismatch",
        "description": "Check if the transaction balances don't add up — a sign of account manipulation or data tampering.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "nameOrig": {"type": "STRING"},
            },
            "required": ["nameOrig"],
        },
    },
    {
        "name": "submit_risk_decision",
        "description": "Submit your final fraud risk assessment after completing your investigation. ONLY call this when you're confident in your decision.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "risk_score": {"type": "INTEGER", "description": "0-100, where 0-30=normal, 31-60=suspicious, 61-100=high risk"},
                "risk_level": {"type": "STRING", "enum": ["low", "medium", "high"]},
                "action": {"type": "STRING", "enum": ["allow", "flag", "block"]},
                "reasoning": {"type": "STRING", "description": "2-3 sentence explanation of key findings"},
                "key_signals": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Specific signals that drove this decision"},
            },
            "required": ["risk_score", "risk_level", "action", "reasoning", "key_signals"],
        },
    },
]

# ── System prompt (primes the agent) ──────────────────────────────

SYSTEM_PROMPT = """You are FraudShield, an expert fraud detection agent for a mobile money platform in Sub-Saharan Africa.

Your job: investigate suspicious transactions by calling the available tools, analysing the results, and submitting a risk decision.

RULES:
1. Always call fetch_account_history FIRST for any investigation.
2. Based on what the history reveals, decide which additional tools to call:
   - If the account has recent activity → calculate_velocity
   - If the account has history → get_baseline
   - If the transaction is CASH_OUT or TRANSFER → check_mule_status
   - If the account has prior flags → check_risk_history
   - If amounts look suspicious → check_balance_mismatch
3. For SMALL PAYMENT transactions (< $100) to accounts with no flags: a quick
   history check is enough. Don't over-investigate low-risk transactions.
4. For LARGE CASH_OUT or TRANSFER (> $1,000) to new recipients: dig deeper.
   Check velocity, baseline, mule status, and risk history.
5. When you have enough evidence, call submit_risk_decision.
6. NEVER guess. If you need more data, call another tool.
7. A velocity score above 6 combined with a CASH_OUT is highly suspicious.
8. A dormant account suddenly making a large TRANSFER is a takeover signal.

Be thorough but efficient. High-risk transactions need deep investigation.
Low-risk transactions should be cleared quickly."""


# ── The Agent ─────────────────────────────────────────────────────

class FraudShieldAgent:
    """Multi-turn agent that investigates transactions via Gemini function calling.

    Each evaluation produces:
    - decision: dict with risk_score, action, reasoning, key_signals
    - trace: list of dicts showing each turn (tool called, result, timing)
    """

    def __init__(
        self,
        mcp: MongoDBMCPClient | None = None,
        api_key: str | None = None,
        model_name: str = "gemini-2.5-flash",
    ) -> None:
        key = api_key or os.getenv("GEMINI_API_KEY", "")
        if not key:
            raise ValueError("GEMINI_API_KEY is not set.")

        genai.configure(api_key=key)
        self.model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=SYSTEM_PROMPT,
            tools=TOOLS,
        )
        self._mcp = mcp or MongoDBMCPClient()

    # ── Public API ────────────────────────────────────────────────

    async def evaluate(
        self, transaction: Dict[str, Any]
    ) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Investigate a transaction and return (decision, trace).

        The trace list contains every turn: what tool Gemini called,
        the result, and timing — useful for the UI to show the agent's
        thought process.
        """
        t0 = time.time()
        self._validate(transaction)

        # Prime Gemini with the transaction under investigation
        prompt = self._build_prompt(transaction)
        chat = self.model.start_chat()

        trace: List[Dict[str, Any]] = []
        decision: Optional[Dict[str, Any]] = None

        try:
            response = chat.send_message(prompt)

            for turn in range(1, MAX_TURNS + 1):
                turn_start = time.time()

                if not self._has_function_call(response):
                    # Gemini returned text instead of a function call
                    text = response.candidates[0].content.parts[0].text if response.candidates else ""
                    logger.warning(f"Turn {turn}: No function call, text='{text[:100]}'")
                    if turn >= MAX_TURNS - 1:
                        # Last chance — force a decision
                        response = chat.send_message(
                            "You MUST call submit_risk_decision NOW with your best assessment. "
                            "Do not call any other tools."
                        )
                    else:
                        response = chat.send_message(
                            "Call one of the available tools to investigate, "
                            "or call submit_risk_decision if you have enough evidence."
                        )
                    continue

                func = response.candidates[0].content.parts[0].function_call
                tool_name = func.name
                tool_args = dict(func.args)

                # Extract Gemini's reasoning for choosing this tool
                reasoning = self._extract_reasoning(response)

                logger.info(f"Turn {turn}: → {tool_name}{tool_args}")

                # Execute the tool
                tool_result = await self._execute_tool(tool_name, tool_args, transaction)
                turn_elapsed = (time.time() - turn_start) * 1000

                trace.append({
                    "turn": turn,
                    "tool": tool_name,
                    "args": tool_args,
                    "result_summary": self._summarise_result(tool_name, tool_result),
                    "reasoning": reasoning,
                    "elapsed_ms": round(turn_elapsed),
                })

                # Feed result back to Gemini
                response = chat.send_message(
                    genai.protos.Part(
                        function_response=genai.protos.FunctionResponse(
                            name=tool_name,
                            response={"result": tool_result},
                        )
                    )
                )

                # Check if Gemini submitted a decision
                if self._has_function_call(response):
                    func2 = response.candidates[0].content.parts[0].function_call
                    if func2.name == "submit_risk_decision":
                        decision = dict(func2.args)
                        logger.info(
                            f"Agent decision: score={decision['risk_score']} "
                            f"action={decision['action']} in {turn} turns"
                        )
                        break

            # If no decision after max turns, use heuristic fallback
            if decision is None:
                logger.warning(f"No decision after {MAX_TURNS} turns, using heuristic fallback")
                decision = self._heuristic_fallback(transaction, trace)

        except Exception as exc:
            logger.error(f"Agent evaluation failed: {exc}")
            decision = self._heuristic_fallback(transaction, trace)

        total_elapsed = (time.time() - t0) * 1000

        # Append investigation summary to trace
        trace.append({
            "turn": 0,  # special: summary
            "tool": "_summary",
            "result_summary": self._build_summary(trace, transaction),
            "reasoning": "",
            "elapsed_ms": round(total_elapsed),
        })

        return decision, trace

    # ── Summary builder ───────────────────────────────────────────

    @staticmethod
    def _build_summary(trace: list, txn: Dict[str, Any]) -> str:
        """Synthesise the investigation summary from Gemini's own reasoning
        for each tool call, rather than hardcoded templates."""
        steps = [t for t in trace if t.get("turn", 0) > 0]
        count = len(steps)
        total_available = 6

        if count == 0:
            return f"Used 0 of {total_available} tools — no investigation performed."

        depth = (
            "quick assessment" if count <= 2
            else "standard investigation" if count <= 4
            else "deep investigation"
        )

        lines: list[str] = []
        for step in steps:
            tool = step["tool"]
            reason = step.get("reasoning", "")
            if reason:
                # Take the first sentence for conciseness
                first = reason.split(".")[0].strip()
                if first and not first.endswith("?") and not first.endswith("!"):
                    first += "."
                lines.append(f"\n  •  {tool} — {first}")
            else:
                lines.append(f"\n  •  {tool}")

        used_vs_total = f"Used {count} of {total_available} tools — {depth}."
        return used_vs_total + "".join(lines)

    # ── Tool execution ────────────────────────────────────────────

    async def _execute_tool(
        self, name: str, args: Dict[str, Any], txn: Dict[str, Any]
    ) -> Any:
        """Route tool call to the appropriate MCP query."""
        try:
            if name == "fetch_account_history":
                return await self._tool_history(args)
            elif name == "calculate_velocity":
                return await self._tool_velocity(args)
            elif name == "check_mule_status":
                return await self._tool_mule(args)
            elif name == "get_baseline":
                return await self._tool_baseline(args)
            elif name == "check_risk_history":
                return await self._tool_risk_history(args)
            elif name == "check_balance_mismatch":
                return await self._tool_balance_mismatch(args)
            elif name == "submit_risk_decision":
                return args  # already the decision
            else:
                return {"error": f"Unknown tool: {name}"}
        except MCPConnectionError as exc:
            return {"error": str(exc)}
        except Exception as exc:
            return {"error": str(exc)}

    async def _tool_history(self, args: Dict[str, Any]) -> Dict[str, Any]:
        name_orig = args["nameOrig"]
        step = args["currentStep"]
        docs = await self._mcp.find(
            "transactions",
            {"nameOrig": name_orig, "step": {"$gte": max(0, step - 24)}},
            limit=500,
        )
        if not docs:
            return {"transaction_count": 0, "total_amount": 0, "types": [], "avg_amount": 0}

        amounts = [d.get("amount", 0) for d in docs]
        types_list = list(set(d.get("type", "?") for d in docs))
        total = sum(amounts)
        return {
            "transaction_count": len(docs),
            "total_amount": total,
            "avg_amount": round(total / len(docs), 2),
            "types": types_list,
        }

    async def _tool_velocity(self, args: Dict[str, Any]) -> Dict[str, Any]:
        name_orig = args["nameOrig"]
        step = args["currentStep"]
        docs = await self._mcp.find(
            "transactions",
            {"nameOrig": name_orig, "step": {"$gte": max(0, step - 24)}},
            limit=500,
        )
        count = len(docs)
        if count == 0:
            return {"velocity_score": 1.0, "risk": "low"}

        # Score 1-10
        if count <= 5:
            base = 1.0 + (count / 5.0) * 2.0
        elif count <= 10:
            base = 3.0 + ((count - 5) / 5.0) * 3.0
        elif count <= 20:
            base = 6.0 + ((count - 10) / 10.0) * 2.0
        else:
            base = 8.0 + min(2.0, (count - 20) / 20.0 * 2.0)

        high_risk = sum(1 for d in docs if d.get("type") in ("CASH_OUT", "TRANSFER"))
        if count > 0 and (high_risk / count) > 0.8:
            base += 1.5
        elif count > 0 and (high_risk / count) > 0.5:
            base += 0.5

        score = round(min(10.0, max(1.0, base)), 1)
        return {
            "velocity_score": score,
            "transaction_count_24h": count,
            "high_risk_ratio": round(high_risk / count, 2) if count else 0,
            "risk": "high" if score >= 6 else "medium" if score >= 3 else "low",
        }

    async def _tool_mule(self, args: Dict[str, Any]) -> Dict[str, Any]:
        name_dest = args["nameDest"]
        # Primary: direct flag check
        flagged = await self._mcp.find("flagged_accounts", {"accountId": name_dest}, limit=1)

        if len(flagged) > 0:
            return {"is_mule": True, "source": "flagged_accounts", "confidence": "high"}

        # Fallback: check mule network patterns
        mule_pattern = await self._mcp.aggregate(
            "transactions",
            [
                {"$match": {"type": "TRANSFER", "nameDest": name_dest}},
                {"$group": {"_id": None, "received": {"$sum": "$amount"}, "count": {"$sum": 1}}},
            ],
        )
        if mule_pattern and mule_pattern[0].get("count", 0) > 10:
            return {
                "is_mule": True,
                "source": "network_analysis",
                "confidence": "medium",
                "received_count": mule_pattern[0]["count"],
                "received_total": mule_pattern[0]["received"],
            }

        return {"is_mule": False}

    async def _tool_baseline(self, args: Dict[str, Any]) -> Dict[str, Any]:
        name_orig = args["nameOrig"]
        count = await self._mcp.count("transactions", {"nameOrig": name_orig})
        if count == 0:
            return {"avg_weekly_transactions": 0, "avg_weekly_amount": 0, "status": "new_account"}

        agg = await self._mcp.aggregate(
            "transactions",
            [
                {"$match": {"nameOrig": name_orig}},
                {"$group": {
                    "_id": None,
                    "total_txns": {"$sum": 1},
                    "total_amount": {"$sum": "$amount"},
                    "min_step": {"$min": "$step"},
                    "max_step": {"$max": "$step"},
                }},
            ],
        )
        if agg:
            r = agg[0]
            week_span = max(1, (r.get("max_step", 0) - r.get("min_step", 0)) / 168)
            return {
                "avg_weekly_transactions": round(r["total_txns"] / week_span, 1),
                "avg_weekly_amount": round(r["total_amount"] / week_span, 2),
                "total_lifetime_txns": r["total_txns"],
                "status": "established",
            }
        return {"avg_weekly_transactions": 0, "avg_weekly_amount": 0, "status": "unknown"}

    async def _tool_risk_history(self, args: Dict[str, Any]) -> Dict[str, Any]:
        name_orig = args["nameOrig"]
        docs = await self._mcp.find("risk_scores", {"nameOrig": name_orig}, limit=1)
        if not docs:
            return {"has_history": False, "previous_scores": [], "total_blocked": 0}

        doc = docs[0]
        return {
            "has_history": True,
            "last_risk_score": doc.get("last_risk_score", 0),
            "total_transactions": doc.get("total_transactions", 0),
            "total_blocked": doc.get("total_blocked", 0),
            "total_flagged": doc.get("total_flagged", 0),
            "recent_scores": doc.get("score_history", [])[-5:],
        }

    async def _tool_balance_mismatch(self, args: Dict[str, Any]) -> Dict[str, Any]:
        name_orig = args["nameOrig"]
        docs = await self._mcp.find(
            "transactions",
            {"nameOrig": name_orig, "type": {"$in": ["CASH_OUT", "TRANSFER"]}},
            limit=20,
        )
        mismatches = 0
        for d in docs:
            expected = d.get("expectedNewBalanceOrg", d.get("oldbalanceOrg", 0) - d.get("amount", 0))
            actual = d.get("newbalanceOrig", 0)
            if abs(actual - expected) > 0.01:
                mismatches += 1
        return {
            "transactions_checked": len(docs),
            "balance_mismatches": mismatches,
            "tampering_suspected": mismatches > 0,
        }

    # ── Helpers ───────────────────────────────────────────────────

    @staticmethod
    def _validate(txn: Dict[str, Any]) -> None:
        required = {"step", "type", "amount", "nameOrig", "nameDest"}
        missing = required - set(txn.keys())
        if missing:
            raise ValueError(f"Missing required fields: {missing}")

    def _build_prompt(self, txn: Dict[str, Any]) -> str:
        return (
            f"INVESTIGATE THIS TRANSACTION:\n"
            f"  Type: {txn['type']}\n"
            f"  Amount: ${txn['amount']:,.2f}\n"
            f"  From: {txn['nameOrig']}\n"
            f"  To: {txn['nameDest']}\n"
            f"  Simulation Day: {txn['step'] // 24 + 1} (step {txn['step']})\n"
            f"  Balance before: ${txn.get('oldbalanceOrg', 0):,.2f}\n"
            f"  Balance after: ${txn.get('newbalanceOrig', 0):,.2f}\n"
            f"\n"
            f"Begin your investigation by calling fetch_account_history."
        )

    @staticmethod
    def _has_function_call(response) -> bool:
        try:
            part = response.candidates[0].content.parts[0]
            return hasattr(part, "function_call") and part.function_call is not None
        except (IndexError, AttributeError):
            return False

    @staticmethod
    def _extract_reasoning(response) -> str:
        """Extract Gemini's reasoning text that accompanies a function call.

        Gemini often explains WHY it's calling a tool in the text part
        alongside the function_call part.  This gives us the agent's
        thought process for the UI trace.
        """
        try:
            for part in response.candidates[0].content.parts:
                if hasattr(part, "text") and part.text and part.text.strip():
                    return part.text.strip()[:200]
        except (IndexError, AttributeError):
            pass
        return ""

    @staticmethod
    def _summarise_result(tool_name: str, result: Any) -> str:
        """Create a short human-readable summary of tool results."""
        if isinstance(result, dict):
            if tool_name == "fetch_account_history":
                return f"{result.get('transaction_count', 0)} txns, ${result.get('total_amount', 0):,.0f} total"
            if tool_name == "calculate_velocity":
                return f"score {result.get('velocity_score', 0)}/10 ({result.get('risk', '?')})"
            if tool_name == "check_mule_status":
                return f"mule={'YES' if result.get('is_mule') else 'no'} ({result.get('source', 'N/A')})"
            if tool_name == "get_baseline":
                return f"{result.get('avg_weekly_transactions', 0)} txns/week, ${result.get('avg_weekly_amount', 0):,.0f}/week"
            if tool_name == "check_risk_history":
                return f"{'has history' if result.get('has_history') else 'no history'}, {result.get('total_blocked', 0)} blocked"
            if tool_name == "check_balance_mismatch":
                return f"{result.get('balance_mismatches', 0)} mismatches / {result.get('transactions_checked', 0)} checked"
        return str(result)[:80]

    def _heuristic_fallback(
        self, txn: Dict[str, Any], trace: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Rule-based fallback when Gemini fails to decide."""
        from agent.gemini_client import GeminiClient

        context = {
            "transaction": txn,
            "history_24h": {"transaction_count": 0, "total_amount": 0, "types": [], "avg_amount": 0},
            "baseline": {"avg_weekly_transactions": 0, "avg_weekly_amount": 0},
            "recipient_flagged": False,
            "velocity_score": 1.0,
        }
        return GeminiClient.heuristic_decision(context)
