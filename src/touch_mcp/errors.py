"""Error hierarchy for TouchDesigner MCP server operations."""

from __future__ import annotations


class TDError(Exception):
    """Base error for TouchDesigner operations."""

    code: str = "TD_ERROR"


class TDConnectionError(TDError):
    """Raised when a connection to TouchDesigner cannot be established or is lost."""

    code = "CONNECTION_ERROR"


class TDTimeoutError(TDError):
    """Raised when a TouchDesigner operation exceeds the configured timeout."""

    code = "TIMEOUT"


class TDNodeNotFoundError(TDError):
    """Raised when a referenced TouchDesigner node does not exist."""

    code = "NODE_NOT_FOUND"


class TDInvalidParamError(TDError):
    """Raised when an invalid parameter is supplied to a TouchDesigner operation."""

    code = "INVALID_PARAM"


class TDScriptError(TDError):
    """Raised when a script executed inside TouchDesigner fails."""

    code = "SCRIPT_ERROR"
