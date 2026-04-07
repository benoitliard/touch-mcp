"""Batch execution tool for TouchDesigner — multiple operations in one round-trip."""

from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import Context

from touch_mcp.errors import TDConnectionError
from touch_mcp.server import mcp


@mcp.tool()
async def td_batch(operations: str, ctx: Context = None) -> str:
    """Execute multiple TouchDesigner operations in a single WebSocket round-trip.

    This is the primary performance tool for complex workflows.  Instead of
    issuing several sequential tool calls — each incurring a full network
    round-trip — you can bundle all operations into one request and receive
    all responses together.

    Ideal use-cases include:
    - Creating several nodes and wiring them in one shot.
    - Reading multiple CHOP channels and parameters simultaneously.
    - Applying bulk parameter changes across many nodes.

    Args:
        operations: JSON array string of operation objects.  Each object must
                    have:
                    - "method" (str): the TouchDesigner bridge method name
                      (e.g. "node.create", "par.set", "chop.read").
                    - "params" (object): method-specific parameter dict.
                    Example:
                    '[
                      {"method": "node.create",
                       "params": {"parentPath": "/project1",
                                  "type": "noiseCHOP", "name": null}},
                      {"method": "par.set",
                       "params": {"path": "/project1/noise1",
                                  "values": {"roughness": 0.7}}},
                      {"method": "node.create",
                       "params": {"parentPath": "/project1",
                                  "type": "nullCHOP", "name": null}},
                      {"method": "connection.create",
                       "params": {"fromPath": "/project1/noise1",
                                  "toPath": "/project1/null1",
                                  "fromOutput": 0, "toInput": 0}}
                    ]'

    Returns:
        JSON array of response objects in the same order as the input
        operations.  Each response reflects the result of the corresponding
        method call and has the same shape as the single-operation tools.
    """
    bridge = ctx.request_context.lifespan_context["bridge"]
    if not bridge.connected:
        raise TDConnectionError("Not connected to TouchDesigner.")

    try:
        parsed_ops: Any = json.loads(operations)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"'operations' must be a valid JSON array string. Got: {operations!r}"
        ) from exc

    if not isinstance(parsed_ops, list):
        raise ValueError(
            f"'operations' must decode to a JSON array. Got type: {type(parsed_ops).__name__}"
        )

    if not parsed_ops:
        return json.dumps([])

    requests: list[dict[str, Any]] = []
    for i, op in enumerate(parsed_ops):
        if not isinstance(op, dict):
            raise ValueError(
                f"Operation at index {i} must be an object with 'method' and 'params' keys. "
                f"Got: {op!r}"
            )
        if "method" not in op:
            raise ValueError(
                f"Operation at index {i} is missing required key 'method'. Got: {op!r}"
            )
        if "params" not in op:
            raise ValueError(
                f"Operation at index {i} is missing required key 'params'. Got: {op!r}"
            )
        if not isinstance(op["params"], dict):
            raise ValueError(
                f"Operation at index {i}: 'params' must be an object. "
                f"Got type: {type(op['params']).__name__}"
            )
        requests.append({"method": op["method"], "params": op["params"]})

    results = await bridge.batch(requests)
    return json.dumps(results)
