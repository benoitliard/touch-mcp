"""TouchDesigner MCP Server — high-performance live control via WebSocket."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from mcp.server.fastmcp import FastMCP

from touch_mcp.bridge.connection import TDBridge

logger = logging.getLogger("touch_mcp")

# These will be set by cli.py before run_server is called
_td_host = "localhost"
_td_port = 9980
_td_timeout = 30.0


@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[dict]:
    """Manage the WebSocket bridge lifecycle."""
    bridge = TDBridge(host=_td_host, port=_td_port, timeout=_td_timeout)
    await bridge.connect()
    try:
        yield {"bridge": bridge}
    finally:
        await bridge.disconnect()


mcp = FastMCP(
    "touch-mcp",
    lifespan=lifespan,
)

# Import tool modules to register them via @mcp.tool() decorators
import touch_mcp.tools.nodes  # noqa: E402, F401
import touch_mcp.tools.parameters  # noqa: E402, F401
import touch_mcp.tools.connections  # noqa: E402, F401
import touch_mcp.tools.data  # noqa: E402, F401
import touch_mcp.tools.scripts  # noqa: E402, F401
import touch_mcp.tools.timeline  # noqa: E402, F401
import touch_mcp.tools.render  # noqa: E402, F401
import touch_mcp.tools.project  # noqa: E402, F401
import touch_mcp.tools.layout  # noqa: E402, F401
import touch_mcp.tools.batch  # noqa: E402, F401


def run_server(host: str, port: int, timeout: float) -> None:
    """Start the MCP server with the given TD connection settings.

    This function is called by cli.py after argument parsing. It mutates the
    module-level connection variables so that the ``lifespan`` context manager
    picks up the correct host/port/timeout when FastMCP initialises the server.

    Args:
        host: Hostname or IP address of the TouchDesigner WebSocket server.
        port: TCP port on which TouchDesigner is listening.
        timeout: Per-request timeout in seconds.
    """
    global _td_host, _td_port, _td_timeout
    _td_host = host
    _td_port = port
    _td_timeout = timeout
    mcp.run(transport="stdio")
