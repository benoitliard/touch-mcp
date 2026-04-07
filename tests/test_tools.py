"""Unit tests for MCP tool parameter validation.

These tests focus on the JSON parsing and validation logic inside the tool
functions — specifically ``td_set_parameters`` (parameters.py) and
``td_batch`` (batch.py).  They do not require a live WebSocket connection;
the bridge is replaced with a lightweight mock via ``unittest.mock``.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers — build a fake MCP Context whose lifespan_context holds a mock bridge
# ---------------------------------------------------------------------------


def _make_ctx(bridge: Any) -> MagicMock:
    """Return a minimal MCP Context mock with a bridge injected into lifespan_context."""
    ctx = MagicMock()
    ctx.request_context.lifespan_context = {"bridge": bridge}
    return ctx


def _connected_bridge(**request_return_value: Any) -> MagicMock:
    """Return a mock bridge that reports connected=True and returns the given value from request/batch."""
    bridge = MagicMock()
    bridge.connected = True
    bridge.request = AsyncMock(return_value=request_return_value or {"ok": True, "result": {}})
    bridge.batch = AsyncMock(return_value=[{"ok": True, "result": {}}])
    return bridge


def _disconnected_bridge() -> MagicMock:
    """Return a mock bridge that reports connected=False."""
    bridge = MagicMock()
    bridge.connected = False
    return bridge


# ---------------------------------------------------------------------------
# td_set_parameters — JSON parsing validation
# ---------------------------------------------------------------------------


class TestTdSetParameters:
    """Tests for the JSON-string parsing in td_set_parameters."""

    @pytest.mark.asyncio
    async def test_valid_json_string_is_parsed_and_forwarded(self) -> None:
        """Well-formed JSON is decoded and forwarded to bridge.request."""
        from touch_mcp.tools.parameters import td_set_parameters

        values_dict = {"tx": 1.0, "ty": 2.5, "Roughness": 0.8}
        bridge = _connected_bridge(ok=True, result={"updated": list(values_dict.keys())})
        ctx = _make_ctx(bridge)

        await td_set_parameters(path="/project1/noise1", values=json.dumps(values_dict), ctx=ctx)

        bridge.request.assert_awaited_once()
        call_args = bridge.request.call_args
        # Second positional argument is the params dict.
        params_sent = call_args[0][1]
        assert params_sent["values"] == values_dict

    @pytest.mark.asyncio
    async def test_invalid_json_raises_value_error(self) -> None:
        """A non-JSON string for 'values' must raise ValueError."""
        from touch_mcp.tools.parameters import td_set_parameters

        bridge = _connected_bridge()
        ctx = _make_ctx(bridge)

        with pytest.raises(ValueError, match="valid JSON"):
            await td_set_parameters(path="/project1/noise1", values="not-json", ctx=ctx)

    @pytest.mark.asyncio
    async def test_json_array_raises_value_error(self) -> None:
        """A JSON array string (not an object) must raise ValueError."""
        from touch_mcp.tools.parameters import td_set_parameters

        bridge = _connected_bridge()
        ctx = _make_ctx(bridge)

        with pytest.raises(ValueError, match="JSON object"):
            await td_set_parameters(path="/p", values='["tx", "ty"]', ctx=ctx)

    @pytest.mark.asyncio
    async def test_json_scalar_raises_value_error(self) -> None:
        """A bare JSON scalar (not an object) must raise ValueError."""
        from touch_mcp.tools.parameters import td_set_parameters

        bridge = _connected_bridge()
        ctx = _make_ctx(bridge)

        with pytest.raises(ValueError, match="JSON object"):
            await td_set_parameters(path="/p", values="42", ctx=ctx)

    @pytest.mark.asyncio
    async def test_empty_object_is_valid(self) -> None:
        """An empty JSON object ``{}`` is valid and must not raise."""
        from touch_mcp.tools.parameters import td_set_parameters

        bridge = _connected_bridge()
        ctx = _make_ctx(bridge)

        # Should not raise.
        await td_set_parameters(path="/p", values="{}", ctx=ctx)
        bridge.request.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_boolean_values_preserved(self) -> None:
        """Boolean values inside the JSON string must be preserved as Python bools."""
        from touch_mcp.tools.parameters import td_set_parameters

        bridge = _connected_bridge()
        ctx = _make_ctx(bridge)

        await td_set_parameters(path="/p", values='{"active": true, "bypass": false}', ctx=ctx)

        params_sent = bridge.request.call_args[0][1]
        assert params_sent["values"]["active"] is True
        assert params_sent["values"]["bypass"] is False

    @pytest.mark.asyncio
    async def test_string_values_preserved(self) -> None:
        """String values inside the JSON must remain strings."""
        from touch_mcp.tools.parameters import td_set_parameters

        bridge = _connected_bridge()
        ctx = _make_ctx(bridge)

        await td_set_parameters(path="/p", values='{"label": "hello"}', ctx=ctx)

        params_sent = bridge.request.call_args[0][1]
        assert params_sent["values"]["label"] == "hello"

    @pytest.mark.asyncio
    async def test_path_forwarded_correctly(self) -> None:
        """The node path must be passed through to bridge.request unchanged."""
        from touch_mcp.tools.parameters import td_set_parameters

        bridge = _connected_bridge()
        ctx = _make_ctx(bridge)

        node_path = "/project1/comp1/noise99"
        await td_set_parameters(path=node_path, values='{"tx": 0}', ctx=ctx)

        params_sent = bridge.request.call_args[0][1]
        assert params_sent["path"] == node_path

    @pytest.mark.asyncio
    async def test_result_returned_as_json_string(self) -> None:
        """The tool must return a JSON string representation of the bridge result."""
        from touch_mcp.tools.parameters import td_set_parameters

        fake_result = {"ok": True, "result": {"updated": ["tx"]}}
        bridge = _connected_bridge(**fake_result)
        ctx = _make_ctx(bridge)

        raw_result = await td_set_parameters(path="/p", values='{"tx": 1}', ctx=ctx)

        parsed = json.loads(raw_result)
        assert parsed == fake_result


# ---------------------------------------------------------------------------
# td_batch — JSON parsing validation
# ---------------------------------------------------------------------------


class TestTdBatch:
    """Tests for the JSON-string parsing in td_batch."""

    @pytest.mark.asyncio
    async def test_valid_operations_array_forwarded(self) -> None:
        """A valid JSON array of operations is forwarded to bridge.batch."""
        from touch_mcp.tools.batch import td_batch

        ops = [
            {"method": "system.ping", "params": {}},
            {"method": "node.create", "params": {"parentPath": "/p", "type": "noiseCHOP", "name": None}},
        ]
        bridge = _connected_bridge()
        bridge.batch = AsyncMock(return_value=[{"ok": True}, {"ok": True}])
        ctx = _make_ctx(bridge)

        await td_batch(operations=json.dumps(ops), ctx=ctx)

        bridge.batch.assert_awaited_once()
        sent_requests = bridge.batch.call_args[0][0]
        assert len(sent_requests) == 2
        assert sent_requests[0]["method"] == "system.ping"
        assert sent_requests[1]["method"] == "node.create"

    @pytest.mark.asyncio
    async def test_invalid_json_raises_value_error(self) -> None:
        """A non-JSON string for 'operations' must raise ValueError."""
        from touch_mcp.tools.batch import td_batch

        bridge = _connected_bridge()
        ctx = _make_ctx(bridge)

        with pytest.raises(ValueError, match="valid JSON"):
            await td_batch(operations="{bad json", ctx=ctx)

    @pytest.mark.asyncio
    async def test_json_object_raises_value_error(self) -> None:
        """A JSON object (not an array) must raise ValueError."""
        from touch_mcp.tools.batch import td_batch

        bridge = _connected_bridge()
        ctx = _make_ctx(bridge)

        with pytest.raises(ValueError, match="JSON array"):
            await td_batch(operations='{"method": "ping", "params": {}}', ctx=ctx)

    @pytest.mark.asyncio
    async def test_empty_array_returns_empty_json_array(self) -> None:
        """An empty operations array must return ``'[]'`` without calling bridge.batch."""
        from touch_mcp.tools.batch import td_batch

        bridge = _connected_bridge()
        ctx = _make_ctx(bridge)

        result = await td_batch(operations="[]", ctx=ctx)

        assert json.loads(result) == []
        bridge.batch.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_operation_missing_method_raises(self) -> None:
        """An operation without a 'method' key must raise ValueError."""
        from touch_mcp.tools.batch import td_batch

        bridge = _connected_bridge()
        ctx = _make_ctx(bridge)

        bad_ops = json.dumps([{"params": {}}])
        with pytest.raises(ValueError, match="method"):
            await td_batch(operations=bad_ops, ctx=ctx)

    @pytest.mark.asyncio
    async def test_operation_missing_params_raises(self) -> None:
        """An operation without a 'params' key must raise ValueError."""
        from touch_mcp.tools.batch import td_batch

        bridge = _connected_bridge()
        ctx = _make_ctx(bridge)

        bad_ops = json.dumps([{"method": "system.ping"}])
        with pytest.raises(ValueError, match="params"):
            await td_batch(operations=bad_ops, ctx=ctx)

    @pytest.mark.asyncio
    async def test_operation_params_not_dict_raises(self) -> None:
        """An operation whose 'params' value is not an object must raise ValueError."""
        from touch_mcp.tools.batch import td_batch

        bridge = _connected_bridge()
        ctx = _make_ctx(bridge)

        bad_ops = json.dumps([{"method": "system.ping", "params": [1, 2, 3]}])
        with pytest.raises(ValueError, match="params"):
            await td_batch(operations=bad_ops, ctx=ctx)

    @pytest.mark.asyncio
    async def test_non_dict_operation_raises(self) -> None:
        """A non-object element inside the operations array must raise ValueError."""
        from touch_mcp.tools.batch import td_batch

        bridge = _connected_bridge()
        ctx = _make_ctx(bridge)

        bad_ops = json.dumps(["not_an_object"])
        with pytest.raises(ValueError):
            await td_batch(operations=bad_ops, ctx=ctx)

    @pytest.mark.asyncio
    async def test_result_returned_as_json_string(self) -> None:
        """The tool must return a JSON string representation of all bridge results."""
        from touch_mcp.tools.batch import td_batch

        fake_results = [{"ok": True, "result": {"pong": True}}]
        bridge = _connected_bridge()
        bridge.batch = AsyncMock(return_value=fake_results)
        ctx = _make_ctx(bridge)

        raw = await td_batch(
            operations=json.dumps([{"method": "system.ping", "params": {}}]),
            ctx=ctx,
        )

        assert json.loads(raw) == fake_results

    @pytest.mark.asyncio
    async def test_error_on_index_reported_correctly(self) -> None:
        """ValueError for a bad operation at index N should mention that index."""
        from touch_mcp.tools.batch import td_batch

        bridge = _connected_bridge()
        ctx = _make_ctx(bridge)

        # First op is fine; second op is missing 'method'.
        ops = json.dumps([
            {"method": "system.ping", "params": {}},
            {"params": {}},  # missing method
        ])
        with pytest.raises(ValueError, match="index 1"):
            await td_batch(operations=ops, ctx=ctx)
