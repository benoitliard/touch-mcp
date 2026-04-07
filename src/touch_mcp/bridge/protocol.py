"""WebSocket message protocol for TouchDesigner communication."""

from __future__ import annotations

import json
from typing import Any


def make_request(method: str, params: dict[str, Any], req_id: int) -> str:
    """Build a JSON-RPC-style request message.

    Args:
        method: The remote method name to invoke on the TouchDesigner side.
        params: Keyword parameters to pass with the request.
        req_id: Unique integer identifying this request for correlation.

    Returns:
        A JSON-encoded string ready for transmission over the WebSocket.

    Example:
        >>> make_request("par.set", {"node": "/path", "name": "tx", "value": 1.0}, 1)
        '{"id": 1, "method": "par.set", "params": {"node": "/path", "name": "tx", "value": 1.0}}'
    """
    return json.dumps({"id": req_id, "method": method, "params": params})


def make_batch(requests: list[dict[str, Any]]) -> str:
    """Build a JSON batch request (array of individual request dicts).

    All requests in the batch should already be constructed as dicts — e.g.
    via ``json.loads(make_request(...))`` — before being passed here.

    Args:
        requests: A list of request dicts, each containing ``id``, ``method``,
            and ``params`` keys.

    Returns:
        A JSON-encoded string representing a batch array.

    Example:
        >>> reqs = [
        ...     {"id": 1, "method": "par.set", "params": {"node": "/p", "name": "tx", "value": 0}},
        ...     {"id": 2, "method": "par.set", "params": {"node": "/p", "name": "ty", "value": 1}},
        ... ]
        >>> make_batch(reqs)
        '[{"id": 1, ...}, {"id": 2, ...}]'
    """
    return json.dumps(requests)


def parse_response(raw: str) -> dict[str, Any] | list[dict[str, Any]]:
    """Parse a raw JSON response string from TouchDesigner.

    Handles both single-response objects and batch-response arrays.

    Args:
        raw: The raw JSON string received over the WebSocket.

    Returns:
        A single response dict, or a list of response dicts for batch replies.

    Raises:
        json.JSONDecodeError: If ``raw`` is not valid JSON.
    """
    return json.loads(raw)


def is_error(response: dict[str, Any]) -> bool:
    """Return ``True`` if a response dict signals a TouchDesigner-side error.

    TouchDesigner signals errors by setting ``"ok": false`` in the response
    envelope. A missing ``"ok"`` key is treated as success.

    Args:
        response: A single parsed response dict.

    Returns:
        ``True`` when ``response["ok"]`` is explicitly ``False``.
    """
    return response.get("ok") is False
