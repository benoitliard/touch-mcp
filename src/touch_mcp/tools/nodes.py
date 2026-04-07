"""Node management tools for TouchDesigner — create, delete, list, and inspect operators."""

from __future__ import annotations

import json

from mcp.server.fastmcp import Context

from touch_mcp.errors import TDConnectionError
from touch_mcp.server import mcp


@mcp.tool()
async def td_create_node(
    parent_path: str,
    operator_type: str,
    name: str | None = None,
    ctx: Context = None,
) -> str:
    """Create a new operator node in TouchDesigner.

    Args:
        parent_path: Path to the parent container (e.g. "/project1").
        operator_type: Operator type string (e.g. "noiseCHOP", "waveTOP", "sphereSOP").
        name: Optional custom name for the new node. If omitted TouchDesigner
              assigns a default name based on the operator type.

    Returns:
        JSON object with the created node's path, type, and assigned name.
    """
    bridge = ctx.request_context.lifespan_context["bridge"]
    if not bridge.connected:
        raise TDConnectionError("Not connected to TouchDesigner.")
    result = await bridge.request(
        "node.create",
        {"parentPath": parent_path, "type": operator_type, "name": name},
    )
    return json.dumps(result)


@mcp.tool()
async def td_delete_node(path: str, ctx: Context = None) -> str:
    """Delete an operator node from the TouchDesigner network.

    Deletes the node at *path* and all of its children.  Connections to
    neighbouring nodes are removed automatically by TouchDesigner.

    Args:
        path: Full path of the node to delete (e.g. "/project1/noise1").

    Returns:
        JSON object confirming deletion with the deleted node path.
    """
    bridge = ctx.request_context.lifespan_context["bridge"]
    if not bridge.connected:
        raise TDConnectionError("Not connected to TouchDesigner.")
    result = await bridge.request("node.delete", {"path": path})
    return json.dumps(result)


@mcp.tool()
async def td_list_nodes(
    path: str = "/",
    family: str | None = None,
    depth: int = 1,
    ctx: Context = None,
) -> str:
    """List child nodes under a path, optionally filtered by operator family.

    Args:
        path: Parent path to list children of (default: "/").
        family: Filter results by operator family.  Accepted values:
                "CHOP", "TOP", "SOP", "DAT", "COMP", "MAT", "VOP".
                Omit to return all families.
        depth: Recursion depth — 1 returns direct children only, higher values
               recurse into sub-networks.

    Returns:
        JSON array of node descriptor objects containing path, type, family,
        and name for each matching node.
    """
    bridge = ctx.request_context.lifespan_context["bridge"]
    if not bridge.connected:
        raise TDConnectionError("Not connected to TouchDesigner.")
    result = await bridge.request(
        "node.list",
        {"path": path, "family": family, "depth": depth},
    )
    return json.dumps(result)


@mcp.tool()
async def td_get_node(path: str, ctx: Context = None) -> str:
    """Get detailed information about a TouchDesigner node.

    Returns comprehensive node metadata including operator type, family,
    network position, current parameter values, and input/output connection
    lists.

    Args:
        path: Full path of the node to inspect (e.g. "/project1/noise1").

    Returns:
        JSON object with fields: path, name, type, family, x, y, parameters,
        inputs, outputs, and any operator-specific state.
    """
    bridge = ctx.request_context.lifespan_context["bridge"]
    if not bridge.connected:
        raise TDConnectionError("Not connected to TouchDesigner.")
    result = await bridge.request("node.get", {"path": path})
    return json.dumps(result)
