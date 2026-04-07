"""WebSocket bridge package for TouchDesigner communication."""

from touch_mcp.bridge.connection import TDBridge
from touch_mcp.bridge.protocol import is_error, make_batch, make_request, parse_response

__all__ = [
    "TDBridge",
    "is_error",
    "make_batch",
    "make_request",
    "parse_response",
]
