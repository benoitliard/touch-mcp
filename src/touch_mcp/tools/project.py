"""Project-level tools for TouchDesigner — info and save operations."""

from __future__ import annotations

import json

from mcp.server.fastmcp import Context

from touch_mcp.errors import TDConnectionError
from touch_mcp.server import mcp


@mcp.tool()
async def td_project_info(ctx: Context = None) -> str:
    """Get metadata about the currently open TouchDesigner project.

    Returns identifying information about the TD instance and active project,
    including the application build number and current FPS performance.

    Returns:
        JSON object with:
        - "name": project name (filename without extension).
        - "path": absolute path to the .toe file on disk, or null if unsaved.
        - "fps": current realtime frames-per-second as measured by TD.
        - "targetFps": configured target frame rate.
        - "build": TouchDesigner build number string (e.g. "2023.11760").
        - "version": TouchDesigner version string (e.g. "2023.11").
        - "platform": operating system platform string.
    """
    bridge = ctx.request_context.lifespan_context["bridge"]
    if not bridge.connected:
        raise TDConnectionError("Not connected to TouchDesigner.")
    result = await bridge.request("project.info", {})
    return json.dumps(result)


@mcp.tool()
async def td_project_save(
    path: str | None = None,
    ctx: Context = None,
) -> str:
    """Save the current TouchDesigner project to disk.

    When *path* is omitted the project is saved to its current file location
    (equivalent to Ctrl+S).  Supply *path* to perform a Save As and write the
    project to a new location (equivalent to Ctrl+Shift+S).

    Args:
        path: Absolute path for Save As (e.g. "/Users/me/projects/new.toe").
              Omit to save in place.  The path must end in ".toe".

    Returns:
        JSON object with:
        - "savedPath": absolute path where the project was saved.
        - "success": true if the save completed without errors.
    """
    bridge = ctx.request_context.lifespan_context["bridge"]
    if not bridge.connected:
        raise TDConnectionError("Not connected to TouchDesigner.")
    result = await bridge.request("project.save", {"path": path})
    return json.dumps(result)
