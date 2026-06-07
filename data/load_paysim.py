"""
load_paysim.py - PaySim Data Loader
Loads the PaySim CSV into MongoDB Atlas in chunks with derived fields and indexes.

Usage:
    python data/load_paysim.py
"""

import os
import time
import sys

import certifi
import pandas as pd
from dotenv import load_dotenv
from loguru import logger
from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.errors import BulkWriteError
from tqdm import tqdm

# ── Load environment ──────────────────────────────────────────────
load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "fraudshield")
PAYSIM_CSV_PATH = os.getenv("PAYSIM_CSV_PATH", "./raw_materials/PS_20174392719_1491204439457_log.csv")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "10000"))

if not MONGODB_URI:
    logger.error("MONGODB_URI not set in .env - cannot connect to MongoDB Atlas.")
    sys.exit(1)

# ── Connect to MongoDB ────────────────────────────────────────────
logger.info("Connecting to MongoDB Atlas...")

# Only use TLS certificate bundle for Atlas (mongodb+srv://) connections
mongo_kwargs = {}
if MONGODB_URI.startswith("mongodb+srv://"):
    mongo_kwargs["tlsCAFile"] = certifi.where()

client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=30000, **mongo_kwargs)
db = client[MONGODB_DATABASE]
collection = db["transactions"]

# Verify connectivity
try:
    client.admin.command("ping")
    logger.info("✅ Connected to MongoDB Atlas successfully.")
except Exception as e:
    logger.error(f"❌ Failed to connect to MongoDB Atlas: {e}")
    sys.exit(1)

# ── Check CSV exists ──────────────────────────────────────────────
if not os.path.exists(PAYSIM_CSV_PATH):
    logger.error(f"PaySim CSV not found at: {PAYSIM_CSV_PATH}")
    sys.exit(1)

file_size_mb = os.path.getsize(PAYSIM_CSV_PATH) / (1024 * 1024)
logger.info(f"PaySim CSV: {PAYSIM_CSV_PATH} ({file_size_mb:.0f} MB)")

# ── Drop existing data (idempotent re-run) ────────────────────────
logger.info("Dropping existing transactions collection (if any)...")
collection.drop()
logger.info("✅ Existing data cleared.")

# ── Stream CSV → MongoDB ──────────────────────────────────────────
logger.info(f"Loading PaySim data in batches of {BATCH_SIZE:,} rows...")
start_time = time.time()
total_rows = 0
total_batches = 0

try:
    reader = pd.read_csv(PAYSIM_CSV_PATH, chunksize=BATCH_SIZE)

    for chunk in tqdm(reader, desc="Loading", unit="batch"):
        # Add derived field: expectedNewBalanceOrg = oldbalanceOrg - amount
        chunk["expectedNewBalanceOrg"] = chunk["oldbalanceOrg"] - chunk["amount"]

        # Convert to list of dicts for insert_many
        documents = chunk.to_dict(orient="records")

        try:
            collection.insert_many(documents, ordered=False)
        except BulkWriteError as bwe:
            # ordered=False means duplicates don't abort the batch
            n_inserted = bwe.details.get("nInserted", 0)
            total_rows += n_inserted
            total_batches += 1
            continue

        total_rows += len(documents)
        total_batches += 1

        if total_batches % 100 == 0:
            elapsed = time.time() - start_time
            rate = total_rows / elapsed if elapsed > 0 else 0
            logger.debug(
                f"Batch {total_batches} | {total_rows:,} rows | "
                f"{rate:,.0f} docs/sec"
            )

except Exception as e:
    logger.error(f"❌ Fatal error during load: {e}")
    sys.exit(1)

elapsed = time.time() - start_time
rate = total_rows / elapsed if elapsed > 0 else 0
logger.info(f"✅ Loaded {total_rows:,} documents in {elapsed:.1f}s ({rate:,.0f} docs/sec)")
logger.info(f"   Batches: {total_batches} | Collection: {MONGODB_DATABASE}.transactions")

# ── Create indexes (AFTER bulk insert - faster on existing data) ──
logger.info("Creating compound indexes...")

indexes = [
    # 1. Agent 24h history lookup - most critical
    ([("nameOrig", ASCENDING), ("step", DESCENDING)], "nameOrig_step"),
    # 2. Fraud type filtering
    ([("type", ASCENDING), ("isFraud", ASCENDING)], "type_isFraud"),
    # 3. Amount anomaly detection
    ([("amount", DESCENDING)], "amount"),
    # 4. Recipient mule checks
    ([("nameDest", ASCENDING), ("type", ASCENDING)], "nameDest_type"),
    # 5. Time-based queries
    ([("step", ASCENDING)], "step"),
]

for fields, name in indexes:
    t0 = time.time()
    collection.create_index(fields, name=name, background=True)
    logger.info(f"   ✅ Index [{name}] created in {time.time() - t0:.1f}s")

# ── Create supporting collections ─────────────────────────────────
logger.info("Creating supporting collections...")

# fraudshield.alerts - agent decisions
alerts_collection = db["alerts"]
alerts_collection.create_index([("timestamp", DESCENDING)], name="timestamp_desc")
alerts_collection.create_index([("risk_score", DESCENDING)], name="risk_score_desc")
logger.info("   ✅ fraudshield.alerts (indexed)")

# fraudshield.risk_scores - per-account risk profiles
risk_scores = db["risk_scores"]
risk_scores.create_index([("nameOrig", ASCENDING)], unique=True, name="nameOrig_unique")
logger.info("   ✅ fraudshield.risk_scores (unique index)")

# fraudshield.flagged_accounts - known mule accounts
flagged = db["flagged_accounts"]
flagged.create_index([("accountId", ASCENDING)], unique=True, name="accountId_unique")
logger.info("   ✅ fraudshield.flagged_accounts (unique index)")

# ── Final summary ─────────────────────────────────────────────────
final_count = collection.count_documents({})
logger.info("=" * 60)
logger.info(f"🎉 Day 1 load complete!")
logger.info(f"   Documents in fraudshield.transactions: {final_count:,}")
logger.info(f"   Total time: {elapsed:.1f}s")
logger.info(f"   Throughput: {rate:,.0f} docs/sec")
logger.info(f"   Indexes: {len(indexes)} compound indexes created")
logger.info(f"   Supporting collections: alerts, risk_scores, flagged_accounts")
logger.info("=" * 60)
logger.info("Ready for: python data/verify_day1.py")
