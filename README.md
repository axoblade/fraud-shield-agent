# FraudShield Agent

### AI-Powered Real-Time Fraud Detection Using Gemini + MongoDB MCP + PaySim Data

> _"Every minute, over $1,500 is lost to mobile money fraud across Sub-Saharan Africa. Traditional systems catch it after the money is gone. FraudShield Agent stops it before it ever leaves the account."_

## [![Launch App](https://img.shields.io/badge/🚀%20Launch%20App-fraudshield-2563eb?style=for-the-badge)](https://fraud-shield-agent-612621242021.europe-west1.run.app)

[![How It Works](https://img.shields.io/badge/▶️%20How%20It%20Works-Video-262626?style=for-the-badge)](https://youtube.com/your-video)

### All Tools & Products Used

| Category           | Tools                                                                                             |
| ------------------ | ------------------------------------------------------------------------------------------------- |
| **Google Cloud**   | Gemini 2.5 Flash, Cloud Run                                                                       |
| **MongoDB**        | MongoDB Atlas (M20), MongoDB MCP Server                                                           |
| **Backend**        | Python 3.12, FastAPI, Uvicorn, WebSocket                                                          |
| **Frontend**       | React 19, TypeScript, Vite, CSS Custom Properties                                                 |
| **AI / ML**        | Google ADK (Agent Development Kit), Gemini 2.5 Flash, Function Calling, Heuristic Fallback Engine |
| **Data**           | PaySim Dataset (6.36M transactions), Pandas, Chunked CSV Loading                                  |
| **Infrastructure** | Docker (multi-stage), pnpm, Google Cloud Build                                                    |
| **Libraries**      | Pydantic, Loguru, python-dotenv, MCP Python SDK v1.27.2                                           |

### Google Cloud Products Used

| Product                   | How We Use It                                                                                                                                                                                                                                                             |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Gemini 2.5 Flash**      | Multi-turn reasoning engine; the agent's brain. Gemini receives 7 registered tools, decides which to call based on transaction context, analyses results, and submits a final risk decision. All via function calling through the **Google Agent Development Kit (ADK)**. |
| **Cloud Run**             | Serverless hosting for the FastAPI backend + React frontend. Single Docker container, auto-scaling, HTTPS by default. Deployed at [fraud-shield-agent-612621242021.europe-west1.run.app](https://fraud-shield-agent-612621242021.europe-west1.run.app).                   |
| **Agent Development Kit** | Code-first agent framework. We use ADK's `Agent`, `Runner`, and `FunctionTool` to orchestrate the multi-turn investigation compliant with the hackathon's required code-first path within the Google Cloud Agent Builder ecosystem.                                       |

---

## Inspiration

The idea for FraudShield Agent was born from a frustrating reality we kept encountering: mobile money is the financial backbone of hundreds of millions of people across Africa, yet the fraud detection systems protecting these accounts are stuck in the past.

We had seen firsthand how rule-based fraud systems work; or rather, how they fail. They are brittle. They generate enormous numbers of false positives, freezing legitimate transactions for ordinary people who depend on mobile money for rent, groceries, and school fees. And when real fraud does slip through, it is almost always detected _after_ the money has already moved, sometimes days later.

The question that kept nagging us was simple: **Why is there no system that reasons about fraud the way a skilled human investigator would?**

A human investigator wouldn't just check if a single transaction exceeds a threshold. They would ask: _How does this transaction compare to the user's history? Is this account suddenly withdrawing 10× its usual amount? Has the destination account been flagged before? Does the timing suggest a coordinated attack?_

That multi-step, context-aware reasoning is exactly what large language models like Gemini are built for. When the Google Cloud Rapid Agent Hackathon presented the opportunity to build an agent that goes beyond chat; one that **reasons, plans, and acts**; we knew this was the project we had to build.

FraudShield Agent is our answer: an autonomous AI agent that thinks like a fraud investigator and acts with the speed of a computer.

---

## What It Does

FraudShield Agent is a **multi-turn autonomous agent** that investigates mobile money transactions in real time. Unlike a rules engine or a classification API, the agent **decides which tools to call** and **how deep to investigate** based on what it finds.

```
Transaction arrives
       │
       ▼
┌─────────────────────────────────────────┐
│  Gemini 2.5 Flash receives transaction   │
│  + 7 registered investigation tools      │
│                                          │
│  Turn 1: _tool_history (always)              │
│  Turn 2+: Gemini decides — _tool_velocity?   │
│           _tool_mule? _tool_baseline?         │
│           _tool_balance_mismatch?             │
│  Final:  _tool_submit_decision               │
│          → risk score 0–100              │
│          → action: allow / flag / block  │
└──────────────┬──────────────────────────┘
               │  MongoDB MCP Server
               ▼
┌─────────────────────────────────────────┐
│  MongoDB Atlas; 6.36M transactions      │
│  5 MCP tools: find, aggregate,           │
│  insert_one, update_one, count           │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  Action Executor                         │
│  Risk 0–30  → ALLOW                     │
│  Risk 31–60 → FLAG (insert alert)       │
│  Risk 61–100→ BLOCK (alert + SMS)       │
└─────────────────────────────────────────┘
```

A $50 PAYMENT to a known account gets a single history check. A $500K CASH_OUT to a new recipient triggers full velocity, mule, baseline, and balance investigation; up to 6 turns. The agent **chooses** how deep to go.

Every decision is transparent: per-tool reasoning from Gemini, a heuristic baseline for comparison, and auto-generated signal tags are all visible in the dashboard.

---

## How We Built It

### The Stack

| Layer       | Technology                                              | Role                                                            |
| ----------- | ------------------------------------------------------- | --------------------------------------------------------------- |
| Agent Brain | Google Gemini 2.5 Flash via ADK (Agent Development Kit) | Multi-turn reasoning and dynamic tool selection                 |
| Database    | MongoDB Atlas (M20)                                     | Stores 6.36M transactions, alerts, risk scores                  |
| Integration | MongoDB MCP Server via npx                              | Gives Gemini 5 tools to query and write data                    |
| Dataset     | PaySim Synthetic Mobile Money Dataset                   | 6.36M labeled transactions, 30 days of activity                 |
| Backend     | FastAPI + Uvicorn + WebSocket                           | REST API, live metrics streaming, replay engine                 |
| Frontend    | React 19 + TypeScript + Vite                            | Professional dashboard with agent trace visualization           |
| Alerts      | Generic SMS provider (pluggable)                        | Console logger by default; Twilio/Vonage/Africa's Talking ready |
| Deployment  | Docker + Google Cloud Run                               | Multi-stage container build, single-command deploy              |

### Phase 1; The Data Foundation

We started by loading the **PaySim dataset** into MongoDB Atlas. PaySim is a synthetic mobile money dataset based on real aggregated financial logs from an African mobile money operator, covering 30 days of activity across 6.36 million transactions.

The dataset's class imbalance is striking and realistic:

$$P(\text{fraud}) = \frac{8{,}213}{6{,}362{,}620} \approx 0.0013 = 0.13\%$$

This means 99.87% of transactions are completely legitimate. Any naive model that simply predicts "not fraud" for every transaction achieves 99.87% accuracy; and catches exactly zero fraudulent transactions. This is the **accuracy paradox**, and it's why rule-based thresholds fail.

To prepare MongoDB Atlas, we created compound indexes to ensure the aggregation queries our agent runs stay under 200ms even across 6.36 million records:

```javascript
db.transactions.createIndex({ nameOrig: 1, step: -1 });
db.transactions.createIndex({ type: 1, isFraud: 1 });
db.transactions.createIndex({ amount: -1 });
db.transactions.createIndex({ nameDest: 1, type: 1 });
db.transactions.createIndex({ step: 1 });
```

### Phase 2; The MongoDB MCP Integration

The MongoDB MCP server is what transforms Gemini from a language model into an **action-taking agent**. We configured it with five core tools that the agent uses autonomously:

- **`find()`**; Fetch a user's transaction history in a rolling 24-hour window
- **`aggregate()`**; Run complex fraud-pattern pipelines (velocity, mule networks, balance mismatches)
- **`insert_one()`**; Log high-risk alerts and agent decisions back to MongoDB
- **`update_one()`**; Update risk scores on user profiles as evidence accumulates
- **`count()`**; Quickly measure transaction volume to detect bursts

The agent doesn't just connect to MongoDB as a data store; it uses MongoDB's aggregation pipeline as its **analytical engine**. For example, detecting a money mule network requires joining two collections and comparing inbound vs. outbound flows, which the agent executes in a single pipeline call:

```javascript
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
	{ $match: { incomingCount: { $gt: 10 }, "outgoing.amount": { $gt: 0 } } },
]);
```

### Phase 3; The Gemini Multi-Turn Reasoning Loop

The agent's investigation is **dynamic**, not a fixed pipeline. Gemini 2.5 Flash receives 7 registered tools and a system prompt priming it as a fraud investigator. For each transaction, the agent:

1. Calls `_tool_history`; always the first step
2. Analyses the result and decides: _velocity? mule? baseline? balance? risk history?_
3. Calls the next tool based on what the evidence demands
4. Repeats up to 6 turns until confident
5. Calls `submit_risk_decision` with a risk score, action, reasoning, and key signals

The risk score is a weighted evaluation that Gemini produces by reasoning over multiple signals simultaneously:

$$
\text{Action} = \begin{cases}
\text{Allow} & \text{if } R \in [0, 30] \\
\text{Flag for Review} & \text{if } R \in [31, 60] \\
\text{Block} & \text{if } R \in [61, 100]
\end{cases}
$$

where $R$ is the risk score output by Gemini's reasoning step. A heuristic baseline runs alongside every Gemini decision for consistency and provides signal tags when Gemini omits them.

### Phase 4; The Dashboard & Alerts

We built a **React + TypeScript dashboard** connected via **FastAPI + WebSocket** that shows the agent's decisions in real time:

- **Live metrics**; Transaction volume, fraud blocked, alerts count updated every 5 seconds
- **Manual evaluation**; Submit any transaction through a fly-out modal and watch the agent investigate turn-by-turn
- **Replay engine** — Stream transactions at configurable speed (1×–20×). Each transaction is fetched one at a time via MongoDB `$sample` for true random sampling — no pre-fetch, no bias.
- **Agent trace**; Every tool call rendered with Gemini's reasoning, per-step analysis, heuristic baseline, and investigation summary
- **Verbose log**; Terminal-style live log of every WebSocket event

When a transaction is blocked, an alert is logged to MongoDB and an SMS can be sent through any provider (Twilio, Vonage, Africa's Talking; pluggable by design).

---

## What We Learned

### 1. MongoDB MCP is not just a connector; it's a reasoning partner

Before this project, we thought of MCP as a bridge: a way to let an LLM read from a database. What we discovered is that MongoDB's aggregation framework, when accessed via MCP, becomes part of the agent's _cognitive loop_. The agent doesn't retrieve raw data and do analysis in Python; it _delegates_ the analysis to MongoDB's pipeline engine, then reasons over the aggregated result. This division of labour is far more efficient and scalable.

### 2. The accuracy paradox demands precision-recall framing

Because only 0.13% of transactions are fraudulent, we had to completely abandon accuracy as a meaningful metric. We reframed the agent's performance around **precision** and **recall**:

$$\text{Precision} = \frac{TP}{TP + FP}, \quad \text{Recall} = \frac{TP}{TP + FN}$$

In a fraud detection context, the cost of a false negative (missed fraud) is almost always greater than the cost of a false positive (blocked legitimate transaction). We tuned the risk threshold accordingly, biasing slightly toward higher recall at the cost of some precision.

### 3. Gemini's reasoning is most powerful when given structured context

The quality of Gemini's fraud reasoning improved dramatically when we stopped giving it raw transaction rows and started giving it **pre-aggregated summaries**; e.g. "9 transactions in 20 hours totalling $6,200, versus a historical baseline of 1-2 transactions per week under $500." Structured context enables structured reasoning.

### 4. Real-time detection requires index discipline

Running aggregation pipelines on 6.36 million documents without proper compound indexes produced queries that took 8–12 seconds. After adding the right indexes, the same queries resolved in under 150ms; fast enough for real-time blocking.

### 5. A multi-turn agent outperforms a fixed pipeline

Our initial design used a deterministic 7-step pipeline: always check history, always calculate velocity, always check mule status. We found this wasted time on low-risk transactions. Switching to Gemini function calling; where the agent _chooses_ which tools to call; made the system both faster (quick checks for small payments) and more thorough (deep investigation for suspicious patterns).

---

## Challenges We Faced

### Challenge 1; Loading 6.36 Million Records Efficiently

Naively inserting 6.36 million PaySim rows one document at a time would take hours. We solved this with MongoDB's `insertMany()` in batches of 10,000 documents, using a Python loader with chunked CSV reading. Total load time: approximately 4 minutes.

### Challenge 2; Preventing Gemini Hallucination in Function Calls

Early in development, Gemini occasionally returned malformed function calls or narrative text instead of calling a tool. We solved this by enforcing strict function-calling schemas with typed parameters, adding retry logic with gentle nudging ("You MUST call submit_risk_decision NOW"), and implementing a heuristic fallback that computes a risk score from available trace data when Gemini fails to decide within 6 turns.

### Challenge 3; Handling the Imbalanced Dataset in Validation

With only 0.13% fraud, random sampling for evaluation would almost never include a fraudulent transaction. We built a replay engine that interleaves fraudulent and legitimate transactions chronologically, giving the agent a realistic but evaluable test stream where fraud appears at its natural frequency.

### Challenge 4; Simulating Real-Time Without a Live Stream

The PaySim dataset is historical, not streaming. To simulate real-time detection for the demo, we built a **WebSocket replay engine** that feeds transactions to the agent in chronological order at configurable speed; fast enough to demonstrate the agent blocking fraud, slow enough to show the reasoning steps on screen.

### Challenge 5; Protobuf Serialization in the API Layer

Gemini function-call responses contain protobuf `RepeatedComposite` objects that Python's JSON serializer and Pydantic cannot handle. We built a recursive sanitizer (`_to_plain`) that strips protobuf types from every response before it reaches the frontend, applied consistently across both REST and WebSocket endpoints.

---

## What FraudShield Agent Does That Rules Cannot

Traditional fraud systems apply static thresholds: "block if amount > $10,000." FraudShield Agent applies _contextual_ intelligence. The same $1,000 transaction might be perfectly normal for one user and deeply suspicious for another. FraudShield knows the difference because it has access to the user's full history via MongoDB MCP.

The agent's detection coverage spans four major fraud patterns:

| Pattern                | Detection Method                               | MCP Tool Used |
| ---------------------- | ---------------------------------------------- | ------------- |
| Rapid Cash-Out         | Velocity aggregation over 24h window           | `aggregate()` |
| Money Mule Network     | Inbound/outbound flow comparison via `$lookup` | `aggregate()` |
| Balance Mismatch Fraud | `expectedBalance = oldBalance − amount` check  | `find()`      |
| High-Velocity Transfer | Per-hour transaction count anomaly detection   | `aggregate()` |

---

## Impact

Mobile money is not a convenience for most of its users in Sub-Saharan Africa; it is their primary financial infrastructure. An account drain doesn't just mean a bad week; it can mean a family can't pay school fees, a small business can't make payroll, or a household can't buy food.

FraudShield Agent is designed with this reality in mind. By blocking fraud **before money leaves the account**, it protects users who have no safety net and no fraud insurance; people for whom a single successful attack could be financially catastrophic.

The same architecture is immediately replicable for any mobile money operator in the region, using MongoDB Atlas and Google Cloud Run, keeping the infrastructure costs accessible even for smaller operators.

---

## What's Next

- **MongoDB Change Streams** for millisecond-latency detection on live transaction feeds
- **`$graphLookup`** to map and visualize entire money mule networks
- **Federated learning** so multiple operators can share fraud signal patterns without sharing raw customer data
- **User feedback loop** so false positives are reported, logged via `insert_one()`, and used to continuously improve the agent's reasoning prompts

---

## Quick Start

```bash
git clone https://github.com/axoblade/fraud-shield-agent.git && cd fraud-shield-agent

# Backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # Fill in GEMINI_API_KEY + MONGODB_URI

# Frontend
cd frontend && pnpm install && cd ..

# Run
uvicorn api.server:app --reload --port 8000   # Terminal 1
cd frontend && pnpm dev                        # Terminal 2
```

Open **http://localhost:5173**.

### Docker

```bash
docker build -t fraudshield-agent .
docker run -p 8000:8000 --env-file .env fraudshield-agent
# Open http://localhost:8000
```

---

## Repository Structure

```
fraud-shield-agent/
├── agent/
│   ├── adk_agent.py            # ADK-based multi-turn agent (primary)
│   ├── mongo_mcp.py           # Persistent MCP client with auto-reconnect
│   ├── gemini_client.py       # Single-shot Gemini wrapper + heuristic fallback
│   └── actions.py             # Block / flag / allow executor
│
├── api/
│   └── server.py              # FastAPI: REST + WebSocket endpoints
│
├── frontend/                  # React 19 + TypeScript + Vite
│   └── src/
│       ├── App.tsx            # Login gate
│       ├── App.css            # Professional light theme
│       ├── pages/
│       │   ├── Landing.tsx    # Product pitch + case study
│       │   ├── Login.tsx      # admin/admin auth
│       │   └── Dashboard.tsx  # Metrics + replay + modal
│       └── components/
│           ├── Navbar.tsx
│           ├── MetricsBar.tsx
│           ├── TransactionForm.tsx
│           ├── ResultCard.tsx
│           └── ReplayPanel.tsx
│
├── data/
│   ├── load_paysim.py         # CSV → MongoDB chunked loader
│   └── verify_indexes.py      # Post-load index verification
│
├── queries/                   # MongoDB aggregation pipelines
│   ├── rapid_cashout.js
│   ├── mule_network.js
│   ├── balance_mismatch.js
│   └── velocity_check.js
│
├── Dockerfile
├── .dockerignore
├── requirements.txt
├── .env.example
└── README.md
```

---

## Built With

`Google Gemini 2.5 Flash` · `Google ADK` · `Google Cloud Run` · `MongoDB Atlas` · `MongoDB MCP Server` · `FastAPI` · `React 19` · `TypeScript` · `Vite` · `WebSocket` · `Docker` · `PaySim Dataset` · `Python 3.12`

---

## Team

FraudShield Agent was designed and built by **Axoblade**, a solutions architect crafting intelligent, high-impact digital products.

This project was built for the **Google Cloud Rapid Agent Hackathon**, competing in the **MongoDB Track**.

**Developer & Architect:** Batte Akhsam
**Website:** [axoblade.com](https://axoblade.com)
**LinkedIn:** [linkedin.com/in/batteakhsam](https://linkedin.com/in/batteakhsam)
**GitHub:** [github.com/axoblade](https://github.com/axoblade)

---

_FraudShield Agent; AI that doesn't just detect fraud. It stops it._
