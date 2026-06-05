# FraudShield Agent — Complete Project Delivery Roadmap

### Google Cloud Rapid Agent Hackathon | MongoDB Track | Deadline: June 11, 2026 @ 2:00 PM PDT (11:00 PM EAT)

> This document is the single source of truth for building and delivering FraudShield Agent from scratch to submission. Every decision, every file, every query, every prompt, and every deployment step is documented here. No back-and-forth required.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture](#2-architecture)
3. [Repository Structure](#3-repository-structure)
4. [Environment Setup](#4-environment-setup)
5. [Day 1 — Data Foundation](#5-day-1--data-foundation)
6. [Day 2 — MongoDB MCP Server](#6-day-2--mongodb-mcp-server)
7. [Day 3 — Gemini Agent Core](#7-day-3--gemini-agent-core)
8. [Day 4 — Actions & Alerts](#8-day-4--actions--alerts)
9. [Day 5 — React Dashboard + FastAPI Backend](#9-day-5--react-dashboard--fastapi-backend)
10. [Day 6 — Docker & Cloud Run Deployment](#10-day-6--docker--cloud-run-deployment)
11. [Day 7 — GitHub Repository](#11-day-7--github-repository)
12. [Day 8 — Demo Video Script](#12-day-8--demo-video-script)
13. [Day 9 — Devpost Submission](#13-day-9--devpost-submission)
14. [All MongoDB Aggregation Queries](#14-all-mongodb-aggregation-queries)
15. [All Gemini Prompts](#15-all-gemini-prompts)
16. [Environment Variables Reference](#16-environment-variables-reference)
17. [Troubleshooting Guide](#17-troubleshooting-guide)
18. [Submission Checklist](#18-submission-checklist)

---

## 1. Project Overview

### What FraudShield Agent Does

FraudShield Agent is an autonomous AI agent that detects and blocks mobile money fraud in real time. It is not a chatbot — it is an agent that:

1. Receives a transaction
2. Gemini 2.5 Flash decides WHICH tools to call and HOW DEEP to investigate
3. Agent dynamically queries MongoDB via MCP (history, velocity, mule, baseline, risk history, balance mismatch)
4. Each tool result feeds back into Gemini for the next decision — max 6 turns
5. When confident, Gemini calls submit_risk_decision with a risk score 0-100
6. Action Executor routes: allow / flag / block + inserts alert + sends SMS
7. Full investigation trace (tool calls, reasoning, analysis) rendered in the dashboard

### Why It Wins the MongoDB Track

- Uses 5 MCP tools: `find`, `aggregate`, `insert_one`, `update_one`, `count`
- Runs on 6.3 million real PaySim transactions in MongoDB Atlas
- True multi-turn agent — Gemini chooses tools dynamically
- Real-world problem with massive impact in Sub-Saharan Africa
- Complete end-to-end flow: transaction in → agent investigation → reasoning → action out

### Hackathon Details

- **Event:** Google Cloud Rapid Agent Hackathon
- **URL:** https://rapid-agent.devpost.com
- **Track:** MongoDB
- **Prize:** $5,000 (1st), $3,000 (2nd), $2,000 (3rd)
- **Deadline:** June 11, 2026 @ 2:00 PM PDT = June 11, 2026 @ 11:00 PM EAT
- **Judges:** Daoud Farooqi (Partner Solutions Architect, MongoDB) and Gaurab Aryal (Senior PM, MongoDB)

### Judging Criteria

| Criterion                    | Weight | How FraudShield Delivers                     |
| ---------------------------- | ------ | -------------------------------------------- |
| Technological Implementation | High   | 5 MCP tools, Gemini reasoning, 6.3M docs     |
| Design                       | Medium | Professional React dashboard with live feed  |
| Potential Impact             | High   | Stops mobile money fraud before money leaves |
| Quality of Idea              | Medium | Autonomous agent, not a chatbot              |

---

## 2. Architecture

```
┌─────────────────────────────────────────────────┐
│              Incoming Transaction                │
│   { type, amount, nameOrig, nameDest, step }     │
└─────────────────────┬───────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────┐
│     FraudShield Agent (Python)                   │
│     Gemini 2.5 Flash with function calling        │
│                                                  │
│  Multi-turn dynamic investigation:               │
│  Turn 1: fetch_account_history (always first)    │
│  Turn 2+: Gemini decides — velocity? mule?       │
│          baseline? risk_history? balance?         │
│  Final:  submit_risk_decision → score + action   │
│                                                  │
│  7 registered tools, max 6 turns                 │
└──────────────┬──────────────────────────────────┘
               │  MongoDB MCP Server (npx)
               ▼
┌─────────────────────────────────────────────────┐
│              MongoDB Atlas                       │
│                                                  │
│  fraudshield.transactions   (6.3M documents)    │
│  fraudshield.alerts         (agent decisions)   │
│  fraudshield.risk_scores    (per-account)       │
│  fraudshield.flagged_accounts (known mules)     │
└──────────────┬──────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────┐
│              Action Executor                     │
│                                                  │
│  Risk 0-30  → Allow  → log normal               │
│  Risk 31-60 → Flag   → insert_one (alert)       │
│  Risk 61-100→ Block  → insert_one + SMS alert   │
└─────────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────┐
│         React Dashboard (FastAPI + WebSocket)   │
│  - Live metrics (volume, fraud, alerts)         │
│  - Manual transaction analysis (fly-out modal)  │
│  - Real-time replay via WebSocket               │
│  - Split-pane: results + terminal logs          │
│  - Agent trace with per-step reasoning          │
│  - Heuristic baseline on every response         │
└─────────────────────────────────────────────────┘
```

### Technology Stack

| Layer            | Technology                | Version                        |
| ---------------- | ------------------------- | ------------------------------ |
| Agent Brain      | Google Gemini 2.5 Flash   | Latest via google-generativeai |
| Backend          | FastAPI + Uvicorn         | 0.115+                         |
| Frontend         | React + TypeScript + Vite | 19+ / 8+                       |
| Database         | MongoDB Atlas             | M0 Free Tier                   |
| MCP Integration  | mongodb-mcp-server        | Latest via npx                 |
| Realtime         | WebSocket (native)        | —                              |
| Deployment       | Google Cloud Run          | Latest                         |
| Language         | Python 3.12+ / TypeScript | —                              |
| Containerisation | Docker                    | Latest                         |

---

## 3. Repository Structure

```
fraudshield-agent/
│
├── README.md                        # Project overview and setup instructions
├── LICENSE                          # MIT License — REQUIRED by hackathon rules
├── requirements.txt                 # Python dependencies
├── .env.example                     # Environment variables template (no secrets)
├── .gitignore                       # Ignore .env, __pycache__, data/*.csv, logs/
├── Dockerfile                       # Container definition for Cloud Run
├── docker-compose.yml               # Local multi-service orchestration
│
├── config/
│   └── mcp_config.json              # MongoDB MCP server configuration
│
├── data/
│   ├── load_paysim.py               # Batch CSV loader into MongoDB Atlas
│   └── verify_day1.py               # Post-load verification script
│
├── agent/
│   ├── agent_core.py                # Multi-turn agent with Gemini function calling (main)
│   ├── mongo_mcp.py                 # Persistent MCP client with auto-reconnect
│   ├── gemini_client.py             # Legacy single-shot Gemini wrapper + heuristic fallback
│   ├── fraud_detector.py            # Original fixed pipeline (reference)
│   └── actions.py                   # Block / flag / allow action executor
│
├── api/
│   └── server.py                    # FastAPI backend (REST + WebSocket)
│
├── frontend/                        # React + TypeScript + Vite dashboard
│   ├── src/
│   │   ├── api.ts                   # API client + WebSocket helper
│   │   ├── App.tsx                  # Root — login gate
│   │   ├── App.css                  # Professional light theme
│   │   ├── pages/
│   │   │   ├── Login.tsx            # admin/admin auth
│   │   │   └── Dashboard.tsx        # Main dashboard layout
│   │   └── components/
│   │       ├── Navbar.tsx           # Top navigation bar
│   │       ├── MetricsBar.tsx       # Live MongoDB counts
│   │       ├── TransactionForm.tsx  # Validated txn input
│   │       ├── ResultCard.tsx       # AI analysis display
│   │       └── ReplayPanel.tsx      # WebSocket replay + split pane
│   └── index.html
│
├── queries/
│   ├── rapid_cashout.js             # Aggregation pipeline: rapid cash-out
│   ├── mule_network.js              # Aggregation pipeline: money mule network
│   ├── balance_mismatch.js          # Aggregation pipeline: balance mismatch
│   └── velocity_check.js            # Aggregation pipeline: high-velocity
│
└── logs/                            # Auto-created at runtime, gitignored
```

---

## 4. Environment Setup

### Prerequisites

- Python 3.12 or higher
- Node.js 18 or higher (for MCP server + frontend)
- pnpm (for frontend package management)
- MongoDB Atlas account (free M0 tier is sufficient)
- Google Cloud account with Gemini API key
- Git

### Step-by-Step Local Setup

```bash
# 1. Clone the repository
git clone https://github.com/axoblade/fraudshield-agent.git
cd fraudshield-agent

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate        # Mac/Linux
venv\Scripts\activate           # Windows

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Install frontend dependencies
cd frontend && pnpm install && cd ..

# 5. Copy and configure environment variables
cp .env.example .env
# Open .env in your editor and fill in all values

# 6. Create the logs directory
mkdir -p logs
```

### Running the Application

```bash
# Terminal 1 — Backend API
source venv/bin/activate
uvicorn api.server:app --reload --port 8000

# Terminal 2 — Frontend
cd frontend && pnpm dev
```

Open `http://localhost:5173` — login with **admin / admin**.

# 5. Copy and configure environment variables

cp .env.example .env

# Open .env in your editor and fill in all values

# 6. Create the logs directory

mkdir -p logs

```

### requirements.txt — Full Content
```

pymongo[srv]==4.7.2
python-dotenv==1.0.1
pandas==2.2.2
google-generativeai==0.7.2
google-cloud-aiplatform==1.57.0
tqdm==4.66.4
tenacity==8.3.0
loguru==0.7.2
mcp>=1.0.0
fastapi>=0.115.0
uvicorn>=0.49.0
websockets>=14.0

````

---

## 5. Day 1 — Data Foundation

**Goal:** 6.3M PaySim transactions loaded into MongoDB Atlas, all indexes created, all 4 fraud detection queries returning results in under 500ms.

### Step 1.1 — MongoDB Atlas Setup

1. Go to https://cloud.mongodb.com
2. Create a new project called `fraudshield`
3. Build a free M0 cluster (any region, closest to you)
4. Under Database Access → Add a database user with read/write privileges
5. Under Network Access → Add IP Address → Allow Access from Anywhere (0.0.0.0/0)
6. Click Connect → Drivers → Copy the connection string
7. Replace `<password>` in the string with your actual password
8. Paste the full string into your `.env` as `MONGODB_URI`

### Step 1.2 — Download PaySim Dataset

1. Go to: https://www.kaggle.com/datasets/ealaxi/paysim1
2. Download `PS_20174392719_1491204439457_log.csv` (~500MB)
3. Place it inside the `data/` folder of your project

### Step 1.3 — data/load_paysim.py

This script reads the PaySim CSV in chunks of 10,000 rows and inserts them into MongoDB Atlas using `insertMany()`. It also creates all required indexes and supporting collections.

**Key implementation details:**
- Use `pd.read_csv(path, chunksize=10000)` to stream the file — never load 500MB into memory at once
- Add a derived field `expectedNewBalanceOrg = oldbalanceOrg - amount` to each document — this is used in the balance mismatch query
- Create indexes AFTER the bulk insert, not before — MongoDB builds indexes faster on existing data
- Use `ordered=False` in `insertMany()` so duplicate key errors don't abort the entire batch
- The loader should print progress every 100 batches and log total time and throughput on completion

**Documents inserted into `fraudshield.transactions` look like this:**
```json
{
  "step": 1,
  "hour": 1,
  "type": "CASH_OUT",
  "amount": 9839.64,
  "nameOrig": "C1231006815",
  "oldbalanceOrg": 170136.0,
  "newbalanceOrig": 160296.36,
  "nameDest": "M1979787155",
  "oldbalanceDest": 0.0,
  "newbalanceDest": 0.0,
  "isFraud": 0,
  "isFlaggedFraud": 0,
  "expectedNewBalanceOrg": 160296.36
}
````

**Compound indexes to create (in this order, after load):**

```javascript
// 1. Agent 24h history lookup — most critical
{ "nameOrig": 1, "step": -1 }

// 2. Fraud type filtering
{ "type": 1, "isFraud": 1 }

// 3. Amount anomaly detection
{ "amount": -1 }

// 4. Recipient mule checks
{ "nameDest": 1, "type": 1 }

// 5. Time-based queries
{ "step": 1 }
```

**Supporting collections to create:**

- `fraudshield.alerts` — indexed on `timestamp` (desc) and `risk_score` (desc)
- `fraudshield.risk_scores` — unique index on `nameOrig`
- `fraudshield.flagged_accounts` — unique index on `accountId`

**Expected completion:** ~4 minutes, ~300,000 docs/sec throughput.

### Step 1.4 — data/verify_day1.py

Run this after the loader finishes. It executes all 4 fraud detection pipelines and reports response time for each.

**Expected output:**

```
✅ FAST | Rapid Cash-Out Detection      | 142ms | 847 results
✅ FAST | High-Velocity Transfer        | 198ms | 2341 results
✅ FAST | Balance Mismatch Fraud        | 89ms  | 8213 results
✅ FAST | Known Fraud Accounts Summary  | 44ms  | 5 results

transactions:      6,362,620 documents
alerts:            0 documents
risk_scores:       0 documents
flagged_accounts:  0 documents

Day 1 verification complete. Ready for Day 2.
```

If any query shows ⚠️ SLOW (over 500ms), the indexes did not build correctly. Drop and recreate them manually in the Atlas UI under: Cluster → Collections → Indexes.

---

## 6. Day 2 — MongoDB MCP Server

**Goal:** The MCP server is running, all 5 MCP tools are tested manually, and all 4 aggregation pipelines are verified to work via the MCP interface.

### Step 2.1 — config/mcp_config.json

```json
{
	"mcpServers": {
		"mongodb": {
			"command": "npx",
			"args": ["-y", "@mongodb-js/mongodb-mcp-server"],
			"env": {
				"MDB_MCP_CONNECTION_STRING": "YOUR_MONGODB_ATLAS_URI_HERE"
			}
		}
	}
}
```

Replace `YOUR_MONGODB_ATLAS_URI_HERE` with your actual Atlas URI. This file is used by Google Cloud Agent Builder to configure the MCP tool connection. Never commit this file with a real URI — add it to `.gitignore`.

### Step 2.2 — agent/mongo_mcp.py

This module is a Python wrapper around the MongoDB MCP server. It exposes 5 clean async methods that the agent calls.

**Class: `MongoDBMCPClient`**

**Constructor:**

- Reads `MONGODB_URI` from environment
- Initialises an `StdioServerParameters` object pointing to `npx @mongodb-js/mongodb-mcp-server`
- Sets the `MDB_MCP_CONNECTION_STRING` env var for the subprocess

**Methods to implement:**

```python
async def find(self, collection: str, query: dict, limit: int = 100) -> list:
    """
    Calls the MCP find tool.
    database = "fraudshield"
    collection = collection param
    filter = json.dumps(query)
    limit = limit param
    Returns: list of matching documents
    """

async def aggregate(self, collection: str, pipeline: list) -> list:
    """
    Calls the MCP aggregate tool.
    database = "fraudshield"
    collection = collection param
    pipeline = json.dumps(pipeline)
    Returns: list of aggregation results
    """

async def insert_one(self, collection: str, document: dict) -> str:
    """
    Calls the MCP insert-one tool.
    Returns: inserted document ID as string
    """

async def update_one(self, collection: str, filter: dict, update: dict) -> dict:
    """
    Calls the MCP update-one tool.
    update should use MongoDB update operators e.g. {"$set": {...}, "$inc": {...}}
    Returns: result with matchedCount and modifiedCount
    """

async def count(self, collection: str, query: dict = {}) -> int:
    """
    Calls the MCP count tool.
    Returns: integer count of matching documents
    """
```

**Error handling pattern for every method:**

```python
async with ClientSession(self.server_params) as session:
    await session.initialize()
    result = await session.call_tool("find", arguments={...})
    raw = result.content[0].text
    return json.loads(raw)
```

Wrap every call in `try/except` and re-raise as a custom `MCPConnectionError` with the original message.

### Step 2.3 — Manual MCP Tool Tests

After implementing `mongo_mcp.py`, write a quick test script `test_mcp.py` (not committed, just for verification) that calls all 5 methods and prints results:

```python
import asyncio
from agent.mongo_mcp import MongoDBMCPClient

async def test():
    mcp = MongoDBMCPClient()

    # Test 1: find
    results = await mcp.find("transactions", {"isFraud": 1}, limit=3)
    print(f"find: {len(results)} fraud transactions found")

    # Test 2: aggregate
    results = await mcp.aggregate("transactions", [
        {"$match": {"type": "CASH_OUT"}},
        {"$group": {"_id": None, "count": {"$sum": 1}, "total": {"$sum": "$amount"}}},
    ])
    print(f"aggregate: {results}")

    # Test 3: insert_one
    doc_id = await mcp.insert_one("alerts", {
        "test": True, "message": "MCP insert_one working"
    })
    print(f"insert_one: {doc_id}")

    # Test 4: update_one
    result = await mcp.update_one(
        "alerts",
        {"test": True},
        {"$set": {"verified": True}}
    )
    print(f"update_one: {result}")

    # Test 5: count
    count = await mcp.count("transactions", {"isFraud": 1})
    print(f"count: {count} fraud transactions")

asyncio.run(test())
```

All 5 tests must pass before moving to Day 3.

---

## 7. Day 3 — Gemini Agent Core

> **What we built:** The original plan called for a fixed 7-step pipeline. During implementation, this evolved into a **multi-turn agent with Gemini function calling** — the agent dynamically chooses which tools to call based on what it finds. See `agent/agent_core.py` for the implementation.

**Goal:** The agent follows a dynamic investigation workflow, calling tools via Gemini function calling until confident enough to submit a risk decision (max 6 turns).

### Step 3.1 — agent/gemini_client.py

This module wraps Google Gemini 3 and exposes a single method: `reason_about_transaction`.

**Class: `GeminiClient`**

**Constructor:**

- Reads `GEMINI_API_KEY` from environment
- Calls `genai.configure(api_key=...)`
- Instantiates `genai.GenerativeModel('gemini-2.5-flash')` — use flash for speed and cost

**Method: `reason_about_transaction`**

Takes a pre-assembled context dict and returns a structured JSON decision.

**Input context dict:**

```python
{
    "transaction": {
        "nameOrig": "C123456789",
        "type": "CASH_OUT",
        "amount": 5000.00,
        "step": 500,
        "nameDest": "M987654321",
        "oldbalanceOrg": 5200.00,
        "newbalanceOrig": 200.00,
    },
    "history_24h": {
        "transaction_count": 9,
        "total_amount": 6200.00,
        "types": ["CASH_OUT", "CASH_OUT", "TRANSFER"],
        "avg_amount": 688.89,
    },
    "baseline": {
        "avg_weekly_transactions": 1.5,
        "avg_weekly_amount": 450.00,
    },
    "recipient_flagged": False,
    "velocity_score": 8.7,
}
```

**The Gemini prompt (exact text to use):**

```
You are FraudShield, an expert fraud detection AI for a mobile money platform.

Analyze the following transaction and context, then return a fraud risk assessment.

CURRENT TRANSACTION:
- Account: {nameOrig}
- Type: {type}
- Amount: ${amount:,.2f}
- Time Step: {step}
- Destination: {nameDest}

ACCOUNT ACTIVITY (last 24 hours):
- Transactions: {transaction_count}
- Total Amount: ${total_amount:,.2f}
- Average per transaction: ${avg_amount:,.2f}

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

{
  "risk_score": <integer 0-100>,
  "risk_level": "<low|medium|high>",
  "action": "<allow|flag|block>",
  "reasoning": "<2-3 sentence explanation of the key signals that drove this score>",
  "key_signals": ["<signal 1>", "<signal 2>", "<signal 3>"]
}
```

**Retry logic:**
Use the `tenacity` library to retry up to 3 times if Gemini returns malformed JSON:

````python
from tenacity import retry, stop_after_attempt, wait_fixed

@retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
def _call_gemini(self, prompt: str) -> dict:
    response = self.model.generate_content(prompt)
    text = response.text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())
````

### Step 3.2 — agent/fraud_detector.py

This is the core agent. It orchestrates the 7 steps by calling `MongoDBMCPClient` and `GeminiClient`.

**Class: `FraudDetectorAgent`**

**Constructor:**

- Instantiates `MongoDBMCPClient` and `GeminiClient`
- Reads thresholds from env: `RISK_BLOCK_THRESHOLD=61`, `RISK_FLAG_THRESHOLD=31`

**Main method: `async evaluate_transaction(transaction: dict) -> dict`**

```
Step 1 — Validate input
    Required fields: step, type, amount, nameOrig, nameDest
    Raise ValueError if any are missing

Step 2 — Fetch 24h history via MCP find()
    Query: { nameOrig: transaction.nameOrig, step: { $gte: transaction.step - 24 } }
    Collection: transactions
    Limit: 500

Step 3 — Calculate velocity via MCP aggregate()
    Pipeline: match nameOrig + recent steps, group by null, sum count and amount
    Also calculate avg_amount from the history list directly

Step 4 — Check recipient mule status via MCP find()
    Query: { accountId: transaction.nameDest }
    Collection: flagged_accounts
    recipient_flagged = len(results) > 0

Step 5 — Get baseline via MCP aggregate()
    Pipeline: match nameOrig across all history, group by week bucket, avg count and amount
    If no history exists (new account), use conservative defaults: avg_weekly=0, avg_amount=0

Step 6 — Assemble context dict and call GeminiClient.reason_about_transaction()
    This returns the structured decision JSON

Step 7 — Execute action based on risk_score
    Call actions.execute(transaction, decision)
    Return the full decision dict with transaction attached
```

**Timing:** Log the total execution time for each evaluation. Target is under 2 seconds end-to-end.

### Step 3.3 — Smoke Test

Create 5 test transactions and run them through the agent:

```python
# Test transactions
transactions = [
    # 1. Normal small transaction
    {"step": 100, "type": "PAYMENT", "amount": 50, "nameOrig": "C111111111",
     "nameDest": "M222222222", "oldbalanceOrg": 1000, "newbalanceOrig": 950},

    # 2. Large CASH_OUT — should trigger high risk
    {"step": 500, "type": "CASH_OUT", "amount": 9999, "nameOrig": "C1231006815",
     "nameDest": "M1979787155", "oldbalanceOrg": 10000, "newbalanceOrig": 1},

    # 3. Known fraudulent transaction from PaySim (isFraud=1)
    # Pull one from the database to test

    # 4. Transfer to new account
    {"step": 300, "type": "TRANSFER", "amount": 500, "nameOrig": "C333333333",
     "nameDest": "C444444444", "oldbalanceOrg": 2000, "newbalanceOrig": 1500},

    # 5. Micro transaction (common in mule laundering)
    {"step": 200, "type": "TRANSFER", "amount": 1.00, "nameOrig": "C555555555",
     "nameDest": "C666666666", "oldbalanceOrg": 500, "newbalanceOrig": 499},
]
```

Expected results: Transaction 1 should score under 30. Transaction 2 should score over 61 and trigger a block.

---

## 8. Day 4 — Actions & Alerts

**Goal:** The agent doesn't just score transactions — it takes action. Blocks are logged to MongoDB, SMS alerts are sent, and risk profiles are updated.

### Step 4.1 — agent/actions.py

**Class: `ActionExecutor`**

**Constructor:**

- Instantiates `MongoDBMCPClient`
- SMS alerts via generic `send_sms()` function (console logger by default — plug in any provider)

**Methods:**

```python
async def execute(self, transaction: dict, decision: dict) -> dict:
    """
    Routes to the correct action based on risk_score.
    Returns a result dict with action_taken and any IDs.
    """
    score = decision["risk_score"]
    if score >= RISK_BLOCK_THRESHOLD:
        return await self._block(transaction, decision)
    elif score >= RISK_FLAG_THRESHOLD:
        return await self._flag(transaction, decision)
    else:
        return await self._allow(transaction, decision)


async def _block(self, transaction: dict, decision: dict) -> dict:
    """
    1. Insert alert document into fraudshield.alerts
    2. Update risk_score profile in fraudshield.risk_scores
    3. Send SMS alert to account holder
    Returns: { "action": "block", "alert_id": "...", "sms_sent": True/False }
    """

async def _flag(self, transaction: dict, decision: dict) -> dict:
    """
    1. Insert alert document into fraudshield.alerts (lower priority)
    2. Update risk_score profile
    Returns: { "action": "flag", "alert_id": "..." }
    """

async def _allow(self, transaction: dict, decision: dict) -> dict:
    """
    1. Update risk_score profile with normal activity log
    Returns: { "action": "allow" }
    """
```

**Alert document schema (inserted via MCP insert_one):**

```json
{
  "transaction": { ...original transaction fields... },
  "risk_score": 87,
  "risk_level": "high",
  "action": "block",
  "reasoning": "Account performed 9 CASH_OUT transactions in 20 hours...",
  "key_signals": ["velocity_spike", "amount_anomaly", "new_recipient"],
  "timestamp": "2026-06-02T14:30:00Z",
  "resolved": false,
  "false_positive": null
}
```

**Risk score update document (upserted via MCP update_one):**

```json
{
	"$set": {
		"nameOrig": "C123456789",
		"last_seen": "2026-06-02T14:30:00Z",
		"last_risk_score": 87
	},
	"$inc": {
		"total_transactions": 1,
		"total_blocked": 1
	},
	"$push": {
		"score_history": { "$each": [87], "$slice": -20 }
	}
}
```

**SMS alert (generic — edit `agent/actions.py` to plug in your provider):**

```
FraudShield Alert: A transaction of $5,000 on your account has been
BLOCKED due to suspicious activity (Risk Score: 87/100).
If this was you, contact support immediately. Ref: {alert_id}
```

The `send_sms()` function in `agent/actions.py` logs to console by default.
Replace the body with any SMS provider — Twilio, Vonage, Africa's Talking, etc.
No env vars required.

### Step 4.2 — Transaction Replay Engine

This is needed for the demo video. It reads PaySim transactions chronologically and feeds them to the agent to simulate real-time detection.

**File: `data/replay_engine.py`**

```python
"""
replay_engine.py
Feeds PaySim transactions to the FraudShield agent in chronological order.
Use this for the demo video — set speed to slow enough to show reasoning.
"""

async def replay(speed_multiplier: float = 10.0, limit: int = 1000):
    """
    Fetches transactions from MongoDB ordered by step.
    Feeds them to the agent one by one.
    speed_multiplier: 1.0 = real-time (1 per hour), 10.0 = 10x speed
    limit: number of transactions to replay (use a mix of fraud and normal)
    """
    mcp   = MongoDBMCPClient()
    agent = FraudDetectorAgent()

    # Fetch a mix: all fraud + equal number of normal
    fraud_txns  = await mcp.find("transactions", {"isFraud": 1}, limit=limit//2)
    normal_txns = await mcp.find("transactions", {"isFraud": 0, "type": "CASH_OUT"},
                                  limit=limit//2)
    all_txns = sorted(fraud_txns + normal_txns, key=lambda x: x["step"])

    for txn in all_txns:
        result = await agent.evaluate_transaction(txn)
        print(f"Step {txn['step']} | {txn['type']} | ${txn['amount']:,.0f} | "
              f"Risk: {result['risk_score']} | Action: {result['action'].upper()}")
        await asyncio.sleep(0.5 / speed_multiplier)
```

---

## 9. Day 5 — React Dashboard + FastAPI Backend

**Goal:** A professional React dashboard with real-time WebSocket replay. Judges will open this URL.

### Architecture

```
React (Vite :5173)  ←→  FastAPI (:8000)  ←→  Gemini + MongoDB Atlas
       │                      │
  Login (admin/admin)    POST /api/login (dummy auth)
  Manual Analysis        POST /api/evaluate (7-step pipeline)
  Live Metrics           GET  /api/metrics (MCP count queries)
  Replay Engine          WS   /ws/replay (WebSocket stream)
```

### Backend: `api/server.py`

FastAPI application with CORS, dummy auth tokens, and three endpoints plus one WebSocket:

- `POST /api/login` — accepts `{username, password}`, returns token
- `POST /api/evaluate` — validates transaction, runs full 7-step pipeline, returns risk decision
- `GET /api/metrics` — returns total/fraud/alert counts from MongoDB
- `WS /ws/replay` — streams mixed fraud + normal transactions chronologically; client controls speed and limit

### Frontend: `frontend/`

React 19 + TypeScript + Vite. Professional light theme with Inter font.

| Component         | Purpose                                                                        |
| ----------------- | ------------------------------------------------------------------------------ |
| `Navbar`          | Sticky top bar with shield logo, "Analyze Transaction" + "Logout"              |
| `MetricsBar`      | 3-column live counts: transactions, fraud, alerts                              |
| `TransactionForm` | Validated form (type, amount, day, accounts) — opens in slide-out modal        |
| `ResultCard`      | Color-coded risk result with reasoning + signal tags                           |
| `ReplayPanel`     | Full-width split pane: left = result cards, right = terminal-style verbose log |
| `Login`           | Shield SVG icon, labeled inputs, radial gradient background                    |

The Vite dev server proxies `/api` and `/ws` to the FastAPI backend, so the frontend runs on a single port with no CORS issues in development.

### Key design decisions

- **No emojis** — SVG shield icon, text labels (Blocked/Flagged/Allowed)
- **Light theme** — professional white/gray palette, blue accent
- **Fly-out modal** — manual analysis slides in from the right, doesn't block the replay view
- **Split-pane replay** — results with reasoning on the left, monospace terminal log on the right
- **WebSocket replay** — stop button with 500ms grace period for clean server shutdown

---

## 10. Day 6 — Docker & Cloud Run Deployment

**Goal:** The project is live on a public HTTPS URL.

### Step 6.1 — Dockerfile

```dockerfile
FROM python:3.12-slim

# Install Node.js for MCP server + pnpm for frontend build
RUN apt-get update && apt-get install -y nodejs npm curl && rm -rf /var/lib/apt/lists/*
RUN npm install -g pnpm

WORKDIR /app

# Backend
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Frontend build
COPY frontend/ frontend/
RUN cd frontend && pnpm install && pnpm build

# Copy app code
COPY . .

EXPOSE 8000
CMD ["uvicorn", "api.server:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Step 6.2 — Deploy to Google Cloud Run

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
gcloud services enable run.googleapis.com containerregistry.googleapis.com

gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/fraudshield-agent

gcloud run deploy fraudshield-agent \
  --image gcr.io/YOUR_PROJECT_ID/fraudshield-agent \
  --platform managed --region us-central1 \
  --allow-unauthenticated --min-instances 1 --memory 2Gi \
  --set-env-vars MONGODB_URI="YOUR_URI" \
  --set-env-vars GEMINI_API_KEY="YOUR_KEY" \
  --set-env-vars MONGODB_DATABASE="fraudshield" \
  --set-env-vars RISK_BLOCK_THRESHOLD="61" \
  --set-env-vars RISK_FLAG_THRESHOLD="31"

gcloud run services describe fraudshield-agent \
  --platform managed --region us-central1 \
  --format "value(status.url)"
```

**CRITICAL:** Use `--min-instances 1` to prevent cold starts during the live demo. Cold starts on Cloud Run can take 10-15 seconds which will ruin a demo.

---

## 11. Day 7 — GitHub Repository

**Goal:** Public repo, MIT license visible at the top, clean README, judges can run it in 5 minutes.

### Step 7.1 — .gitignore

```
.env
__pycache__/
*.pyc
*.pyo
venv/
logs/
data/*.csv
data/*.zip
*.egg-info/
.DS_Store
node_modules/
config/mcp_config.json
```

### Step 7.2 — Repository Setup on GitHub

1. Create a new public repository at github.com named `fraudshield-agent`
2. Under the repository description/About section: add website `https://axoblade.com` and topics: `fraud-detection`, `mongodb`, `gemini`, `google-cloud`, `mcp`, `ai-agent`
3. The MIT license must be visible in the About section — GitHub auto-detects it if the file is named `LICENSE` at root

### Step 7.3 — README.md Must Include

- Project title and tagline
- One-paragraph description
- Link to live demo URL
- Link to demo video
- Tech stack list
- Quick start instructions (5 steps max)
- Repository structure tree
- MongoDB collections table
- Built By section with links (Axoblade, LinkedIn, GitHub)
- License badge: `![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)`

---

## 12. Day 8 — Demo Video Script

**Goal:** A 3-minute video that wins judges in the first 30 seconds. Record with OBS (free) or Loom.

### Shot-by-Shot Script

**0:00 – 0:20 | The Hook (voice over a map of Africa)**

> "Over 800 million people in Africa depend on mobile money as their primary financial tool. And every day, fraudsters drain accounts — sometimes before the victim even gets a notification. Traditional fraud detection catches the crime days later. FraudShield Agent stops it before the money moves."

**0:20 – 0:45 | Show the data**

> Switch to MongoDB Atlas UI. Show the transactions collection. Scroll to show 6.3 million documents.
> "We loaded the PaySim dataset — 6.3 million real mobile money transactions — into MongoDB Atlas. Only 0.13% are fraudulent. Finding that needle in the haystack is exactly what FraudShield does."

**0:45 – 1:15 | Show a fraud detection query**

> Switch to terminal or Atlas Aggregation UI. Run the rapid cash-out pipeline.
> "Here's the agent detecting rapid cash-outs. This single aggregation query finds every account that drained over 500,000 in multiple transactions. The result comes back in 142 milliseconds across 6.3 million records — thanks to MongoDB's compound indexes."
> Show the result set.

**1:15 – 2:00 | Live agent evaluation**

> Switch to the React dashboard. Open the manual transaction analysis panel ("Analyze Transaction" button).
> "Now watch the agent reason about a live transaction. I'll submit a suspicious CASH_OUT of $5,000 — this account normally makes one transaction a week under $500."
> Fill in the form. Hit submit. Show the result appearing.
> "The agent fetched 24 hours of history via MongoDB MCP, calculated a velocity score of 8.7 out of 10, checked the recipient against our flagged accounts list, and sent everything to Gemini for reasoning."
> Show the risk score: 87. Show Gemini's reasoning text.
> "Risk score: 87. Transaction BLOCKED."

**2:00 – 2:30 | Show the full loop**

> Switch to the alert feed section of the dashboard.
> "The blocked transaction is immediately logged to MongoDB, and an SMS alert is sent to the account holder."
> Show the alert card appearing in the feed. Show a sample SMS.
> "Every decision the agent makes — the reasoning, the signals, the score — is stored in MongoDB for audit and review."

**2:30 – 3:00 | Impact and close**

> Switch to the live metrics at the top of the dashboard.
> "FraudShield Agent analyzed 6.3 million transactions. It would have caught all 8,213 fraudulent ones — before the money left the account."
> Hold on the dashboard for 5 seconds.
> "Built by Axoblade. FraudShield Agent — AI that doesn't just detect fraud. It stops it."

### Recording Tips

- Use 1080p screen recording minimum
- Speak slowly and clearly — judges watch many videos
- Pause 1 second before and after every key result for emphasis
- If the agent takes more than 3 seconds to respond during recording, do a second take
- Add captions/subtitles if possible (Kapwing is free)
- Upload as unlisted YouTube video or Loom link

---

## 13. Day 9 — Devpost Submission

**Goal:** Submitted before June 11 @ 11:00 PM EAT. Nothing missing.

### Devpost Form Fields

**Project name:** FraudShield Agent

**Tagline:** AI-powered real-time fraud detection that stops mobile money fraud before money leaves the account.

**Elevator pitch (200 chars):**

> AI agent stops mobile money fraud in real-time. Gemini + MongoDB MCP analyzes 6.3M transactions, detects patterns, blocks suspicious cash-outs before money leaves.

**About the project:** Paste the full project story from `FRAUDSHIELD_PROJECT_STORY.md`

**Try it out links:**

- Hosted URL: your Cloud Run URL
- GitHub: https://github.com/axoblade/fraudshield-agent

**Video demo:** YouTube or Loom URL

**Track:** Select MongoDB

**Built with (tag all):**
`google-gemini` `google-cloud-run` `mongodb` `mongodb-atlas` `mongodb-mcp-server` `python` `fastapi` `react` `typescript` `docker` `paysim` `websocket`

**What inspired you:** Use the Inspiration section from the project story

**What you learned:** Use the What We Learned section from the project story

**How you built it:** Use the How We Built It section from the project story

**Challenges:** Use the Challenges We Faced section from the project story

---

## 14. All MongoDB Aggregation Queries

These are the exact pipelines used by the agent. Copy them directly into `queries/` JS files and into the Python agent.

### Query 1: Rapid Cash-Out Detection

```javascript
// queries/rapid_cashout.js
db.transactions.aggregate([
	{ $match: { type: "CASH_OUT" } },
	{
		$group: {
			_id: "$nameOrig",
			count: { $sum: 1 },
			totalAmount: { $sum: "$amount" },
			maxStep: { $max: "$step" },
			minStep: { $min: "$step" },
		},
	},
	{ $match: { count: { $gt: 5 }, totalAmount: { $gt: 500000 } } },
	{ $sort: { totalAmount: -1 } },
	{ $limit: 100 },
]);
```

### Query 2: 24-Hour Transaction Velocity (per account)

```javascript
// Used inside the agent for each evaluated transaction
// Replace ACCOUNT_ID and CURRENT_STEP with runtime values
db.transactions.aggregate([
	{
		$match: {
			nameOrig: "ACCOUNT_ID",
			step: { $gte: CURRENT_STEP - 24, $lte: CURRENT_STEP },
		},
	},
	{
		$group: {
			_id: null,
			count: { $sum: 1 },
			totalAmount: { $sum: "$amount" },
			avgAmount: { $avg: "$amount" },
			types: { $addToSet: "$type" },
		},
	},
]);
```

### Query 3: Money Mule Network Detection

```javascript
// queries/mule_network.js
db.transactions.aggregate([
	{ $match: { type: "TRANSFER" } },
	{
		$group: {
			_id: "$nameDest",
			receivedAmount: { $sum: "$amount" },
			incomingCount: { $sum: 1 },
		},
	},
	{
		$lookup: {
			from: "transactions",
			localField: "_id",
			foreignField: "nameOrig",
			as: "outgoing",
		},
	},
	{
		$addFields: {
			outgoingCount: { $size: "$outgoing" },
			outgoingAmount: { $sum: "$outgoing.amount" },
		},
	},
	{
		$match: {
			incomingCount: { $gt: 10 },
			outgoingCount: { $gt: 0 },
		},
	},
	{ $sort: { receivedAmount: -1 } },
	{ $limit: 50 },
]);
```

### Query 4: Balance Mismatch Fraud Detection

```javascript
// queries/balance_mismatch.js
db.transactions.aggregate([
	{
		$match: {
			type: { $in: ["CASH_OUT", "TRANSFER"] },
		},
	},
	{
		$addFields: {
			balanceDiff: {
				$abs: {
					$subtract: ["$newbalanceOrig", "$expectedNewBalanceOrg"],
				},
			},
		},
	},
	{ $match: { balanceDiff: { $gt: 0.01 } } },
	{ $sort: { balanceDiff: -1 } },
	{ $limit: 100 },
]);
```

### Query 5: High-Velocity Transfer Detection

```javascript
// queries/velocity_check.js
db.transactions.aggregate([
	{
		$group: {
			_id: { account: "$nameOrig", hour: "$hour" },
			transactionCount: { $sum: 1 },
			totalValue: { $sum: "$amount" },
			types: { $addToSet: "$type" },
		},
	},
	{ $match: { transactionCount: { $gt: 5 } } },
	{ $sort: { transactionCount: -1 } },
	{ $limit: 100 },
]);
```

### Query 6: Account Historical Baseline

```javascript
// Used inside the agent to compare current behavior to normal
// Replace ACCOUNT_ID with runtime value
db.transactions.aggregate([
	{ $match: { nameOrig: "ACCOUNT_ID" } },
	{
		$group: {
			_id: { week: { $floor: { $divide: ["$step", 168] } } },
			weeklyCount: { $sum: 1 },
			weeklyAmount: { $sum: "$amount" },
		},
	},
	{
		$group: {
			_id: null,
			avgWeeklyTransactions: { $avg: "$weeklyCount" },
			avgWeeklyAmount: { $avg: "$weeklyAmount" },
			totalWeeks: { $sum: 1 },
		},
	},
]);
```

---

## 15. All Gemini Prompts

### Primary Fraud Evaluation Prompt

(See full prompt text in Section 7.1 above — use that exact text verbatim)

### System Context Prompt (prepend to every conversation)

```
You are FraudShield, an autonomous fraud detection agent for a mobile money platform
serving millions of users across Sub-Saharan Africa. Your role is to analyze transactions
and protect users from fraud. You have access to real-time transaction data via MongoDB MCP.

When evaluating transactions, you must:
1. Always return structured JSON — never plain text
2. Base decisions on data, not assumptions
3. Err on the side of caution for high-value CASH_OUT and TRANSFER transactions
4. Explain your reasoning in plain language that non-technical staff can understand
5. List the specific signals that drove your risk score
```

### False Positive Feedback Prompt (Day 2 enhancement, if time allows)

```
A transaction was blocked with risk score {risk_score} but has been confirmed as legitimate
by the account holder. Here are the transaction details and the original reasoning:

{original_decision}

Update your assessment. Identify what signals were misleading and what you would weight
differently in future evaluations for this account type.

Return JSON: { "updated_score": int, "false_positive_signals": [], "learning": "..." }
```

---

## 16. Environment Variables Reference

Complete `.env.example` — copy to `.env` and fill in all values:

```bash
# ── MongoDB Atlas ──────────────────────────────────────
# Get from: Atlas → Connect → Drivers → Connection String
MONGODB_URI=mongodb+srv://<username>:<password>@<cluster>.mongodb.net/?retryWrites=true&w=majority
MONGODB_DATABASE=fraudshield

# ── Google Cloud / Gemini ──────────────────────────────
# Project ID: GCP Console → Project selector → Project ID
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
# API Key: GCP Console → APIs & Services → Credentials → Create API Key
GEMINI_API_KEY=AIza...

# ── SMS Alerts ────────────────────────────────────────
# Generic SMS function in agent/actions.py — logs to console by default.
# Plug in your own SMS provider (Twilio, Vonage, Africa's Talking, etc.)
# No env vars required — edit the send_sms() function directly.

# ── PaySim Data ────────────────────────────────────────
# Full path to the downloaded PaySim CSV file
PAYSIM_CSV_PATH=./data/PS_20174392719_1491204439457_log.csv

# ── Agent Thresholds ───────────────────────────────────
RISK_BLOCK_THRESHOLD=61
RISK_FLAG_THRESHOLD=31
BATCH_SIZE=10000
```

---

## 17. Troubleshooting Guide

### MongoDB Issues

**Problem:** `ServerSelectionTimeoutError` when connecting
**Solution:** In Atlas → Network Access → verify 0.0.0.0/0 is in the IP whitelist. Also verify the password in the URI has no special characters that need URL encoding (use %40 for @, %23 for #).

**Problem:** Aggregation queries taking over 2 seconds
**Solution:** Check indexes exist in Atlas UI → Collections → Indexes tab. If missing, run:

```javascript
db.transactions.createIndex({ nameOrig: 1, step: -1 });
db.transactions.createIndex({ type: 1, isFraud: 1 });
db.transactions.createIndex({ amount: -1 });
```

**Problem:** `load_paysim.py` crashes partway through
**Solution:** The script uses `ordered=False` so it's safe to re-run. Check the count first — if you have 3M documents, start from where you left off by modifying the CSV reader to skip already-loaded rows, or just drop and restart.

**Problem:** `expectedNewBalanceOrg` field missing on older documents
**Solution:** Run this update on the collection to backfill:

```javascript
db.transactions.updateMany({ expectedNewBalanceOrg: { $exists: false } }, [
	{
		$set: {
			expectedNewBalanceOrg: { $subtract: ["$oldbalanceOrg", "$amount"] },
		},
	},
]);
```

### Gemini Issues

**Problem:** Gemini returns plain text instead of JSON
**Solution:** The retry wrapper in `gemini_client.py` handles this. If it persists after 3 retries, check if the prompt ends with the JSON format instruction. Also verify you're using `gemini-2.5-flash` not an older model.

**Problem:** Gemini API quota exceeded
**Solution:** Apply for increased quota at: GCP Console → Vertex AI → Generative AI → Quotas. Free tier allows ~60 requests/minute. Add `time.sleep(1)` between evaluations in the replay engine if hitting limits.

**Problem:** `google.api_core.exceptions.InvalidArgument`
**Solution:** The prompt may be too long. Trim the history_24h to the last 10 transactions maximum when building the context dict.

### MCP Issues

**Problem:** `MCP server not found` or `npx command not found`
**Solution:** Verify Node.js is installed: `node --version`. Install the MCP server globally: `npm install -g @mongodb-js/mongodb-mcp-server`. Verify: `npx @mongodb-js/mongodb-mcp-server --version`.

**Problem:** MCP returns empty results for valid queries
**Solution:** Verify `MDB_MCP_CONNECTION_STRING` is set in the MCP server's env (not your Python env). Check the database name is exactly `fraudshield` (case-sensitive).

### Frontend / API Issues

**Problem:** CORS errors in browser console
**Solution:** Backend already has `allow_origins=["*"]` in FastAPI CORS middleware. Ensure backend is running on port 8000 and Vite proxy is configured in `vite.config.ts`.

**Problem:** WebSocket replay not connecting
**Solution:** Ensure `websockets` is installed (`pip install websockets`). Restart uvicorn. Check that the Vite proxy has `ws: true` for the `/ws` path.

**Problem:** Cloud Run container crashes on startup
**Solution:** Check Cloud Run logs in GCP Console. Most common cause is a missing environment variable. Verify all env vars are set in the `gcloud run deploy` command.

### Cloud Run Issues

**Problem:** Slow response / cold start
**Solution:** Use `--min-instances 1` in the deploy command. This keeps one container always warm.

**Problem:** Container build fails
**Solution:** Ensure the Dockerfile copies all necessary files. Run `docker build -t test .` locally first to verify the build succeeds before pushing to GCP.

---

## 18. Submission Checklist

Complete every item before June 11 @ 11:00 PM EAT.

### Code & Repository

- [ ] GitHub repository is public
- [ ] MIT LICENSE file is at the root and visible in the About section
- [ ] README.md is complete with setup instructions
- [ ] `.env.example` is committed (not `.env`)
- [ ] All source files committed: agent/, api/, frontend/src/, data/, config/, queries/
- [ ] `.gitignore` excludes `.env`, CSV files, and `__pycache__`

### Functionality

- [ ] 6.3M PaySim transactions loaded in MongoDB Atlas
- [ ] All 5 MCP tools working: find, aggregate, insert_one, update_one, count
- [ ] Agent completes 7-step evaluation end-to-end
- [ ] Risk score returned for every transaction
- [ ] Block action logs alert to MongoDB
- [ ] SMS alert fires on block (even if using sandbox number)
- [ ] React dashboard shows live metrics, replay, and agent trace
- [ ] Manual transaction input on dashboard works

### Deployment

- [ ] Docker container builds successfully
- [ ] App runs locally via docker-compose
- [ ] Deployed to Google Cloud Run with public HTTPS URL
- [ ] Cloud Run has min-instances=1 (no cold starts)
- [ ] All environment variables set as Cloud Run secrets/env vars
- [ ] Public URL loads the React dashboard without errors

### Demo Video

- [ ] Video is 3 minutes or under
- [ ] Video shows: data load → query → live agent evaluation → block → SMS → dashboard
- [ ] Video is uploaded and link is accessible (YouTube unlisted or Loom)
- [ ] Audio is clear

### Devpost Submission

- [ ] Project name: FraudShield Agent
- [ ] Project story complete (all 6 sections)
- [ ] Hosted URL added
- [ ] GitHub URL added
- [ ] Demo video URL added
- [ ] MongoDB track selected
- [ ] All technologies tagged
- [ ] Team member: Batte Akhsam / Axoblade
- [ ] Submitted before June 11 @ 11:00 PM EAT

---

_Built by Axoblade — https://axoblade.com_
_Developer: Batte Akhsam — linkedin.com/in/batteakhsam — github.com/axoblade_
_FraudShield Agent: AI that doesn't just detect fraud — it stops it._
