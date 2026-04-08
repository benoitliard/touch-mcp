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


@mcp.tool()
async def td_copy_node(
    source_path: str,
    dest_parent_path: str,
    name: str | None = None,
    ctx: Context = None,
) -> str:
    """Copy a node (with all its parameters) to a new location.

    Args:
        source_path: Path of the node to copy (e.g. "/project1/noise1").
        dest_parent_path: Path of the parent container for the copy
                          (e.g. "/project1/base1").
        name: Optional name for the copy.  If omitted, TouchDesigner assigns
              a default name derived from the source operator type.

    Returns:
        JSON object with the new node's path, type, and assigned name.
    """
    bridge = ctx.request_context.lifespan_context["bridge"]
    if not bridge.connected:
        raise TDConnectionError("Not connected to TouchDesigner.")
    result = await bridge.request(
        "node.copy",
        {"sourcePath": source_path, "destParentPath": dest_parent_path, "name": name},
    )
    return json.dumps(result)


@mcp.tool()
async def td_rename_node(path: str, new_name: str, ctx: Context = None) -> str:
    """Rename a node without destroying it.

    Renames the node in place; all wires and parameter references that use
    the operator's path will need to be updated separately.

    Args:
        path: Full path of the node to rename (e.g. "/project1/noise1").
        new_name: New name for the node (e.g. "myNoise").

    Returns:
        JSON object with the updated node path and new name.
    """
    bridge = ctx.request_context.lifespan_context["bridge"]
    if not bridge.connected:
        raise TDConnectionError("Not connected to TouchDesigner.")
    result = await bridge.request("node.rename", {"path": path, "name": new_name})
    return json.dumps(result)


@mcp.tool()
async def td_find_nodes(
    path: str = "/",
    name: str | None = None,
    type: str | None = None,
    family: str | None = None,
    depth: int = 5,
    ctx: Context = None,
) -> str:
    """Search for nodes matching criteria recursively.

    More powerful than ``td_list_nodes`` — searches the entire subtree rooted
    at *path* rather than a single level of children.

    Args:
        path: Root path to search from (default: "/").
        name: Substring to match in node names (case-insensitive).
              Example: "noise" matches "noise1", "myNoise", "noiseBlend".
        type: Operator type to match exactly (e.g. "noiseCHOP", "waveTOP").
        family: Operator family to match.  Accepted values: "CHOP", "TOP",
                "SOP", "DAT", "COMP", "MAT", "VOP".
        depth: Maximum recursion depth (default: 5).

    Returns:
        JSON array of node descriptor objects containing path, type, family,
        and name for each matching node.
    """
    bridge = ctx.request_context.lifespan_context["bridge"]
    if not bridge.connected:
        raise TDConnectionError("Not connected to TouchDesigner.")
    result = await bridge.request(
        "node.find",
        {"path": path, "name": name, "type": type, "family": family, "depth": depth},
    )
    return json.dumps(result)


@mcp.tool()
async def td_get_errors(
    path: str,
    include_children: bool = False,
    ctx: Context = None,
) -> str:
    """Get errors and warnings for a node.

    Useful for diagnosing cook errors, missing file references, GLSL compile
    failures, and other operator-level issues without needing to look at the
    TouchDesigner UI.

    Args:
        path: Full path of the node to check (e.g. "/project1/glsl1").
        include_children: If ``True``, also collect errors from all descendant
                          nodes recursively.

    Returns:
        JSON object with:
        - "errors": list of error message strings.
        - "warnings": list of warning message strings.
        - "children": dict mapping child paths to their own error/warning lists
          (only present when include_children is True).
    """
    bridge = ctx.request_context.lifespan_context["bridge"]
    if not bridge.connected:
        raise TDConnectionError("Not connected to TouchDesigner.")
    result = await bridge.request(
        "node.errors",
        {"path": path, "includeChildren": include_children},
    )
    return json.dumps(result)


@mcp.tool()
async def td_set_flags(
    path: str,
    display: bool | None = None,
    render: bool | None = None,
    bypass: bool | None = None,
    ctx: Context = None,
) -> str:
    """Set display, render, and/or bypass flags on a node.

    Only the flags that are explicitly provided will be changed; omitted flags
    keep their current state.

    Args:
        path: Full path of the node (e.g. "/project1/geo1").
        display: Set display flag (blue flag).  The displayed node's output
                 is shown in the network viewer.
        render: Set render flag (purple flag).  Controls whether the node
                participates in a SOP/TOP render pipeline.
        bypass: Set bypass flag (yellow flag).  Bypassed nodes pass their
                first input through unchanged.

    Returns:
        JSON object confirming the updated flag states for the node.
    """
    bridge = ctx.request_context.lifespan_context["bridge"]
    if not bridge.connected:
        raise TDConnectionError("Not connected to TouchDesigner.")
    result = await bridge.request(
        "node.set_flags",
        {"path": path, "display": display, "render": render, "bypass": bypass},
    )
    return json.dumps(result)
