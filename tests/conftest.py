"""Shared pytest fixtures for the touch-mcp test suite."""

from __future__ import annotations

import asyncio
import json
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
import websockets
from websockets.asyncio.server import ServerConnection, serve

from touch_mcp.bridge.connection import TDBridge


# ---------------------------------------------------------------------------
# pytest-asyncio configuration
# ---------------------------------------------------------------------------

pytest_plugins = ("pytest_asyncio",)


# ---------------------------------------------------------------------------
# Mock WebSocket server
# ---------------------------------------------------------------------------

# Error codes mirroring the JSON-RPC convention used by the bridge protocol.
_METHOD_NOT_FOUND = -32601


async def _handle_client(ws: ServerConnection) -> None:
    """Process all messages from a single connected client.

    Handles both single requests (JSON object) and batch requests (JSON array).
    For each request the handler dispatches to :func:`_handle_single` to
    build the appropriate response.
    """
    async for raw in ws:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            responses = [_handle_single(req) for req in parsed]
            await ws.send(json.dumps(responses))
        else:
            response = _handle_single(parsed)
            await ws.send(json.dumps(response))


def _handle_single(req: dict) -> dict:
    """Build a response dict for one request object.

    Supported methods:
    * ``system.ping``  — returns ``{"id": ..., "ok": true, "result": {"pong": true}}``
    * ``node.create``  — returns a fake node descriptor.
    * Anything else   — returns a METHOD_NOT_FOUND error envelope.
    """
    req_id = req.get("id")
    method = req.get("method", "")
    params = req.get("params", {})

    if method == "system.ping":
        return {"id": req_id, "ok": True, "result": {"pong": True}}

    if method == "node.create":
        parent = params.get("parentPath", "/project1")
        op_type = params.get("type", "noiseCHOP")
        name = params.get("name") or f"{op_type}1"
        return {
            "id": req_id,
            "ok": True,
            "result": {
                "path": f"{parent}/{name}",
                "name": name,
                "type": op_type,
            },
        }

    # Unknown method — return an error envelope.
    return {
        "id": req_id,
        "ok": False,
        "error": {
            "code": _METHOD_NOT_FOUND,
            "message": f"Method not found: {method!r}",
        },
    }


@pytest_asyncio.fixture
async def mock_server() -> AsyncGenerator[tuple[str, int], None]:
    """Spin up a local WebSocket server that implements the touch-mcp protocol.

    Binds to ``localhost`` on an OS-assigned free port and yields a
    ``(host, port)`` tuple.  The server is shut down after the test completes.
    """
    async with serve(_handle_client, host="127.0.0.1", port=0) as server:
        # Retrieve the actual port chosen by the OS.
        sockets = server.sockets
        host, port, *_ = sockets[0].getsockname()
        yield host, port


# ---------------------------------------------------------------------------
# TDBridge fixture
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def bridge(mock_server: tuple[str, int]) -> AsyncGenerator[TDBridge, None]:
    """Provide a :class:`TDBridge` already connected to the mock server.

    Automatically disconnects after the test.
    """
    host, port = mock_server
    td_bridge = TDBridge(
        host=host,
        port=port,
        timeout=5.0,
        reconnect_interval=0.1,
        max_reconnect_attempts=3,
    )
    await td_bridge.connect()
    yield td_bridge
    await td_bridge.disconnect()
