"""Network layout tools for TouchDesigner — position and align nodes in the editor."""

from __future__ import annotations

import json

from mcp.server.fastmcp import Context

from touch_mcp.errors import TDConnectionError
from touch_mcp.server import mcp


@mcp.tool()
async def td_set_node_position(positions: str, ctx: Context = None) -> str:
    """Set the network-editor position of one or more TouchDesigner nodes.

    Positions are specified in network coordinates (not screen pixels).
    Multiple nodes can be repositioned in a single call for efficiency.

    Args:
        positions: JSON array string of position objects.  Each object must
                   have the keys:
                   - "path" (str): full path of the node to move.
                   - "x" (float): horizontal position in network units.
                   - "y" (float): vertical position in network units.
                   Example:
                   '[{"path": "/project1/noise1", "x": 0, "y": 0},
                     {"path": "/project1/math1",  "x": 200, "y": 0}]'

    Returns:
        JSON array of objects confirming the new position of each node,
        each containing "path", "x", and "y".
    """
    bridge = ctx.request_context.lifespan_context["bridge"]
    if not bridge.connected:
        raise TDConnectionError("Not connected to TouchDesigner.")
    try:
        parsed_positions = json.loads(positions)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"'positions' must be a valid JSON array string. Got: {positions!r}"
        ) from exc
    if not isinstance(parsed_positions, list):
        raise ValueError(
            f"'positions' must decode to a JSON array. Got type: {type(parsed_positions).__name__}"
        )
    for entry in parsed_positions:
        if not isinstance(entry, dict) or not {"path", "x", "y"}.issubset(entry.keys()):
            raise ValueError(
                "Each position entry must be an object with 'path', 'x', and 'y' keys. "
                f"Got: {entry!r}"
            )
    result = await bridge.request("layout.setPositions", {"positions": parsed_positions})
    return json.dumps(result)


@mcp.tool()
async def td_align_nodes(
    paths: str,
    direction: str = "horizontal",
    spacing: int = 200,
    ctx: Context = None,
) -> str:
    """Align a group of TouchDesigner nodes in the network editor.

    Distributes the listed nodes evenly along the specified axis, preserving
    their order and adjusting positions to achieve the requested spacing.

    Args:
        paths: Comma-separated list of node paths to align
               (e.g. "/project1/noise1,/project1/math1,/project1/null1").
               At least two paths must be provided.
        direction: Layout axis — "horizontal" spaces nodes left-to-right,
                   "vertical" spaces them top-to-bottom (default: "horizontal").
        spacing: Distance between node centres in network units (default: 200).

    Returns:
        JSON array of objects with the updated "path", "x", and "y" for each
        repositioned node.
    """
    bridge = ctx.request_context.lifespan_context["bridge"]
    if not bridge.connected:
        raise TDConnectionError("Not connected to TouchDesigner.")
    if direction not in ("horizontal", "vertical"):
        raise ValueError(
            f"'direction' must be 'horizontal' or 'vertical'. Got: {direction!r}"
        )
    path_list = [p.strip() for p in paths.split(",") if p.strip()]
    if len(path_list) < 2:
        raise ValueError(
            "At least two node paths are required for alignment. "
            f"Got: {path_list!r}"
        )
    result = await bridge.request(
        "layout.alignNodes",
        {"paths": path_list, "direction": direction, "spacing": spacing},
    )
    return json.dumps(result)
