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

                try:
                    func = response.candidates[0].content.parts[0].function_call
                    tool_name = func.name
                    tool_args = dict(func.args)
                except (AttributeError, TypeError, ValueError) as exc:
                    logger.error(f"Turn {turn}: malformed function call — {exc}")
                    response = chat.send_message(
                        "Your last function call was malformed. "
                        "Please call a valid tool or submit_risk_decision."
                    )
                    continue

                # Extract Gemini's reasoning for choosing this tool
                reasoning = self._extract_reasoning(response)

                logger.info(f"Turn {turn}: → {tool_name}{tool_args}")

                # Execute the tool
                raw_result = await self._execute_tool(tool_name, tool_args, transaction)
                tool_result = self._sanitize_result(raw_result)
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

                # Capture Gemini's analysis of the tool result.
                # Gemini produces text explaining what it learned before
                # deciding the next step — this is the per-tool reasoning.
                analysis = self._extract_text(response)

                # Check if Gemini submitted a decision
                if self._has_function_call(response):
                    try:
                        func2 = response.candidates[0].content.parts[0].function_call
                        if func2.name == "submit_risk_decision":
                            decision = dict(func2.args)
                    except (AttributeError, TypeError, ValueError) as exc:
                        logger.error(f"Turn {turn}: malformed submit_risk_decision — {exc}")
                        # Force heuristic fallback
                        decision = None
                        break

                    if decision is not None:

                        # If submit_risk_decision's reasoning field is weak or
                        # empty, replace it with the richer analysis text.
                        if analysis and (
                            not decision.get("reasoning")
                            or len(decision.get("reasoning", "")) < 30
                        ):
                            decision["reasoning"] = analysis

                        # Append the final analysis as a visible trace step
                        if analysis:
                            trace.append({
                                "turn": turn,
                                "tool": "analysis",
                                "result_summary": analysis[:500],
                                "reasoning": "",
                                "elapsed_ms": 0,
                            })

                        logger.info(
                            f"Agent decision: score={decision['risk_score']} "
                            f"action={decision['action']} in {turn} turns"
                        )
                        break

                # Per-tool analysis: always capture what Gemini learned from
                # the result, even when it's not the final decision.
                if analysis and not (
                    self._has_function_call(response)
                    and response.candidates[0].content.parts[0].function_call.name == "submit_risk_decision"
                ):
                    trace.append({
                        "turn": turn,
                        "tool": "_tool_analysis",
                        "result_summary": analysis[:400],
                        "reasoning": "",
                        "elapsed_ms": 0,
                    })

            # If no decision after max turns, use heuristic fallback
            if decision is None:
                logger.warning(f"No decision after {MAX_TURNS} turns, using heuristic fallback")
                decision = self._heuristic_fallback(transaction, trace)

        except Exception as exc:
            logger.error(f"Agent evaluation failed: {exc}")
            decision = self._heuristic_fallback(transaction, trace)

        total_elapsed = (time.time() - t0) * 1000

        # Always attach heuristic baseline for consistent comparison
        heuristics = self._compute_heuristic(transaction, trace)
        trace.append({
            "turn": 0,
            "tool": "_heuristic",
            "result_summary": (
                f"Heuristic baseline: velocity={heuristics['velocity_score']:.1f}/10, "
                f"type_risk={heuristics['type_risk']}, "
                f"amount_risk={heuristics['amount_risk']}, "
                f"24h_txns={heuristics['hist_count']}, "
                f"mule={heuristics['recipient_flagged']}, "
                f"score={heuristics['risk_score']}/100 → {heuristics['action']}"
            ),
            "reasoning": "",
            "elapsed_ms": 0,
            "heuristic_data": heuristics,
        })

        # Ensure key_signals is never empty — generate from trace data if
        # Gemini didn't provide them (it often doesn't).
        if (
            not isinstance(decision.get("key_signals"), list)
            or len(decision.get("key_signals", [])) == 0
        ):
            decision["key_signals"] = self._generate_signals(heuristics, transaction)

        # Append investigation summary to trace
        trace.append({
            "turn": -1,  # summary (after heuristic at turn 0)
            "tool": "_summary",
            "result_summary": self._build_summary(trace, transaction),
            "reasoning": "",
            "elapsed_ms": round(total_elapsed),
        })

        return decision, trace

    # ── Heuristic computer ────────────────────────────────────────

    @staticmethod
    def _compute_heuristic(
        txn: Dict[str, Any], trace: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Compute rule-based risk metrics from trace data for comparison."""
        # Extract findings from the trace
        velocity_score = 1.0
        hist_count = 0
        recipient_flagged = False

        for step in trace:
            tool = step.get("tool", "")
            result = step.get("result_summary", "")
            if tool == "calculate_velocity":
                import re
                m = re.search(r"score ([\d.]+)/10", str(result))
                if m:
                    velocity_score = float(m.group(1))
            if tool == "fetch_account_history":
                import re
                m = re.search(r"(\d+) txns", str(result))
                if m:
                    hist_count = int(m.group(1))
            if tool == "check_mule_status" and "YES" in str(result):
                recipient_flagged = True

        txn_type = txn.get("type", "")
        amount = txn.get("amount", 0)

        score = 10.0
        score += min(30, velocity_score * 3)
        if txn_type == "CASH_OUT":
            score += 20
            type_risk = "high"
        elif txn_type == "TRANSFER":
            score += 15
            type_risk = "medium"
        elif txn_type == "DEBIT":
            score += 5
            type_risk = "low"
        else:
            type_risk = "low"

        if hist_count > 20:
            score += 15
        elif hist_count > 10:
            score += 10
        elif hist_count > 5:
            score += 5

        if amount > 5000:
            score += 10
            amount_risk = "large"
        elif amount > 1000:
            score += 5
            amount_risk = "medium"
        else:
            amount_risk = "small"

        if recipient_flagged:
            score += 15

        score = min(100, int(score))
        action = "block" if score >= 61 else "flag" if score >= 31 else "allow"

        return {
            "risk_score": score,
            "action": action,
            "velocity_score": velocity_score,
            "hist_count": hist_count,
            "recipient_flagged": recipient_flagged,
            "type_risk": type_risk,
            "amount_risk": amount_risk,
            "transaction_type": txn_type,
            "transaction_amount": amount,
        }

    @staticmethod
    def _generate_signals(
        heuristics: Dict[str, Any], txn: Dict[str, Any]
    ) -> list[str]:
        """Produce human-readable signal tags from heuristic metrics.

        Used to enrich Gemini decisions (which often lack key_signals) so
        every response shows actionable tags in the UI.
        """
        signals: list[str] = []
        v = heuristics.get("velocity_score", 1.0)
        hc = heuristics.get("hist_count", 0)
        rf = heuristics.get("recipient_flagged", False)
        tr = heuristics.get("type_risk", "low")
        ar = heuristics.get("amount_risk", "small")
        txn_type = heuristics.get("transaction_type", txn.get("type", "?"))

        if v >= 6:
            signals.append(f"velocity_spike ({v:.1f}/10)")
        elif v >= 3:
            signals.append(f"velocity_elevated ({v:.1f}/10)")
        else:
            signals.append("velocity_normal")

        if txn_type in ("CASH_OUT", "TRANSFER"):
            signals.append(f"high_risk_{txn_type.lower()}")

        if ar == "large":
            signals.append("large_amount")
        elif ar == "medium":
            signals.append("medium_amount")

        if rf:
            signals.append("mule_recipient")

        if hc > 10:
            signals.append("unusual_24h_activity")
        elif hc == 0:
            signals.append("no_recent_activity")

        if tr == "high" and ar == "large":
            signals.append("critical_combo")

        if not signals:
            signals.append("normal_pattern")

        return signals

    # ── Summary builder ───────────────────────────────────────────

    @staticmethod
    def _build_summary(trace: list, txn: Dict[str, Any]) -> str:
        """Synthesise the investigation summary from Gemini's own reasoning
        for each tool call, rather than hardcoded templates."""
        # Only count real tool calls (not analysis, heuristic, or summary entries)
        real_tools = [
            t for t in trace
            if t.get("turn", 0) > 0
            and t.get("tool", "") not in ("_tool_analysis", "analysis", "_heuristic", "_summary")
        ]
        count = len(real_tools)
        total_available = 6

        if count == 0:
            return f"Used 0 of {total_available} tools — no investigation performed."

        depth = (
            "quick assessment" if count <= 2
            else "standard investigation" if count <= 4
            else "deep investigation"
        )

        lines: list[str] = []
        for step in real_tools:
            tool = step["tool"]
            reason = step.get("reasoning", "")
            if reason:
                first = reason.split(".")[0].strip()
                if first and not first.endswith("?") and not first.endswith("!"):
                    first += "."
                lines.append(f"\n  •  {tool} — {first}")
            else:
                lines.append(f"\n  •  {tool}")

        return f"Used {count} of {total_available} tools — {depth}." + "".join(lines)

    # ── Result sanitizer ──────────────────────────────────────────

    @staticmethod
    def _sanitize_result(result: Any, max_keys: int = 10, max_str_len: int = 200) -> Any:
        """Trim tool results so they never overflow Gemini's context window.

        Large MongoDB documents or deeply nested structures are truncated
        to prevent malformed JSON in Gemini's function-response history.
        """
        if isinstance(result, dict):
            trimmed = {}
            for k, v in list(result.items())[:max_keys]:
                if isinstance(v, str) and len(v) > max_str_len:
                    trimmed[k] = v[:max_str_len] + "…"
                elif isinstance(v, (list, dict)):
                    trimmed[k] = FraudShieldAgent._sanitize_result(v, max_keys=5, max_str_len=100)
                else:
                    trimmed[k] = v
            return trimmed
        if isinstance(result, list):
            return [
                FraudShieldAgent._sanitize_result(i, max_keys=5, max_str_len=100)
                for i in result[:max_keys]
            ]
        if isinstance(result, str) and len(result) > max_str_len:
            return result[:max_str_len] + "…"
        return result

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
            try:
                return part.function_call is not None
            except AttributeError:
                return False
        except (IndexError, AttributeError):
            return False

    @staticmethod
    def _extract_reasoning(response) -> str:
        """Extract Gemini's reasoning text that accompanies a function call.

        Uses duck-typing (try/except) because protobuf RepeatedComposite
        containers don't reliably support hasattr().
        """
        try:
            for part in response.candidates[0].content.parts:
                try:
                    text = part.text
                    if text and text.strip():
                        return text.strip()
                except (AttributeError, TypeError):
                    pass
        except (IndexError, AttributeError, TypeError):
            pass
        return ""

    @staticmethod
    def _extract_text(response) -> str:
        """Return ALL visible text from a Gemini response (no truncation).

        Separate from _extract_reasoning because we don't truncate here —
        this is used for the final analysis display.
        """
        try:
            parts = []
            for part in response.candidates[0].content.parts:
                try:
                    t = part.text
                    if t and t.strip():
                        parts.append(t.strip())
                except (AttributeError, TypeError):
                    pass
            return "\n\n".join(parts)
        except (IndexError, AttributeError, TypeError):
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
        """Rule-based fallback when Gemini fails to decide.

        Enriches the heuristic with any partial trace data already collected
        so the UI still shows useful context.
        """
        from agent.gemini_client import GeminiClient

        # Pull partial findings from the trace if available
        hist_data: Dict[str, Any] = {"transaction_count": 0, "total_amount": 0, "types": [], "avg_amount": 0}
        baseline_data: Dict[str, Any] = {"avg_weekly_transactions": 0, "avg_weekly_amount": 0}
        velocity_score = 1.0
        recipient_flagged = False

        for step in trace:
            tool = step.get("tool", "")
            result = step.get("result_summary", "")
            # Try to recover structured data from the tool_args if we have it
            if tool == "fetch_account_history" and isinstance(step.get("args"), dict):
                # We can't get the full result here, but we know it ran
                pass
            if tool == "check_mule_status":
                # Parse the result summary for mule status
                if "YES" in str(result):
                    recipient_flagged = True
            if tool == "calculate_velocity":
                # Try to parse score from result summary like "score 8.5/10"
                import re
                m = re.search(r"score ([\d.]+)/10", str(result))
                if m:
                    velocity_score = float(m.group(1))

        context = {
            "transaction": txn,
            "history_24h": hist_data,
            "baseline": baseline_data,
            "recipient_flagged": recipient_flagged,
            "velocity_score": velocity_score,
        }
        decision = GeminiClient.heuristic_decision(context)

        # Prepend trace context if we have any partial findings
        if trace:
            prefix = "" if "Heuristic assessment" in decision.get("reasoning", "") else ""
            if prefix:
                decision["reasoning"] = prefix + decision["reasoning"]

        return decision
