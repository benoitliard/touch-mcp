"""Integration tests for touch_mcp.bridge.connection.TDBridge.

These tests exercise the full send/receive cycle via the mock WebSocket
server defined in conftest.py.  Each test that touches the network is
async and decorated with ``pytest.mark.asyncio``.
"""

from __future__ import annotations

import asyncio

import pytest
import pytest_asyncio
import websockets

from touch_mcp.bridge.connection import TDBridge
from touch_mcp.errors import TDConnectionError, TDTimeoutError


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_connect_and_disconnect(mock_server: tuple[str, int]) -> None:
    """connect() sets connected=True; disconnect() sets it back to False."""
    host, port = mock_server
    td_bridge = TDBridge(host=host, port=port, timeout=5.0)

    assert td_bridge.connected is False

    await td_bridge.connect()
    assert td_bridge.connected is True

    await td_bridge.disconnect()
    assert td_bridge.connected is False


@pytest.mark.asyncio
async def test_connect_to_unreachable_host_raises() -> None:
    """Connecting to a port with no listener raises TDConnectionError."""
    # Port 1 is almost certainly not listening and requires no privileges.
    td_bridge = TDBridge(host="127.0.0.1", port=1, timeout=2.0)
    with pytest.raises(TDConnectionError):
        await td_bridge.connect()


@pytest.mark.asyncio
async def test_disconnect_is_idempotent(bridge: TDBridge) -> None:
    """Calling disconnect() twice should not raise."""
    await bridge.disconnect()
    await bridge.disconnect()  # second call must be safe


# ---------------------------------------------------------------------------
# connected property
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_connected_property_true_when_connected(bridge: TDBridge) -> None:
    assert bridge.connected is True


@pytest.mark.asyncio
async def test_connected_property_false_before_connect(mock_server: tuple[str, int]) -> None:
    host, port = mock_server
    td_bridge = TDBridge(host=host, port=port, timeout=5.0)
    assert td_bridge.connected is False


@pytest.mark.asyncio
async def test_connected_property_false_after_disconnect(bridge: TDBridge) -> None:
    await bridge.disconnect()
    assert bridge.connected is False


# ---------------------------------------------------------------------------
# Single request / response
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_request_ping_returns_pong(bridge: TDBridge) -> None:
    """system.ping must return a response with result.pong == True."""
    response = await bridge.request("system.ping", {})
    assert response["ok"] is True
    assert response["result"]["pong"] is True


@pytest.mark.asyncio
async def test_request_returns_correct_id(bridge: TDBridge) -> None:
    """The response id must match the id embedded in the outgoing request."""
    response = await bridge.request("system.ping", {})
    # id=1 is the first request id (counter starts at 1).
    assert response["id"] == 1


@pytest.mark.asyncio
async def test_request_node_create(bridge: TDBridge) -> None:
    """node.create must return a result containing path, name, and type."""
    response = await bridge.request(
        "node.create",
        {"parentPath": "/project1", "type": "noiseCHOP", "name": "myNoise"},
    )
    assert response["ok"] is True
    result = response["result"]
    assert result["name"] == "myNoise"
    assert result["type"] == "noiseCHOP"
    assert result["path"] == "/project1/myNoise"


@pytest.mark.asyncio
async def test_request_unknown_method_returns_error(bridge: TDBridge) -> None:
    """An unknown method must return an error envelope with ok=False."""
    response = await bridge.request("unknown.method", {})
    assert response["ok"] is False
    assert "error" in response


@pytest.mark.asyncio
async def test_request_without_connecting_raises() -> None:
    """Calling request() before connect() must raise TDConnectionError."""
    td_bridge = TDBridge(host="127.0.0.1", port=9999, timeout=2.0)
    with pytest.raises(TDConnectionError):
        await td_bridge.request("system.ping", {})


@pytest.mark.asyncio
async def test_sequential_requests_have_incrementing_ids(bridge: TDBridge) -> None:
    """Each successive request must carry a strictly incrementing id."""
    r1 = await bridge.request("system.ping", {})
    r2 = await bridge.request("system.ping", {})
    assert r2["id"] == r1["id"] + 1


