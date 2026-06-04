"""
replay_engine.py — Day 4 Transaction Replay Engine
Feeds PaySim transactions to the FraudShield agent in chronological order.
Used for the demo video — simulates real-time fraud detection.

Usage:
    python data/replay_engine.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import time

from dotenv import load_dotenv
from loguru import logger

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.actions import ActionExecutor
from agent.fraud_detector import FraudDetectorAgent
from agent.mongo_mcp import MongoDBMCPClient

load_dotenv()

SPEED_MULTIPLIER = float(os.getenv("REPLAY_SPEED", "10.0"))
REPLAY_LIMIT = int(os.getenv("REPLAY_LIMIT", "200"))
SLEEP_PER_TXN = 0.5 / SPEED_MULTIPLIER  # seconds between transactions

# ── Colour helpers ────────────────────────────────────────────────

def _colour_for_score(score: int) -> str:
    if score >= 61:
        return "\033[91m"  # red
    elif score >= 31:
        return "\033[93m"  # yellow
    return "\033[92m"  # green


RESET = "\033[0m"


# ── Main replay loop ──────────────────────────────────────────────

async def replay(
    speed_multiplier: float = SPEED_MULTIPLIER,
    limit: int = REPLAY_LIMIT,
) -> None:
    """Fetch transactions, feed them to the agent, and print results."""
    half = limit // 2

    async with MongoDBMCPClient() as mcp:
        # ── Fetch a mix of fraud + normal CASH_OUT transactions ────
        logger.info(f"Fetching up to {half} fraud + {half} normal CASH_OUT txns...")

        fraud_txns = await mcp.find("transactions", {"isFraud": 1}, limit=half)
        logger.info(f"   Fraud txns: {len(fraud_txns)}")

        normal_txns = await mcp.find(
            "transactions",
            {"isFraud": 0, "type": "CASH_OUT"},
            limit=half,
        )
        logger.info(f"   Normal txns: {len(normal_txns)}")

        all_txns = sorted(fraud_txns + normal_txns, key=lambda x: x.get("step", 0))
        logger.info(f"   Total to replay: {len(all_txns)}")

        # ── Initialise agent with the shared MCP session ──────────
        agent = FraudDetectorAgent(mcp=mcp)
        executor = ActionExecutor(mcp)

        stats = {"total": 0, "blocked": 0, "flagged": 0, "allowed": 0, "sms_sent": 0}
        t_start = time.time()

        for i, txn in enumerate(all_txns, 1):
            try:
                result = await agent.evaluate_transaction(txn)
                decision = result["decision"]
                score = decision["risk_score"]
                action = decision["action"]

                # Execute the action
                action_result = await executor.execute(txn, decision)
                stats["total"] += 1
                if action == "block":
                    stats["blocked"] += 1
                elif action == "flag":
                    stats["flagged"] += 1
                else:
                    stats["allowed"] += 1
                if action_result.get("sms_sent"):
                    stats["sms_sent"] += 1

            except Exception as exc:
                score = 0
                action = "error"
                logger.error(f"Replay error at tx {i}: {exc}")

            colour = _colour_for_score(score)
            step = txn.get("step", "?")
            txn_type = txn.get("type", "?")
            amount = txn.get("amount", 0)

            print(
                f"{colour}[{i:>4}/{len(all_txns)}]{RESET} "
                f"Step {step:>4} | {txn_type:>9} | "
                f"${amount:>10,.2f} | "
                f"Risk: {score:>3} | {action.upper():>6}"
            )

            await asyncio.sleep(SLEEP_PER_TXN)

        # ── Summary ───────────────────────────────────────────────
        elapsed = time.time() - t_start
        tps = stats["total"] / elapsed if elapsed > 0 else 0

        logger.info("=" * 60)
        logger.info("Replay complete!")
        logger.info(f"   Transactions: {stats['total']}")
        logger.info(f"   🔴 Blocked:   {stats['blocked']}")
        logger.info(f"   🟡 Flagged:   {stats['flagged']}")
        logger.info(f"   🟢 Allowed:   {stats['allowed']}")
        logger.info(f"   📱 SMS sent:  {stats['sms_sent']}")
        logger.info(f"   ⏱️  Time:      {elapsed:.1f}s ({tps:.1f} tps)")
        logger.info("=" * 60)


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("FraudShield Agent — Transaction Replay Engine")
    logger.info(f"   Speed: {SPEED_MULTIPLIER}x | Limit: {REPLAY_LIMIT} txns")
    logger.info("=" * 60)
    asyncio.run(replay())
