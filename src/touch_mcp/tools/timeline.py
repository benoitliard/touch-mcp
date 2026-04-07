"""Timeline control tools for TouchDesigner — playback, frame, and range management."""

from __future__ import annotations

import json

from mcp.server.fastmcp import Context

from touch_mcp.errors import TDConnectionError
from touch_mcp.server import mcp


@mcp.tool()
async def td_timeline_get(ctx: Context = None) -> str:
    """Get the current TouchDesigner timeline state.

    Returns a snapshot of the global timeline including the current frame,
    playback state, configured frame rate, and start/end range.

    Returns:
        JSON object with:
        - "frame": current frame number (float).
        - "playing": true if the timeline is currently playing.
        - "fps": configured frames per second.
        - "start": timeline start frame.
        - "end": timeline end frame.
        - "loop": true if loop playback is enabled.
    """
    bridge = ctx.request_context.lifespan_context["bridge"]
    if not bridge.connected:
        raise TDConnectionError("Not connected to TouchDesigner.")
    result = await bridge.request("timeline.get", {})
    return json.dumps(result)


@mcp.tool()
async def td_timeline_set(
    frame: int | None = None,
    fps: float | None = None,
    start: int | None = None,
    end: int | None = None,
    loop: bool | None = None,
    ctx: Context = None,
) -> str:
    """Set one or more TouchDesigner timeline properties.

    All arguments are optional — only the values you supply are changed.
    Supplying no arguments is a no-op that returns the current state.

    Args:
        frame: Jump to this frame number.
        fps: Set the global frame rate (e.g. 30.0, 60.0).
        start: Set the timeline start frame.
        end: Set the timeline end frame.
        loop: Enable (True) or disable (False) looped playback.

    Returns:
        JSON object reflecting the timeline state after the update.
    """
    bridge = ctx.request_context.lifespan_context["bridge"]
    if not bridge.connected:
        raise TDConnectionError("Not connected to TouchDesigner.")
    params: dict = {}
    if frame is not None:
        params["frame"] = frame
    if fps is not None:
        params["fps"] = fps
    if start is not None:
        params["start"] = start
    if end is not None:
        params["end"] = end
    if loop is not None:
        params["loop"] = loop
    result = await bridge.request("timeline.set", params)
    return json.dumps(result)


@mcp.tool()
async def td_timeline_play(ctx: Context = None) -> str:
    """Start TouchDesigner timeline playback.

    Equivalent to pressing the Play button in the timeline controls.
    Has no effect if the timeline is already playing.

    Returns:
        JSON object confirming playback started with the current frame.
    """
    bridge = ctx.request_context.lifespan_context["bridge"]
    if not bridge.connected:
        raise TDConnectionError("Not connected to TouchDesigner.")
    result = await bridge.request("timeline.play", {})
    return json.dumps(result)


@mcp.tool()
async def td_timeline_pause(ctx: Context = None) -> str:
    """Pause TouchDesigner timeline playback.

    Equivalent to pressing the Pause button in the timeline controls.
    Has no effect if the timeline is already paused.

    Returns:
        JSON object confirming playback paused with the current frame.
    """
    bridge = ctx.request_context.lifespan_context["bridge"]
    if not bridge.connected:
        raise TDConnectionError("Not connected to TouchDesigner.")
    result = await bridge.request("timeline.pause", {})
    return json.dumps(result)
