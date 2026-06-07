"""
mongo_mcp.py - Day 2 MongoDB MCP Client
Python wrapper around mongodb-mcp-server via the MCP Python SDK.

Exposes 5 async methods the agent uses at runtime:
  find, aggregate, insert_one, update_one, count

Usage:
    from agent.mongo_mcp import MongoDBMCPClient

    async with MongoDBMCPClient() as mcp:
        results = await mcp.find("transactions", {"isFraud": 1}, limit=10)
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import re
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from loguru import logger

# ── MCP SDK imports ──────────────────────────────────────────────
try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
except ImportError:
    raise ImportError(
        "The 'mcp' package is required.  "
        "Install it with:  pip install mcp>=1.0.0"
    )

load_dotenv()


# ── Custom exception ──────────────────────────────────────────────
class MCPConnectionError(Exception):
    """Raised when any MCP tool call fails (connection, timeout, auth, etc.)."""


# ── Client ────────────────────────────────────────────────────────
class MongoDBMCPClient:
    """Async wrapper around the MongoDB MCP server (stdio transport).

    Maintains a persistent session - one subprocess, reused across calls.
    The subprocess is lazily started on first use and kept alive.
    """

    DATABASE = "fraudshield"

    def __init__(self, connection_string: Optional[str] = None) -> None:
        self._uri = connection_string or os.getenv("MONGODB_URI", "")
        if not self._uri:
            raise MCPConnectionError("MONGODB_URI is not set.")
        self._session: Optional[ClientSession] = None
        self._read = None
        self._write = None
        self._stdio_ctx = None
        self._session_ctx = None

    async def __aenter__(self) -> "MongoDBMCPClient":
        await self._ensure_connected()
        return self

    async def __aexit__(self, *args: Any) -> None:
        # Silent cleanup - process exit handles EPIPE
        self._session = None
        self._session_ctx = None
        self._read = None
        self._write = None
        self._stdio_ctx = None

    async def _ensure_connected(self) -> ClientSession:
        if self._session is not None:
            return self._session
        params = StdioServerParameters(
            command="npx",
            args=["-y", "mongodb-mcp-server"],
            env={
                "MDB_MCP_CONNECTION_STRING": self._uri,
                "NODE_NO_WARNINGS": "1",
                "GRPC_VERBOSITY": "ERROR",
                "GRPC_TRACE": "none",
            },
        )
        self._stdio_ctx = stdio_client(params)
        self._read, self._write = await self._stdio_ctx.__aenter__()
        self._session_ctx = ClientSession(self._read, self._write)
        self._session = await self._session_ctx.__aenter__()
        await self._session.initialize()
        return self._session

    async def _call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> list:
        """Call an MCP tool against the persistent session.

        If the session dies (EPIPE, BrokenResourceError), recreates it
        and retries once transparently.
        """
        last_exc = None
        for attempt in (1, 2):
            try:
                session = await self._ensure_connected()
                result = await session.call_tool(tool_name, arguments=arguments)
                if result.isError:
                    error_text = result.content[0].text if result.content else "unknown"
                    raise MCPConnectionError(f"MCP tool '{tool_name}' error: {error_text}")
                return list(result.content) if result.content else []
            except Exception as exc:
                last_exc = exc
                if attempt == 1:
                    logger.warning(f"MCP call '{tool_name}' failed, reconnecting: {exc}")
                    self._session = None
                    self._session_ctx = None
                    try:
                        if self._stdio_ctx:
                            await self._stdio_ctx.__aexit__(None, None, None)
                    except Exception:
                        pass
                    self._stdio_ctx = None
                    self._read = None
                    self._write = None
                    continue
                logger.error(f"MCP tool '{tool_name}' failed after retry: {exc}")
        raise MCPConnectionError(f"MCP call to '{tool_name}' failed: {last_exc}") from last_exc

    # ── Internal helpers ─────────────────────────────────────────

    @staticmethod
    def _parse_extended_json(obj: Any) -> Any:
        """Recursively convert MongoDB Extended JSON to plain Python types.

        ``{"$oid": "..."}`` → ``"..."``
        ``{"$numberDouble": "123.45"}`` → ``123.45``
        ``{"$numberInt": "42"}`` → ``42``
        """
        if isinstance(obj, dict):
            if "$oid" in obj and len(obj) == 1:
                return obj["$oid"]
            if "$numberDouble" in obj and len(obj) == 1:
                return float(obj["$numberDouble"])
            if "$numberInt" in obj and len(obj) == 1:
                return int(obj["$numberInt"])
            if "$numberLong" in obj and len(obj) == 1:
                return int(obj["$numberLong"])
            return {k: MongoDBMCPClient._parse_extended_json(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [MongoDBMCPClient._parse_extended_json(i) for i in obj]
        return obj

    @staticmethod
    def _extract_json_from_response(content_items: list) -> Optional[str]:
        """Pull JSON payload from between <untrusted-user-data-…> tags.

        The warning text itself mentions the tags, so we look for the block
        that contains actual JSON (starts with ``[`` or ``{``).
        """
        for item in content_items:
            if not hasattr(item, "text") or not item.text:
                continue
            # Find all untrusted-user-data blocks - the last one has the data
            matches = list(
                re.finditer(
                    r"<untrusted-user-data-[^>]+>\s*(.*?)\s*</untrusted-user-data-[^>]+>",
                    item.text,
                    re.DOTALL,
                )
            )
            for match in reversed(matches):  # last match = actual data
                candidate = match.group(1).strip()
                if candidate.startswith("[") or candidate.startswith("{"):
                    return candidate
        return None

    @staticmethod
    def _parse_count_response(content_items: list) -> Optional[int]:
        """Parse a human-readable count summary like
        'Found 8213 documents in the collection ...'."""
        for item in content_items:
            if not hasattr(item, "text") or not item.text:
                continue
            m = re.search(r"Found (\d+) document", item.text)
            if m:
                return int(m.group(1))
        return None

    @staticmethod
    def _parse_insert_response(content_items: list) -> Optional[str]:
        """Extract inserted ID from an insert-many human-readable response.

        Format: ``Inserted IDs: 6a21e63ddfed960dc8383091``
        """
        for item in content_items:
            if not hasattr(item, "text") or not item.text:
                continue
            # Try "Inserted IDs: <hex>" pattern (most reliable)
            m = re.search(r"Inserted IDs?:\s*([a-f0-9]{24})", item.text)
            if m:
                return m.group(1)
            # Fallback: any 24-char hex ObjectId
            m = re.search(r'"\$oid"\s*:\s*"([a-f0-9]{24})"', item.text)
            if m:
                return m.group(1)
        return ""

    @staticmethod
    def _parse_update_response(content_items: list) -> Dict[str, int]:
        """Parse update-many human-readable response for matched/modified counts."""
        result = {"matchedCount": 0, "modifiedCount": 0}
        for item in content_items:
            if not hasattr(item, "text") or not item.text:
                continue
            m = re.search(r"Matched (\d+)", item.text)
            if m:
                result["matchedCount"] = int(m.group(1))
            m = re.search(r"Modified (\d+)", item.text)
            if m:
                result["modifiedCount"] = int(m.group(1))
        return result

    def _make_safe(self, value: Any) -> Any:
        """Convert MongoDB-specific types to JSON-safe Python primitives."""
        if isinstance(value, dict):
            return {k: self._make_safe(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._make_safe(i) for i in value]
        if hasattr(value, "item"):
            return value.item()
        return value

    # ── Public API (5 tools) ─────────────────────────────────────

    async def find(
        self, collection: str, query: Dict[str, Any], limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Query documents from a collection.

        Returns
        -------
        list[dict]
            Matching documents with Extended JSON types normalised.
        """
        logger.debug(f"find | {collection} | {query} | limit={limit}")
        content = await self._call_tool(
            "find",
            {
                "database": self.DATABASE,
                "collection": collection,
                "filter": query,
                "limit": limit,
            },
        )
        json_str = self._extract_json_from_response(content)
        if json_str:
            try:
                docs = json.loads(json_str)
                return [self._make_safe(self._parse_extended_json(d)) for d in docs]
            except json.JSONDecodeError:
                logger.warning(f"find: could not parse JSON from response")
        return []

    async def aggregate(
        self, collection: str, pipeline: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Run an aggregation pipeline."""
        logger.debug(f"aggregate | {collection} | {len(pipeline)} stages")
        content = await self._call_tool(
            "aggregate",
            {
                "database": self.DATABASE,
                "collection": collection,
                "pipeline": pipeline,
            },
        )
        json_str = self._extract_json_from_response(content)
        if json_str:
            try:
                docs = json.loads(json_str)
                return [self._make_safe(self._parse_extended_json(d)) for d in docs]
            except json.JSONDecodeError:
                logger.warning("aggregate: could not parse JSON from response")
        return []

    async def insert_one(self, collection: str, document: Dict[str, Any]) -> str:
        """Insert a single document (wraps it in an array for insert-many)."""
        logger.debug(f"insert_one | {collection}")
        content = await self._call_tool(
            "insert-many",
            {
                "database": self.DATABASE,
                "collection": collection,
                "documents": [document],
            },
        )
        inserted_id = self._parse_insert_response(content)
        logger.debug(f"insert_one → {inserted_id}")
        return inserted_id

    async def update_one(
        self, collection: str, filter_q: Dict[str, Any], update: Dict[str, Any]
    ) -> Dict[str, int]:
        """Update documents matching *filter_q* via update-many."""
        logger.debug(f"update_one | {collection} | {filter_q}")
        content = await self._call_tool(
            "update-many",
            {
                "database": self.DATABASE,
                "collection": collection,
                "filter": filter_q,
                "update": update,
            },
        )
        return self._parse_update_response(content)

    async def count(
        self, collection: str, query: Optional[Dict[str, Any]] = None
    ) -> int:
        """Count documents matching a query."""
        query = query or {}
        logger.debug(f"count | {collection} | {query}")
        content = await self._call_tool(
            "count",
            {
                "database": self.DATABASE,
                "collection": collection,
                "query": query,
            },
        )
        parsed = self._parse_count_response(content)
        return parsed if parsed is not None else 0