# ---------------------------------------------------------------------------
# Timeout
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_request_timeout_raises_td_timeout_error(mock_server: tuple[str, int]) -> None:
    """A request that receives no response within timeout raises TDTimeoutError.

    We achieve a non-responding server by connecting through a bridge whose
    timeout is very short (0.05 s) and sending a method that the mock server
    will actually respond to — but the server is temporarily paused via a
    custom fixture that never replies, so instead we simply send to a black-hole.

    The simpler approach: connect normally but send a request with a
    per-call timeout override of 0.05 s and block the receive path by
    monkey-patching the ws send so the message is swallowed.
    """
    host, port = mock_server

    # Use a fresh bridge with a very short default timeout.
    td_bridge = TDBridge(host=host, port=port, timeout=0.05)
    await td_bridge.connect()

    try:
        # Patch ws.send to drop the message so the server never sees it and
        # therefore never replies — the future will time out.
        original_send = td_bridge._ws.send  # type: ignore[union-attr]

        async def _silent_send(data: str) -> None:  # noqa: ARG001
            # Drop the message silently — no reply will arrive.
            pass

        td_bridge._ws.send = _silent_send  # type: ignore[union-attr]

        with pytest.raises(TDTimeoutError):
            await td_bridge.request("system.ping", {})
    finally:
        # Restore before disconnect to avoid spurious errors.
        if td_bridge._ws is not None:
            td_bridge._ws.send = original_send  # type: ignore[union-attr]
        await td_bridge.disconnect()


@pytest.mark.asyncio
async def test_request_per_call_timeout_overrides_default(bridge: TDBridge) -> None:
    """A per-call timeout of 0.01 s should trigger before the bridge default."""
    original_send = bridge._ws.send  # type: ignore[union-attr]

    async def _silent_send(data: str) -> None:  # noqa: ARG001
        pass

    bridge._ws.send = _silent_send  # type: ignore[union-attr]
    try:
        with pytest.raises(TDTimeoutError):
            await bridge.request("system.ping", {}, timeout=0.01)
    finally:
        bridge._ws.send = original_send  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# Batch requests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_batch_empty_list_returns_empty(bridge: TDBridge) -> None:
    """An empty batch must return an empty list without a network round-trip."""
    results = await bridge.batch([])
    assert results == []


@pytest.mark.asyncio
async def test_batch_single_request(bridge: TDBridge) -> None:
    """A batch of one request must return a list with one response."""
    results = await bridge.batch([{"method": "system.ping", "params": {}}])
    assert len(results) == 1
    assert results[0]["ok"] is True
    assert results[0]["result"]["pong"] is True


@pytest.mark.asyncio
async def test_batch_multiple_requests_all_returned(bridge: TDBridge) -> None:
    """All responses in a batch must be returned in the same order as inputs."""
    ops = [
        {"method": "system.ping", "params": {}},
        {"method": "node.create", "params": {"parentPath": "/p", "type": "noiseCHOP", "name": "n1"}},
        {"method": "system.ping", "params": {}},
    ]
    results = await bridge.batch(ops)
    assert len(results) == 3
    # First and third are pings.
    assert results[0]["result"]["pong"] is True
    assert results[2]["result"]["pong"] is True
    # Second is node.create.
    assert results[1]["result"]["name"] == "n1"


@pytest.mark.asyncio
async def test_batch_without_connecting_raises() -> None:
    """Calling batch() before connect() must raise TDConnectionError."""
    td_bridge = TDBridge(host="127.0.0.1", port=9999, timeout=2.0)
    with pytest.raises(TDConnectionError):
        await td_bridge.batch([{"method": "system.ping", "params": {}}])


# ---------------------------------------------------------------------------
# Reconnection behaviour
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reconnect_on_disconnect(mock_server: tuple[str, int]) -> None:
    """When the server closes the connection the bridge should attempt reconnect.

    We verify that *after* the server forcefully closes the connection the
    bridge's reconnect loop fires at least one attempt.  Because the mock
    server is still up, the reconnect should succeed and connected should
    return to True.
    """
    host, port = mock_server
    td_bridge = TDBridge(
        host=host,
        port=port,
        timeout=5.0,
        reconnect_interval=0.05,  # Fast back-off for testing.
        max_reconnect_attempts=5,
    )
    await td_bridge.connect()
    assert td_bridge.connected is True

    # Force the underlying WebSocket closed without going through disconnect().
    ws = td_bridge._ws
    await ws.close()  # type: ignore[union-attr]

    # Give the reconnect task a moment to re-establish the connection.
    for _ in range(20):
        await asyncio.sleep(0.05)
        if td_bridge.connected:
            break

    assert td_bridge.connected is True, (
        "Bridge did not reconnect within 1 s after server dropped the connection"
    )

    await td_bridge.disconnect()
