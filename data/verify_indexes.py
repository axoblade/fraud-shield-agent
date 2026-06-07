"""
verify_indexes.py - MongoDB Index Verification
Runs targeted agent-style queries to verify compound indexes are working.
All queries should return in under 500ms.

Usage:
    python data/verify_indexes.py
"""

import os
import sys
import time

import certifi
from dotenv import load_dotenv
from loguru import logger
from pymongo import MongoClient

# ── Load environment ──────────────────────────────────────────────
load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "fraudshield")

if not MONGODB_URI:
    logger.error("MONGODB_URI not set in .env")
    sys.exit(1)

# ── Connect ───────────────────────────────────────────────────────
mongo_kwargs = {}
if MONGODB_URI.startswith("mongodb+srv://"):
    mongo_kwargs["tlsCAFile"] = certifi.where()

client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=30000, **mongo_kwargs)
db = client[MONGODB_DATABASE]
collection = db["transactions"]

# Verify connection
try:
    client.admin.command("ping")
except Exception as e:
    logger.error(f"❌ Cannot connect to MongoDB: {e}")
    sys.exit(1)

# ── Check data exists ─────────────────────────────────────────────
doc_count = collection.count_documents({})
if doc_count == 0:
    logger.error("❌ No documents in fraudshield.transactions. Run load_paysim.py first.")
    sys.exit(1)

logger.info(f"fraudshield.transactions contains {doc_count:,} documents.")

# ── Pick representative test accounts ─────────────────────────────
fraud_accounts = list(collection.distinct("nameOrig", {"isFraud": 1}))
test_fraud_acct = fraud_accounts[0] if fraud_accounts else "C1231006815"

# Normal account with significant activity (use distinct + sampling)
sample_txns = list(collection.aggregate([
    {"$match": {"isFraud": 0, "type": "CASH_OUT"}},
    {"$limit": 50},
    {"$project": {"nameOrig": 1}}
]))
test_normal_acct = sample_txns[0]["nameOrig"] if sample_txns else "C1231006815"

# Get step range from a real transaction
sample_txn = collection.find_one({"nameOrig": test_fraud_acct}, sort=[("step", -1)])
test_step = sample_txn["step"] if sample_txn else 500

logger.info(f"Test fraud account:    {test_fraud_acct} (step={test_step})")
logger.info(f"Test normal account:   {test_normal_acct}")
logger.info("=" * 60)

# ── 1. Index Verification ─────────────────────────────────────────
logger.info("── Index Verification ──")

expected_indexes = {
    "nameOrig_step": [("nameOrig", 1), ("step", -1)],
    "type_isFraud":  [("type", 1), ("isFraud", 1)],
    "amount":        [("amount", -1)],
    "nameDest_type": [("nameDest", 1), ("type", 1)],
    "step":          [("step", 1)],
}

existing_indexes = {idx["name"]: idx for idx in collection.list_indexes()}

for idx_name, idx_fields in expected_indexes.items():
    if idx_name in existing_indexes:
        logger.info(f"   ✅ Index [{idx_name}] exists")
    else:
        logger.warning(f"   ⚠️  Index [{idx_name}] MISSING - run load_paysim.py to recreate")

logger.info("")

# ── 2. Agent-Style Queries (filtered → fast) ──────────────────────
logger.info("── Agent-Style Queries (targeted) ──")

all_passed = True

# Query A: 24h transaction history (the agent's most frequent query)
t0 = time.time()
history = list(collection.aggregate([
    {"$match": {
        "nameOrig": test_fraud_acct,
        "step": {"$gte": test_step - 24, "$lte": test_step}
    }},
    {"$group": {
        "_id": None,
        "count": {"$sum": 1},
        "totalAmount": {"$sum": "$amount"},
        "avgAmount": {"$avg": "$amount"},
        "types": {"$addToSet": "$type"}
    }}
]))
elapsed_ms = (time.time() - t0) * 1000
status = "✅ FAST" if elapsed_ms < 500 else "⚠️  SLOW"
if elapsed_ms >= 500:
    all_passed = False
h_count = history[0]["count"] if history else 0
logger.info(f"{status} | 24h History Lookup (fraud){'':>5} | {elapsed_ms:6.0f}ms | {h_count} txns")

# Query B: 24h history on normal account
t0 = time.time()
history2 = list(collection.aggregate([
    {"$match": {
        "nameOrig": test_normal_acct,
        "step": {"$gte": test_step - 24, "$lte": test_step}
    }},
    {"$group": {
        "_id": None,
        "count": {"$sum": 1},
        "totalAmount": {"$sum": "$amount"},
    }}
]))
elapsed_ms = (time.time() - t0) * 1000
status = "✅ FAST" if elapsed_ms < 500 else "⚠️  SLOW"
if elapsed_ms >= 500:
    all_passed = False
h2_count = history2[0]["count"] if history2 else 0
logger.info(f"{status} | 24h History Lookup (normal){'':>4} | {elapsed_ms:6.0f}ms | {h2_count} txns")

# Query C: Historical weekly baseline for an account
t0 = time.time()
baseline = list(collection.aggregate([
    {"$match": {"nameOrig": test_fraud_acct}},
    {"$group": {
        "_id": {"week": {"$floor": {"$divide": ["$step", 168]}}},
        "weeklyCount": {"$sum": 1},
        "weeklyAmount": {"$sum": "$amount"}
    }},
    {"$group": {
        "_id": None,
        "avgWeeklyTransactions": {"$avg": "$weeklyCount"},
        "avgWeeklyAmount": {"$avg": "$weeklyAmount"},
        "totalWeeks": {"$sum": 1}
    }}
]))
elapsed_ms = (time.time() - t0) * 1000
status = "✅ FAST" if elapsed_ms < 500 else "⚠️  SLOW"
if elapsed_ms >= 500:
    all_passed = False
