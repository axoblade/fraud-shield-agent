"""
adk_agent.py, FraudShield Agent built on Google ADK (Agent Development Kit)

Uses ADK's Agent + Runner + FunctionTool for Gemini function calling,
with the same tool implementations and trace format.
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from loguru import logger

from google.adk import Agent, Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import FunctionTool
from google.genai import types

from agent.actions import ActionExecutor
from agent.mongo_mcp import MCPConnectionError, MongoDBMCPClient

load_dotenv()

MAX_TURNS = 6

SYSTEM_PROMPT = """You are FraudShield, an expert fraud detection agent for a mobile money platform in Sub-Saharan Africa.

Your job: investigate suspicious transactions by calling the available tools, analysing the results, and submitting a risk decision.

IMPORTANT CONTEXT: 99.87% of all transactions are legitimate. Most transactions you investigate will be genuine. Only block when you have clear, multi-signal evidence of fraud. When uncertain, flag for review rather than block.

SCORING GUIDE:
- Score 0-30 (ALLOW): Normal activity — consistent history, no flags, small amounts, expected patterns
- Score 31-60 (FLAG): Unusual but not clearly fraudulent — elevated velocity, new recipient, moderate amount. Deserves human review.
- Score 61-100 (BLOCK): Clear fraud indicators — requires MULTIPLE signals: high velocity + large amount + balance mismatch + mule recipient

Only give a score above 60 when at least TWO major signals agree. A single suspicious signal (e.g. just "new account" or just "large amount") should score below 60.

RULES:
1. Always call _tool_history FIRST for any investigation.
2. Based on what the history reveals, decide which additional tools to call:
   - If the account has recent activity, call _tool_velocity
   - If the account has history, call _tool_baseline
   - If the transaction is CASH_OUT or TRANSFER, call _tool_mule
   - If the account has prior flags, call _tool_risk_history
   - If amounts look suspicious, call _tool_balance_mismatch
3. For SMALL transactions (< $500): a quick history check is usually enough. Don't over-investigate.
4. For LARGE CASH_OUT or TRANSFER (> $1,000) to new recipients: dig deeper.
5. When you have enough evidence, call _tool_submit_decision.
6. NEVER guess. If you need more data, call another tool.
7. A velocity score above 6 combined with a CASH_OUT is highly suspicious.
8. A dormant account suddenly making a large TRANSFER is a takeover signal.

