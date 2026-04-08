"""Script execution and Python introspection tools for TouchDesigner."""

from __future__ import annotations

import json

from mcp.server.fastmcp import Context

from touch_mcp.errors import TDConnectionError
from touch_mcp.server import mcp


@mcp.tool()
async def td_execute_script(
    script: str,
    context_path: str | None = None,
    ctx: Context = None,
) -> str:
    """Execute a Python script inside the running TouchDesigner instance.

    The script runs in TouchDesigner's main thread Python environment and
    has full access to the ``td`` module, ``op()``, ``me``, and all other
    TD globals.  Return values are captured via a ``result`` variable — if
    the script assigns to ``result`` that value is serialised and returned.

    Args:
        script: Python source code to execute.  Multi-line scripts are
                supported.  Example:
                    result = op('/project1/noise1').par.tx.val
        context_path: Optional path to set as the execution context (``me``
                      inside the script).  Omit to use the project root.

    Returns:
        JSON object with:
        - "result": the value of the ``result`` variable if set, else null.
        - "stdout": any text printed to stdout during execution.
        - "error": error message string if an exception was raised, else null.
    """
    bridge = ctx.request_context.lifespan_context["bridge"]
    if not bridge.connected:
        raise TDConnectionError("Not connected to TouchDesigner.")
    result = await bridge.request(
        "script.exec",
        {"code": script, "contextPath": context_path},
    )
    return json.dumps(result)


@mcp.tool()
async def td_class_list(
    pattern: str | None = None,
    ctx: Context = None,
) -> str:
    """List all TouchDesigner Python classes available in the TD environment.

    Useful for discovering operator classes (e.g. ``baseCOMP``, ``noiseCHOP``)
    and utility types (e.g. ``Par``, ``Channel``, ``Cell``).

    Args:
        pattern: Optional glob pattern to filter class names
                 (e.g. "*CHOP" lists all CHOP classes, "noise*" finds noise
                 variants).  Omit to return all classes.

    Returns:
        JSON array of class name strings.
    """
    bridge = ctx.request_context.lifespan_context["bridge"]
    if not bridge.connected:
        raise TDConnectionError("Not connected to TouchDesigner.")
    result = await bridge.request(
        "script.class_list",
        {"pattern": pattern},
    )
    return json.dumps(result)


@mcp.tool()
async def td_class_detail(class_name: str, ctx: Context = None) -> str:
    """Get methods and properties for a TouchDesigner Python class.

    Introspects the requested class and returns its public API surface —
    useful for discovering what you can call on a node reference without
    leaving the MCP session.

    Args:
        class_name: Name of the TD Python class to inspect (e.g. "noiseCHOP",
                    "Par", "Channel").

    Returns:
        JSON object with:
        - "name": class name.
        - "docstring": class-level documentation string.
        - "methods": list of {name, signature, doc} objects.
        - "properties": list of {name, type, doc, readOnly} objects.
    """
    bridge = ctx.request_context.lifespan_context["bridge"]
    if not bridge.connected:
        raise TDConnectionError("Not connected to TouchDesigner.")
    result = await bridge.request(
        "script.class_detail",
        {"name": class_name},
    )
    return json.dumps(result)


@mcp.tool()
async def td_module_help(module_name: str, ctx: Context = None) -> str:
    """Get the help() output for a TouchDesigner Python module.

    Runs ``help(<module>)`` inside TouchDesigner and returns the resulting
    text.  Works for built-in TD modules (``td``, ``TDFunctions``, etc.) and
    any module importable in the TD Python environment.

    Args:
        module_name: Name of the module to query (e.g. "td", "TDFunctions",
                     "numpy").

    Returns:
        JSON object with:
        - "module": module name.
        - "help": full help() text as a string.
    """
    bridge = ctx.request_context.lifespan_context["bridge"]
    if not bridge.connected:
        raise TDConnectionError("Not connected to TouchDesigner.")
    result = await bridge.request(
        "script.module_help",
        {"name": module_name},
    )
    return json.dumps(result)
