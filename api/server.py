# ── Suppress OpenTelemetry noise from ADK (must be before all imports) ──
import os as _os
_os.environ.setdefault("OTEL_PYTHON_DISABLED", "1")
_os.environ.setdefault("GRPC_VERBOSITY", "ERROR")
_os.environ.setdefault("GRPC_TRACE", "none")

"""
api/server.py - FraudShield FastAPI Backend
REST + WebSocket API for the React dashboard.

Endpoints:
  POST /api/login          - dummy auth (admin/admin)
  POST /api/evaluate       - run the fraud detection agent
  GET  /api/metrics        - live MongoDB counts
  WS   /ws/replay          - stream transactions from DB in real time

Usage:
    uvicorn api.server:app --reload --port 8000
"""

import asyncio
import json
import os
import sys
import time
from typing import Any, Dict, List

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger
from pydantic import BaseModel, Field

# ── Path setup ────────────────────────────────────────────────────
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from agent.actions import ActionExecutor
from agent.adk_agent import FraudShieldADKAgent
from agent.mongo_mcp import MongoDBMCPClient


def _to_plain(obj: Any) -> Any:
    """Strip protobuf types from Gemini function-call responses.

    Gemini returns RepeatedComposite for lists and other proto wrappers
    that the MCP SDK can't serialise.  Round-tripping through JSON
    converts everything to plain Python types.
    """
    return json.loads(json.dumps(obj, default=str))

load_dotenv()