Be thorough but fair. Most transactions are genuine. Reserve high scores for clear fraud."""


# ── ADK-based Agent ──────────────────────────────────────────────

class FraudShieldADKAgent:
    """
        Multi-turn agent powered by Google ADK (Agent Development Kit).
        Uses ADK's Agent + Runner for Gemini function calling.
    """

    def __init__(
        self,
        mcp: MongoDBMCPClient | None = None,
        api_key: str | None = None,
        model_name: str = "gemini-2.5-flash",
    ) -> None:
        key = api_key or os.getenv("GEMINI_API_KEY", "") or os.getenv("GOOGLE_API_KEY", "")
        if not key:
            raise ValueError("GEMINI_API_KEY or GOOGLE_API_KEY is not set.")
        os.environ["GOOGLE_API_KEY"] = key
        os.environ.pop("GEMINI_API_KEY", None)  # avoid ADK duplicate warning

        self._mcp = mcp or MongoDBMCPClient()
        self._model = model_name
        self._txn: Dict[str, Any] = {}  # current transaction under investigation

    # ── Public API ────────────────────────────────────────────────

    async def evaluate(
        self, transaction: Dict[str, Any]
    ) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Investigate a transaction and return (decision, trace)."""
        t0 = time.time()
        self._validate(transaction)
        self._txn = transaction

        trace: List[Dict[str, Any]] = []
        decision: Optional[Dict[str, Any]] = None

        # Build ADK tools from our MCP-backed implementations
        tools = [
            FunctionTool(self._tool_history),
            FunctionTool(self._tool_velocity),
            FunctionTool(self._tool_mule),
            FunctionTool(self._tool_baseline),
            FunctionTool(self._tool_risk_history),
            FunctionTool(self._tool_balance_mismatch),
            FunctionTool(self._tool_submit_decision),
        ]

        agent = Agent(
            name="FraudShield",
            description="Fraud detection agent for mobile money transactions",
            model=self._model,
            instruction=SYSTEM_PROMPT,
            tools=tools,
        )
        runner = Runner(agent=agent, session_service=InMemorySessionService(), app_name="fraudshield", auto_create_session=True)

        prompt = self._build_prompt(transaction)

        try:
            turn = 0
            decided = False
            async for event in runner.run_async(
                user_id="fraudshield",
                session_id=f"txn-{transaction.get('nameOrig', 'unknown')}-{int(time.time())}",
                new_message=types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=prompt)],
                ),
            ):
                # Once we have a decision, drain remaining events silently
                # instead of breaking — avoids OTEL GeneratorExit traceback
                if decided:
                    continue

                if not event.content or not event.content.parts:
                    continue

                for part in event.content.parts:
                    fc = getattr(part, "function_call", None)
                    if fc and fc.name:
                        tool_name = fc.name
                        tool_args = dict(fc.args or {})

                        logger.info(f"Turn {turn}: → {tool_name}")

                        reasoning = ""
                        for p in event.content.parts:
                            if hasattr(p, "text") and p.text:
                                reasoning = p.text.strip()[:200]
                                break

                        if tool_name == "_tool_submit_decision":
                            decision = tool_args
                            raw_action = str(decision.get("action", "")).lower()
                            if "block" in raw_action:
                                decision["action"] = "block"
                            elif "flag" in raw_action:
                                decision["action"] = "flag"
                            else:
                                decision["action"] = "allow"
                            decision["risk_score"] = int(decision.get("risk_score", 50))
                            decision.setdefault("risk_level", "medium" if decision["risk_score"] >= 31 else "low")
                            decision.setdefault("reasoning", "")
                            decision["key_signals"] = []

                            turn += 1
                            trace.append({
                                "turn": turn,
                                "tool": "submit_decision",
                                "args": tool_args,
                                "result_summary": f"score={decision['risk_score']}/100 → {decision['action'].upper()}",
                                "reasoning": reasoning,
                                "elapsed_ms": round((time.time() - t0) * 1000),
                            })
                            decided = True
                            continue

                        turn += 1
                        trace.append({
                            "turn": turn,
                            "tool": tool_name.replace("_tool_", ""),
                            "tool_key": tool_name,
                            "args": tool_args,
                            "result_summary": "pending…",
                            "reasoning": reasoning,
                            "elapsed_ms": 0,
                        })

                    # ── Text content (captured as reasoning alongside function calls) ──
                    txt = getattr(part, "text", None)
                    if txt and txt.strip():
                        pass

                    # ── Function response (ADK executed the tool) ──
                    fr = getattr(part, "function_response", None)
                    if fr and fr.name:
                        tool_name = fr.name
                        raw_result = fr.response or {}
                        if isinstance(raw_result, dict) and "result" in raw_result:
                            raw_result = raw_result["result"]
                        result = self._sanitize_result(raw_result)

                        for t in reversed(trace):
                            if t.get("tool_key") == tool_name and t.get("result_summary") == "pending…":
                                t["result_summary"] = self._summarise_result(tool_name, result)
                                t["elapsed_ms"] = round((time.time() - t0) * 1000)
                                break


            # If ADK runner completed without submit_risk_decision → heuristic fallback
            if decision is None:
                logger.warning("ADK runner finished without decision - using heuristic fallback")
                decision = self._heuristic_fallback(transaction, trace)

        except Exception as exc:
            logger.error(f"ADK agent evaluation failed: {exc}")
            decision = self._heuristic_fallback(transaction, trace)

        total_elapsed = (time.time() - t0) * 1000

        # Enrich key_signals if missing
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

        # Always regenerate key_signals from heuristic for consistent formatting
        decision["key_signals"] = self._generate_signals(heuristics, transaction)

        trace.append({
            "turn": -1,
            "tool": "_summary",
            "result_summary": self._build_summary(trace, transaction),
            "reasoning": "",
            "elapsed_ms": round(total_elapsed),
        })

        return decision, trace

    # ── Tool implementations (same logic, ADK-compatible signatures) ──

    async def _tool_history(self, name_orig: str, current_step: int) -> Dict[str, Any]:
        """Get all transactions for an account in the last 24 hours (steps). Call this FIRST."""
        step = current_step
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

    async def _tool_velocity(self, name_orig: str, current_step: int) -> Dict[str, Any]:
        """Calculate a velocity score (1-10) based on recent transaction frequency."""
        step = current_step
        docs = await self._mcp.find(
            "transactions",
            {"nameOrig": name_orig, "step": {"$gte": max(0, step - 24)}},
            limit=500,
        )
        count = len(docs)
        if count == 0:
            return {"velocity_score": 1.0, "risk": "low"}
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

    async def _tool_mule(self, name_dest: str) -> Dict[str, Any]:
        """Check if the destination account is a known money mule."""
        flagged = await self._mcp.find("flagged_accounts", {"accountId": name_dest}, limit=1)
        if len(flagged) > 0:
            return {"is_mule": True, "source": "flagged_accounts", "confidence": "high"}
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

    async def _tool_baseline(self, name_orig: str) -> Dict[str, Any]:
        """Get the account's historical weekly average transactions and spending."""
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

    async def _tool_risk_history(self, name_orig: str) -> Dict[str, Any]:
        """Check if this account has been flagged or blocked before."""
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

    async def _tool_balance_mismatch(self, name_orig: str) -> Dict[str, Any]:
        """Check if transaction balances don't add up - sign of tampering."""
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

    async def _tool_submit_decision(
        self,
        risk_score: int,
        risk_level: str,
        action: str,
        reasoning: str,
        key_signals: List[str],
    ) -> Dict[str, Any]:
        """Submit your final fraud risk assessment. ONLY call when confident."""
        return {
            "risk_score": risk_score,
            "risk_level": risk_level,
            "action": action,
            "reasoning": reasoning,
            "key_signals": key_signals,
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
    def _extract_event_text(event) -> str:
        """Extract any text from an ADK event for reasoning display."""
        try:
            if hasattr(event, "text") and event.text:
                return event.text.strip()[:200]
        except Exception:
            pass
        return ""

    @staticmethod
    def _sanitize_result(result: Any, max_keys: int = 10, max_str_len: int = 200) -> Any:
        if isinstance(result, dict):
            trimmed = {}
            for k, v in list(result.items())[:max_keys]:
                if isinstance(v, str) and len(v) > max_str_len:
                    trimmed[k] = v[:max_str_len] + "…"
                elif isinstance(v, (list, dict)):
                    trimmed[k] = FraudShieldADKAgent._sanitize_result(v, max_keys=5, max_str_len=100)
                else:
                    trimmed[k] = v
            return trimmed
        if isinstance(result, list):
            return [
                FraudShieldADKAgent._sanitize_result(i, max_keys=5, max_str_len=100)
                for i in result[:max_keys]
            ]
        if isinstance(result, str) and len(result) > max_str_len:
            return result[:max_str_len] + "…"
        return result

    @staticmethod
    def _summarise_result(tool_name: str, result: Any) -> str:
        if isinstance(result, dict):
            if tool_name == "_tool_history":
                return f"{result.get('transaction_count', 0)} txns, ${result.get('total_amount', 0):,.0f} total"
            if tool_name == "_tool_velocity":
                return f"score {result.get('velocity_score', 0)}/10 ({result.get('risk', '?')})"
            if tool_name == "_tool_mule":
                return f"mule={'YES' if result.get('is_mule') else 'no'} ({result.get('source', 'N/A')})"
            if tool_name == "_tool_baseline":
                return f"{result.get('avg_weekly_transactions', 0)} txns/week, ${result.get('avg_weekly_amount', 0):,.0f}/week"
            if tool_name == "_tool_risk_history":
                return f"{'has history' if result.get('has_history') else 'no history'}, {result.get('total_blocked', 0)} blocked"
            if tool_name == "_tool_balance_mismatch":
                return f"{result.get('balance_mismatches', 0)} mismatches / {result.get('transactions_checked', 0)} checked"
        return str(result)[:80]

    # ── Heuristic & signal logic ──────────────────────────────────

    @staticmethod
    def _compute_heuristic(txn: Dict[str, Any], trace: List[Dict[str, Any]]) -> Dict[str, Any]:
        velocity_score = 1.0
        hist_count = 0
        recipient_flagged = False
        for step in trace:
            tool = step.get("tool", "")
            result = step.get("result_summary", "")
            if tool == "_tool_velocity":
                m = re.search(r"score ([\d.]+)/10", str(result))
                if m:
                    velocity_score = float(m.group(1))
            if tool == "_tool_history":
                m = re.search(r"(\d+) txns", str(result))
                if m:
                    hist_count = int(m.group(1))
            if tool == "_tool_mule" and "YES" in str(result):
                recipient_flagged = True
        txn_type = txn.get("type", "")
        amount = txn.get("amount", 0)
        score = 10.0
        score += min(30, velocity_score * 3)
        if txn_type == "CASH_OUT":
            score += 20; type_risk = "high"
        elif txn_type == "TRANSFER":
            score += 15; type_risk = "medium"
        elif txn_type == "DEBIT":
            score += 5; type_risk = "low"
        else:
            type_risk = "low"
        if hist_count > 20: score += 15
        elif hist_count > 10: score += 10
        elif hist_count > 5: score += 5
        if amount > 5000:
            score += 10; amount_risk = "large"
        elif amount > 1000:
            score += 5; amount_risk = "medium"
        else:
            amount_risk = "small"
        if recipient_flagged: score += 15
        score = min(100, int(score))
        action = "block" if score >= 61 else "flag" if score >= 31 else "allow"
        return {
            "risk_score": score, "action": action,
            "velocity_score": velocity_score, "hist_count": hist_count,
            "recipient_flagged": recipient_flagged,
            "type_risk": type_risk, "amount_risk": amount_risk,
            "transaction_type": txn_type, "transaction_amount": amount,
        }

    @staticmethod
    def _generate_signals(heuristics: Dict[str, Any], txn: Dict[str, Any]) -> list[str]:
        signals: list[str] = []
        v = heuristics.get("velocity_score", 1.0)
        hc = heuristics.get("hist_count", 0)
        rf = heuristics.get("recipient_flagged", False)
        tr = heuristics.get("type_risk", "low")
        ar = heuristics.get("amount_risk", "small")
        txn_type = heuristics.get("transaction_type", txn.get("type", "?"))
        if v >= 6: signals.append(f"velocity_spike ({v:.1f}/10)")
        elif v >= 3: signals.append(f"velocity_elevated ({v:.1f}/10)")
        else: signals.append("velocity_normal")
        if txn_type in ("CASH_OUT", "TRANSFER"): signals.append(f"high_risk_{txn_type.lower()}")
        if ar == "large": signals.append("large_amount")
        elif ar == "medium": signals.append("medium_amount")
        if rf: signals.append("mule_recipient")
        if hc > 10: signals.append("unusual_24h_activity")
        elif hc == 0: signals.append("no_recent_activity")
        if tr == "high" and ar == "large": signals.append("critical_combo")
        if not signals: signals.append("normal_pattern")
        return signals

    @staticmethod
    def _build_summary(trace: list, txn: Dict[str, Any]) -> str:
        real_tools = [
            t for t in trace
            if t.get("turn", 0) > 0
            and t.get("tool", "") not in ("_tool_analysis", "analysis", "_heuristic", "_summary", "submit_decision")
        ]
        count = len(real_tools)
        total_available = 6
        if count == 0:
            return f"Used 0 of {total_available} tools - no investigation performed."
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
                lines.append(f"\n  •  {tool} - {first}")
            else:
                lines.append(f"\n  •  {tool}")
        return f"Used {count} of {total_available} tools - {depth}." + "".join(lines)

    def _heuristic_fallback(
        self, txn: Dict[str, Any], trace: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        from agent.gemini_client import GeminiClient
        velocity_score = 1.0
        recipient_flagged = False
        for step in trace:
            tool = step.get("tool", "")
            result = step.get("result_summary", "")
            if tool == "_tool_velocity":
                m = re.search(r"score ([\d.]+)/10", str(result))
                if m:
                    velocity_score = float(m.group(1))
            if tool == "_tool_mule" and "YES" in str(result):
                recipient_flagged = True
        context = {
            "transaction": txn,
            "history_24h": {"transaction_count": 0, "total_amount": 0, "types": [], "avg_amount": 0},
            "baseline": {"avg_weekly_transactions": 0, "avg_weekly_amount": 0},
            "recipient_flagged": recipient_flagged,
            "velocity_score": velocity_score,
        }
        decision = GeminiClient.heuristic_decision(context)
        if trace and "Heuristic assessment" in decision.get("reasoning", ""):
            decision["reasoning"] = "[Fallback] " + decision["reasoning"]
        return decision
