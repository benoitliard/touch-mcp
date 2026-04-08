"""Async WebSocket client bridge to TouchDesigner."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import websockets
from websockets.asyncio.client import ClientConnection, connect

from touch_mcp.bridge.protocol import make_batch, make_request, parse_response
from touch_mcp.errors import TDConnectionError, TDTimeoutError

logger = logging.getLogger(__name__)

# Seconds between automatic keepalive pings (delegated to websockets layer).
_PING_INTERVAL: float = 5.0
# Maximum cap for exponential back-off between reconnection attempts.
_BACKOFF_CAP: float = 30.0


class TDBridge:
    """Async WebSocket client that speaks the TouchDesigner request/response protocol.

    The bridge maintains a single persistent WebSocket connection and exposes
    two public coroutines for callers:

    * :meth:`request` — send a single method call and await its response.
    * :meth:`batch` — send multiple calls in one round-trip and receive all
      responses as a list.

    On connection loss the bridge attempts automatic reconnection with
    exponential back-off, up to *max_reconnect_attempts* tries.

    Args:
        host: Hostname or IP of the TouchDesigner WebSocket server.
        port: TCP port of the TouchDesigner WebSocket server.
        timeout: Default request timeout in seconds.  Individual calls may
            override this via the *timeout* keyword argument of
            :meth:`request`.
        reconnect_interval: Base interval (seconds) for the first reconnection
            delay.  Subsequent attempts double this value up to
            ``_BACKOFF_CAP``.
        max_reconnect_attempts: Maximum number of consecutive reconnection
            attempts before giving up and raising :class:`TDConnectionError`.

    Example::

        bridge = TDBridge("localhost", 9980, timeout=30.0)
        await bridge.connect()
        result = await bridge.request("par.get", {"node": "/project1/base1", "name": "tx"})
        await bridge.disconnect()
    """

    def __init__(
        self,
        host: str,
        port: int,
        timeout: float,
        reconnect_interval: float = 2.0,
        max_reconnect_attempts: int = 10,
    ) -> None:
        self._host = host
        self._port = port
        self._timeout = timeout
        self._reconnect_interval = reconnect_interval
        self._max_reconnect_attempts = max_reconnect_attempts

        self._url = f"ws://{host}:{port}"

        self._ws: ClientConnection | None = None
        self._recv_task: asyncio.Task[None] | None = None
        self._pending: dict[int, asyncio.Future[dict[str, Any]]] = {}
        self._next_id: int = 1
        self._connected: bool = False
        # Set when the bridge should stop all background activity.
        self._closing: bool = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def connected(self) -> bool:
        """``True`` while a live WebSocket connection is established."""
        return self._connected

    async def connect(self) -> None:
        """Establish the WebSocket connection and start the receive loop.

        Raises:
            TDConnectionError: If the initial connection attempt fails.
        """
        self._closing = False
        await self._open_connection()
        logger.info("TDBridge connected to %s", self._url)

    async def _wait_connected(self) -> None:
        """Poll until the bridge is connected again (used during reconnection)."""
        while not self._connected:
            if self._closing:
                raise TDConnectionError("Bridge is shutting down.")
            await asyncio.sleep(0.1)

    async def disconnect(self) -> None:
        """Gracefully close the WebSocket connection and cancel background tasks.

        Any pending requests are cancelled with a :class:`TDConnectionError`.
        This method is idempotent.
        """
        self._closing = True
        self._connected = False

        # Cancel the receive task first so it does not race with close.
        if self._recv_task is not None and not self._recv_task.done():
            self._recv_task.cancel()
            try:
                await self._recv_task
            except (asyncio.CancelledError, Exception):
                pass
            self._recv_task = None

        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None

        self._cancel_pending("Bridge disconnected cleanly.")
        logger.info("TDBridge disconnected from %s", self._url)

    async def request(
        self,
        method: str,
        params: dict[str, Any],
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Send a single request and return the corresponding response dict.

        Args:
            method: TouchDesigner method name (e.g. ``"par.set"``).
            params: Method parameters.
            timeout: Per-call timeout override in seconds.  Falls back to the
                bridge-level default when ``None``.

        Returns:
            The parsed response dict returned by TouchDesigner.

        Raises:
            TDConnectionError: If the bridge is not connected.
            TDTimeoutError: If no response is received within *timeout* seconds.
        """
        if not self._connected or self._ws is None:
            # Wait briefly for reconnection before giving up
            if not self._closing:
                try:
                    await asyncio.wait_for(self._wait_connected(), timeout=5.0)
                except asyncio.TimeoutError:
                    raise TDConnectionError(
                        "Not connected to TouchDesigner. Reconnection timed out."
                    )
            else:
                raise TDConnectionError("Not connected to TouchDesigner.")

        req_id = self._next_id
        self._next_id += 1

        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        self._pending[req_id] = future

        payload = make_request(method, params, req_id)
        try:
            await self._ws.send(payload)
        except Exception as exc:
            self._pending.pop(req_id, None)
            future.cancel()
            # Connection is dead — trigger reconnection
            if self._connected and not self._closing:
                self._connected = False
                self._cancel_pending(f"Send failed: {exc}")
                asyncio.create_task(self._reconnect(), name="td-bridge-reconnect")
            raise TDConnectionError(f"Send failed: {exc}") from exc

        effective_timeout = timeout if timeout is not None else self._timeout
        try:
            return await asyncio.wait_for(future, timeout=effective_timeout)
        except asyncio.TimeoutError:
            self._pending.pop(req_id, None)
            raise TDTimeoutError(
                f"Request '{method}' (id={req_id}) timed out after {effective_timeout}s."
            )

    async def batch(
        self,
        requests: list[dict[str, Any]],
        timeout: float | None = None,
    ) -> list[dict[str, Any]]:
        """Send a batch of requests and return all responses in id order.

        Each element of *requests* must be a plain dict with ``"method"`` and
        ``"params"`` keys.  The bridge assigns request ids automatically.

        Args:
            requests: List of ``{"method": ..., "params": ...}`` dicts.
            timeout: Per-call timeout override applied to the whole batch wait.

        Returns:
            List of response dicts in the same order as the input requests.

        Raises:
            TDConnectionError: If the bridge is not connected.
            TDTimeoutError: If the batch response is not received in time.
        """
        if not self._connected or self._ws is None:
            if not self._closing:
                try:
                    await asyncio.wait_for(self._wait_connected(), timeout=5.0)
                except asyncio.TimeoutError:
                    raise TDConnectionError(
                        "Not connected to TouchDesigner. Reconnection timed out."
                    )
            else:
                raise TDConnectionError("Not connected to TouchDesigner.")

        if not requests:
            return []

        loop = asyncio.get_running_loop()
        tagged: list[dict[str, Any]] = []
        futures: dict[int, asyncio.Future[dict[str, Any]]] = {}

        for req in requests:
            req_id = self._next_id
            self._next_id += 1
            future: asyncio.Future[dict[str, Any]] = loop.create_future()
            self._pending[req_id] = future
            futures[req_id] = future
            tagged.append({"id": req_id, "method": req["method"], "params": req["params"]})

        payload = make_batch(tagged)
        try:
            await self._ws.send(payload)
        except Exception as exc:
            for req_id, future in futures.items():
                self._pending.pop(req_id, None)
                if not future.done():
                    future.cancel()
            if self._connected and not self._closing:
                self._connected = False
                self._cancel_pending(f"Batch send failed: {exc}")
                asyncio.create_task(self._reconnect(), name="td-bridge-reconnect")
            raise TDConnectionError(f"Batch send failed: {exc}") from exc

        effective_timeout = timeout if timeout is not None else self._timeout
        try:
            results = await asyncio.wait_for(
                asyncio.gather(*futures.values()),
                timeout=effective_timeout,
            )
        except asyncio.TimeoutError:
            for req_id in futures:
                self._pending.pop(req_id, None)
            raise TDTimeoutError(
                f"Batch of {len(requests)} request(s) timed out after {effective_timeout}s."
            )

        # Return responses in the original request order.
        return [result for result in results]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _open_connection(self) -> None:
        """Open the WebSocket and launch the receive loop.

        Raises:
            TDConnectionError: If the connection attempt fails.
        """
        try:
            self._ws = await connect(
                self._url,
                ping_interval=_PING_INTERVAL,
                ping_timeout=_PING_INTERVAL * 2,
            )
        except Exception as exc:
            raise TDConnectionError(
                f"Failed to connect to TouchDesigner at {self._url}: {exc}"
            ) from exc

        self._connected = True
        self._recv_task = asyncio.create_task(
            self._recv_loop(), name="td-bridge-recv"
        )

    async def _recv_loop(self) -> None:
        """Background task: read messages from the WebSocket and resolve pending futures.

        When the connection is lost the loop triggers reconnection unless the
        bridge is shutting down.
        """
        assert self._ws is not None  # guaranteed by _open_connection

        try:
            async for raw in self._ws:
                self._dispatch(raw)  # type: ignore[arg-type]
        except asyncio.CancelledError:
            logger.debug("Receive loop cancelled.")
            raise
        except websockets.exceptions.ConnectionClosed as exc:
            if self._closing:
                logger.debug("Connection closed during shutdown: %s", exc)
                return
            logger.warning("Connection to %s lost: %s — reconnecting…", self._url, exc)
            self._connected = False
            self._cancel_pending("Connection lost; pending requests cancelled.")
            asyncio.create_task(self._reconnect(), name="td-bridge-reconnect")
        except Exception as exc:
            logger.error("Unexpected error in receive loop: %s", exc, exc_info=True)
            if not self._closing:
                self._connected = False
                self._cancel_pending(f"Receive loop error: {exc}")
                asyncio.create_task(self._reconnect(), name="td-bridge-reconnect")

    def _dispatch(self, raw: str) -> None:
        """Route a raw message to the correct pending future(s).

        Handles both single-response objects and batch-response arrays.

        Args:
            raw: Raw JSON string received from the WebSocket.
        """
        try:
            parsed = parse_response(raw)
        except Exception as exc:
            logger.warning("Could not parse response: %s — raw=%r", exc, raw)
            return

        responses: list[dict[str, Any]] = (
            parsed if isinstance(parsed, list) else [parsed]
        )

        for response in responses:
            req_id = response.get("id")
            if req_id is None:
                logger.debug("Received response without id, ignoring: %r", response)
                continue

            future = self._pending.pop(req_id, None)
            if future is None:
                logger.debug("No pending request for id=%s, ignoring.", req_id)
                continue

            if not future.done():
                future.set_result(response)

    async def _reconnect(self) -> None:
        """Attempt to re-establish the connection using exponential back-off.

        Tries up to *max_reconnect_attempts* times.  On exhaustion, logs a
        critical error — callers holding outstanding requests will already have
        received a :class:`TDConnectionError` via :meth:`_cancel_pending`.
        """
        delay = self._reconnect_interval
        for attempt in range(1, self._max_reconnect_attempts + 1):
            if self._closing:
                return

            logger.info(
                "Reconnection attempt %d/%d in %.1fs…",
                attempt,
                self._max_reconnect_attempts,
                delay,
            )
            await asyncio.sleep(delay)

            if self._closing:
                return

            try:
                await self._open_connection()
                logger.info("Reconnected to %s after %d attempt(s).", self._url, attempt)
                return
            except TDConnectionError as exc:
                logger.warning("Reconnection attempt %d failed: %s", attempt, exc)
                delay = min(delay * 2, _BACKOFF_CAP)

        logger.critical(
            "Exhausted %d reconnection attempts to %s — giving up.",
            self._max_reconnect_attempts,
            self._url,
        )

    def _cancel_pending(self, reason: str) -> None:
        """Reject all currently pending request futures with a :class:`TDConnectionError`.

        Args:
            reason: Human-readable explanation surfaced in the exception message.
        """
        error = TDConnectionError(reason)
        for req_id, future in list(self._pending.items()):
            if not future.done():
                future.set_exception(error)
        self._pending.clear()