if baseline:
    b = baseline[0]
    logger.info(f"{status} | Historical Baseline{'':>11} | {elapsed_ms:6.0f}ms | {b['totalWeeks']} weeks, ~{b['avgWeeklyTransactions']:.1f} txn/wk")
else:
    logger.info(f"{status} | Historical Baseline{'':>11} | {elapsed_ms:6.0f}ms | no history")

# Query D: Recipient mule check (simple indexed find)
t0 = time.time()
mule_check = list(collection.find(
    {"nameDest": test_fraud_acct, "type": "TRANSFER"},
    limit=20
))
elapsed_ms = (time.time() - t0) * 1000
status = "✅ FAST" if elapsed_ms < 500 else "⚠️  SLOW"
if elapsed_ms >= 500:
    all_passed = False
logger.info(f"{status} | Recipient Mule Check{'':8} | {elapsed_ms:6.0f}ms | {len(mule_check)} incoming")

# Query E: Hourly velocity (the agent's highest-frequency check)
t0 = time.time()
velocity = list(collection.aggregate([
    {"$match": {
        "nameOrig": test_fraud_acct,
        "step": {"$gte": test_step - 1, "$lte": test_step}
    }},
    {"$group": {
        "_id": "$hour",
        "count": {"$sum": 1},
        "totalValue": {"$sum": "$amount"},
    }}
]))
elapsed_ms = (time.time() - t0) * 1000
status = "✅ FAST" if elapsed_ms < 500 else "⚠️  SLOW"
if elapsed_ms >= 500:
    all_passed = False
v_total = sum(v["count"] for v in velocity)
logger.info(f"{status} | Hourly Velocity Check{'':9} | {elapsed_ms:6.0f}ms | {v_total} txn(s) in hour")

# Query F: Fraud count (simple indexed count)
t0 = time.time()
fraud_count = collection.count_documents({"isFraud": 1})
elapsed_ms = (time.time() - t0) * 1000
status = "✅ FAST" if elapsed_ms < 500 else "⚠️  SLOW"
if elapsed_ms >= 500:
    all_passed = False
logger.info(f"{status} | Fraud Count (indexed){'':11} | {elapsed_ms:6.0f}ms | {fraud_count:,} fraudulent")

logger.info("")

# ── 3. Full-Collection Analytical Queries ────────────────────────
logger.info("── Full-Collection Queries (allowDiskUse) ──")

FULL_QUERIES = {
    "Rapid Cash-Out (filtered)": [
        {"$match": {"type": "CASH_OUT", "amount": {"$gt": 100000}}},
        {"$group": {
            "_id": "$nameOrig",
            "count": {"$sum": 1},
            "totalAmount": {"$sum": "$amount"},
        }},
        {"$match": {"count": {"$gt": 3}}},
        {"$sort": {"totalAmount": -1}},
        {"$limit": 20},
    ],
    "Mule Pattern (filtered)": [
        {"$match": {"type": "TRANSFER"}},
        {"$group": {
            "_id": "$nameDest",
            "receivedAmount": {"$sum": "$amount"},
            "incomingCount": {"$sum": 1},
        }},
        {"$match": {"incomingCount": {"$gt": 10}}},
        {"$sort": {"receivedAmount": -1}},
        {"$limit": 20},
    ],
    "Balance Mismatch (large-only)": [
        {"$match": {
            "type": {"$in": ["CASH_OUT", "TRANSFER"]},
            "amount": {"$gt": 50000}
        }},
        {"$addFields": {
            "balanceDiff": {
                "$abs": {"$subtract": ["$newbalanceOrig", "$expectedNewBalanceOrg"]}
            }
        }},
        {"$match": {"balanceDiff": {"$gt": 0.01}}},
        {"$sort": {"balanceDiff": -1}},
        {"$limit": 20},
    ],
    "Fraud by Type Breakdown": [
        {"$match": {"isFraud": 1}},
        {"$group": {
            "_id": "$type",
            "count": {"$sum": 1},
            "totalAmount": {"$sum": "$amount"},
        }},
        {"$sort": {"count": -1}},
    ],
}

for name, pipeline in FULL_QUERIES.items():
    t0 = time.time()
    try:
        results = list(collection.aggregate(pipeline, allowDiskUse=True))
        elapsed_ms = (time.time() - t0) * 1000

        status = "✅ FAST" if elapsed_ms < 500 else "⚠️  SLOW"
        if elapsed_ms >= 500:
            all_passed = False

        logger.info(f"{status} | {name:<30} | {elapsed_ms:6.0f}ms | {len(results):,} results")
    except Exception as e:
        logger.error(f"❌ ERROR | {name:<30} | {e}")
        all_passed = False

# ── Collection counts ─────────────────────────────────────────────
logger.info("")
logger.info(f"transactions:      {collection.count_documents({}):,} documents")
logger.info(f"alerts:            {db['alerts'].count_documents({}):,} documents")
logger.info(f"risk_scores:       {db['risk_scores'].count_documents({}):,} documents")
logger.info(f"flagged_accounts:  {db['flagged_accounts'].count_documents({}):,} documents")

logger.info("=" * 60)

if all_passed:
    logger.info("✅ Day 1 verification complete. All queries under 500ms. Ready for Day 2.")
else:
    logger.warning(
        "⚠️  Some queries exceeded 500ms. If on M0, upgrade to M10 for dedicated RAM. "
        "Also verify indexes at: Atlas → Collections → Indexes."
    )
