"""Parameter read/write tools for TouchDesigner operator parameters."""

from __future__ import annotations

import json

from mcp.server.fastmcp import Context

from touch_mcp.errors import TDConnectionError
from touch_mcp.server import mcp


@mcp.tool()
async def td_get_parameters(
    path: str,
    pattern: str | None = None,
    ctx: Context = None,
) -> str:
    """Get current parameter values for a TouchDesigner node.

    Args:
        path: Full path of the node (e.g. "/project1/noise1").
        pattern: Optional glob pattern to filter parameter names
                 (e.g. "t[xyz]" matches tx, ty, tz; "R*" matches all rotation
                 parameters).  Omit to return all parameters.

    Returns:
        JSON object mapping parameter name to its current value.
        Example: {"tx": 0.0, "ty": 1.5, "tz": 0.0}
    """
    bridge = ctx.request_context.lifespan_context["bridge"]
    if not bridge.connected:
        raise TDConnectionError("Not connected to TouchDesigner.")
    result = await bridge.request(
        "par.get",
        {"path": path, "pattern": pattern},
    )
    return json.dumps(result)


@mcp.tool()
async def td_set_parameters(
    path: str,
    values: str,
    ctx: Context = None,
) -> str:
    """Set one or more parameter values on a TouchDesigner node.

    Because MCP tool parameters must be scalar types, *values* is supplied
    as a JSON string that is decoded server-side before forwarding to
    TouchDesigner.

    Args:
        path: Full path of the node (e.g. "/project1/noise1").
        values: JSON string mapping parameter names to their new values.
                Example: '{"tx": 1.0, "ty": 2.5, "Roughness": 0.8}'
                Numeric, boolean, and string values are all supported.

    Returns:
        JSON object confirming which parameters were updated.
    """
    bridge = ctx.request_context.lifespan_context["bridge"]
    if not bridge.connected:
        raise TDConnectionError("Not connected to TouchDesigner.")
    try:
        parsed_values = json.loads(values)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"'values' must be a valid JSON object string. Got: {values!r}"
        ) from exc
    if not isinstance(parsed_values, dict):
        raise ValueError(
            f"'values' must decode to a JSON object (dict). Got type: {type(parsed_values).__name__}"
        )
    result = await bridge.request(
        "par.set",
        {"path": path, "values": parsed_values},
    )
    return json.dumps(result)


@mcp.tool()
async def td_get_parameter_info(
    path: str,
    names: str | None = None,
    ctx: Context = None,
) -> str:
    """Get parameter metadata for a TouchDesigner node.

    Returns detailed schema information for each parameter including its
    display label, style (Float, Int, Toggle, Menu, etc.), default value,
    numeric range, and menu options where applicable.

    Args:
        path: Full path of the node (e.g. "/project1/noise1").
        names: Comma-separated list of parameter names to query
               (e.g. "tx,ty,tz").  Omit to return metadata for all
               parameters on the node.

    Returns:
        JSON array of parameter descriptor objects, each containing:
        name, label, style, default, min, max, clampMin, clampMax,
        menuNames (for menu params), and current value.
    """
    bridge = ctx.request_context.lifespan_context["bridge"]
    if not bridge.connected:
        raise TDConnectionError("Not connected to TouchDesigner.")
    name_list: list[str] | None = None
    if names is not None:
        name_list = [n.strip() for n in names.split(",") if n.strip()]
    result = await bridge.request(
        "par.info",
        {"path": path, "names": name_list},
    )
    return json.dumps(result)