# ── App ───────────────────────────────────────────────────────────
app = FastAPI(title="FraudShield Agent API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Dummy auth ────────────────────────────────────────────────────
DUMMY_CREDENTIALS = {"admin": "admin"}
VALID_TOKENS: set[str] = set()


def _verify_token(token: str) -> bool:
    return token in VALID_TOKENS


# ── Models ────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class TransactionRequest(BaseModel):
    step: int = Field(..., ge=1, le=744, description="Time step (1-744)")
    type: str = Field(..., pattern=r"^(CASH_OUT|TRANSFER|PAYMENT|CASH_IN|DEBIT)$")
    amount: float = Field(..., gt=0, description="Transaction amount (> 0)")
    nameOrig: str = Field(..., min_length=1, description="Origin account ID")
    nameDest: str = Field(..., min_length=1, description="Destination account ID")
    oldbalanceOrg: float = Field(..., ge=0, description="Origin balance before txn")
    newbalanceOrig: float | None = None


class EvaluateResponse(BaseModel):
    risk_score: int
    risk_level: str
    action: str
    reasoning: str
    key_signals: List[str]
    elapsed_ms: float
    alert_id: str = ""
    sms_sent: bool = False
    trace: List[Dict[str, Any]] = []  # turn-by-turn agent reasoning


class MetricsResponse(BaseModel):
    total_transactions: int
    fraud_count: int
    alerts_count: int


# ── Clients (lazy init) ───────────────────────────────────────────

_mcp: MongoDBMCPClient | None = None
_agent: FraudShieldADKAgent | None = None
_executor: ActionExecutor | None = None


def _get_clients():
    global _mcp, _agent, _executor
    if _mcp is None:
        _mcp = MongoDBMCPClient()
        _agent = FraudShieldADKAgent(mcp=_mcp)
        _executor = ActionExecutor(_mcp)
    return _mcp, _agent, _executor


# ── REST endpoints ────────────────────────────────────────────────


@app.post("/api/login")
def login(body: LoginRequest):
    if (
        body.username in DUMMY_CREDENTIALS
        and body.password == DUMMY_CREDENTIALS[body.username]
    ):
        token = f"tok_{os.urandom(16).hex()}"
        VALID_TOKENS.add(token)
        return {"token": token, "username": body.username}
    raise HTTPException(status_code=401, detail="Invalid credentials")


@app.post("/api/evaluate", response_model=EvaluateResponse)
async def evaluate(txn: TransactionRequest):
    mcp, agent, executor = _get_clients()

    t0 = time.time()
    txn_dict = txn.model_dump()
    if txn_dict["newbalanceOrig"] is None:
        txn_dict["newbalanceOrig"] = txn_dict["oldbalanceOrg"] - txn_dict["amount"]

    decision, trace = await agent.evaluate(txn_dict)
    decision = _to_plain(decision)  # strip protobuf types
    trace = _to_plain(trace)        # strip protobuf types from trace
    action_result = await executor.execute(txn_dict, decision)
    elapsed = (time.time() - t0) * 1000

    return EvaluateResponse(
        risk_score=decision["risk_score"],
        risk_level=decision.get("risk_level", "unknown"),
        action=decision.get("action", "unknown"),
        reasoning=decision.get("reasoning", ""),
        key_signals=decision.get("key_signals", []),
        elapsed_ms=round(elapsed),
        alert_id=action_result.get("alert_id", ""),
        sms_sent=action_result.get("sms_sent", False),
        trace=trace,
    )


@app.get("/api/metrics", response_model=MetricsResponse)
async def metrics():
    mcp, _, _ = _get_clients()
    try:
        total = await mcp.count("transactions", {})
        fraud = await mcp.count("transactions", {"isFraud": 1})
        alerts = await mcp.count("alerts", {})
    except Exception:
        total = fraud = alerts = 0
    return MetricsResponse(
        total_transactions=total,
        fraud_count=fraud,
        alerts_count=alerts,
    )


# ── WebSocket: live metrics stream ────────────────────────────────


@app.websocket("/ws/metrics")
async def ws_metrics(ws: WebSocket):
    """Push live MongoDB counts every 5 seconds."""
    await ws.accept()
    # Fresh MCP client per connection - avoids anyio task conflicts
    mcp = MongoDBMCPClient()

    try:
        while True:
            try:
                total = await mcp.count("transactions", {})
                fraud = await mcp.count("transactions", {"isFraud": 1})
                alerts = await mcp.count("alerts", {})
            except Exception:
                total = fraud = alerts = 0

            await ws.send_json({
                "type": "metrics",
                "total_transactions": total,
                "fraud_count": fraud,
                "alerts_count": alerts,
            })
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        pass


# ── WebSocket: replay engine ──────────────────────────────────────


@app.websocket("/ws/replay")
async def ws_replay(ws: WebSocket):
    await ws.accept()
    mcp, agent, executor = _get_clients()

    try:
        while True:
            # Wait for control message from client
            msg = await ws.receive_json()
            action = msg.get("action")

            if action == "start":
                limit = min(msg.get("limit", 200), 1000)
                speed = max(msg.get("speed", 1.0), 0.1)

                await ws.send_json({
                    "type": "replay_start",
                    "total": limit,
                })

                for i in range(limit):
                    # Fetch one random transaction at a time — true streaming
                    batch = await mcp.aggregate("transactions", [
                        {"$sample": {"size": 1}},
                    ])
                    if not batch:
                        break
                    txn = batch[0]

                    try:
                        decision, trace = await agent.evaluate(txn)
                        decision = _to_plain(decision)
                        trace = _to_plain(trace)
                        action_result = await executor.execute(txn, decision)

                        await ws.send_json({
                            "type": "transaction_result",
                            "index": i + 1,
                            "total": limit,
                            "transaction": {
                                "step": txn.get("step"),
                                "type": txn.get("type"),
                                "amount": txn.get("amount"),
                                "nameOrig": txn.get("nameOrig"),
                                "nameDest": txn.get("nameDest"),
                            },
                            "risk_score": decision["risk_score"],
                            "risk_level": decision.get("risk_level"),
                            "action": decision.get("action"),
                            "reasoning": decision.get("reasoning"),
                            "key_signals": decision.get("key_signals") or [],
                            "elapsed_ms": 0,
                            "alert_id": action_result.get("alert_id", ""),
                            "trace": trace,
                        })
                    except Exception as exc:
                        await ws.send_json({
                            "type": "error",
                            "index": i + 1,
                            "error": str(exc),
                        })

                    await asyncio.sleep(0.5 / speed)

                await ws.send_json({"type": "replay_complete", "total": limit})

            elif action == "stop":
                await ws.send_json({"type": "replay_stopped"})
                break

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as exc:
        logger.error(f"WebSocket error: {exc}")
        try:
            await ws.send_json({"type": "error", "error": str(exc)})
        except Exception:
            pass


# ── Health check ──────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok"}


# ── Serve React SPA in production ─────────────────────────────────
# In local dev Vite handles the frontend; in Docker / Cloud Run the
# built assets live at frontend/dist/ and FastAPI serves them directly.
_frontend_dist = os.path.join(_project_root, "frontend", "dist")
if os.path.isdir(_frontend_dist):
    app.mount("/", StaticFiles(directory=_frontend_dist, html=True), name="frontend")
