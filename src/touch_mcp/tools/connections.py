"""Wiring tools for TouchDesigner — create and inspect node connections."""

from __future__ import annotations

import json

from mcp.server.fastmcp import Context

from touch_mcp.errors import TDConnectionError
from touch_mcp.server import mcp


@mcp.tool()
async def td_create_connection(
    from_path: str,
    to_path: str,
    from_output: int = 0,
    to_input: int = 0,
    ctx: Context = None,
) -> str:
    """Wire two TouchDesigner nodes together.

    Connects the specified output of *from_path* to the specified input of
    *to_path*.  Both nodes must exist and be in the same network.  Operators
    of incompatible families (e.g. TOP to CHOP) will be rejected by
    TouchDesigner.

    Args:
        from_path: Full path of the source (upstream) node.
        to_path: Full path of the destination (downstream) node.
        from_output: Zero-based index of the source node's output connector
                     (default: 0).
        to_input: Zero-based index of the destination node's input connector
                  (default: 0).

    Returns:
        JSON object confirming the connection with from/to paths and
        connector indices.
    """
    bridge = ctx.request_context.lifespan_context["bridge"]
    if not bridge.connected:
        raise TDConnectionError("Not connected to TouchDesigner.")
    result = await bridge.request(
        "connection.create",
        {
            "fromPath": from_path,
            "toPath": to_path,
            "fromOutput": from_output,
            "toInput": to_input,
        },
    )
    return json.dumps(result)


@mcp.tool()
async def td_delete_connection(
    path: str,
    input_index: int | None = None,
    output_index: int | None = None,
    ctx: Context = None,
) -> str:
    """Disconnect a node's input or output connector.

    Supply *input_index* to sever the wire arriving at that input, or
    *output_index* to sever all wires leaving that output.  At least one of
    the two index arguments must be provided.

    Args:
        path: Full path of the node whose connection should be removed.
        input_index: Zero-based index of the input connector to disconnect.
                     Omit if disconnecting an output.
        output_index: Zero-based index of the output connector to disconnect.
                      Omit if disconnecting an input.

    Returns:
        JSON object confirming which connectors were disconnected.
    """
    bridge = ctx.request_context.lifespan_context["bridge"]
    if not bridge.connected:
        raise TDConnectionError("Not connected to TouchDesigner.")
    if input_index is None and output_index is None:
        raise ValueError(
            "At least one of 'input_index' or 'output_index' must be specified."
        )
    result = await bridge.request(
        "connection.delete",
        {"path": path, "inputIndex": input_index, "outputIndex": output_index},
    )
    return json.dumps(result)


@mcp.tool()
async def td_get_connections(path: str, ctx: Context = None) -> str:
    """List all input and output connections for a TouchDesigner node.

    Returns a complete picture of what is wired into and out of the node,
    including the remote node path and connector index for each wire.

    Args:
        path: Full path of the node to inspect (e.g. "/project1/merge1").

    Returns:
        JSON object with two keys:
        - "inputs": list of {inputIndex, fromPath, fromOutput} objects.
        - "outputs": list of {outputIndex, toPath, toInput} objects.
    """
    bridge = ctx.request_context.lifespan_context["bridge"]
    if not bridge.connected:
        raise TDConnectionError("Not connected to TouchDesigner.")
    result = await bridge.request("connection.get", {"path": path})
    return json.dumps(result)
