"""Render and screenshot tools for TouchDesigner — capture and export imagery."""

from __future__ import annotations

import json

from mcp.server.fastmcp import Context

from touch_mcp.errors import TDConnectionError
from touch_mcp.server import mcp


@mcp.tool()
async def td_screenshot(
    path: str,
    save_path: str | None = None,
    ctx: Context = None,
) -> str:
    """Save a TOP's current frame as a PNG file on disk.

    The image is saved on the machine running TouchDesigner.
    Returns the file path (NOT the image data) to avoid blocking TD.

    Args:
        path: Full path of the TOP to capture (e.g. "/project1/render1").
        save_path: Optional file path to save the PNG. If omitted, saves
                   to a temp file in /tmp/.

    Returns:
        JSON object with:
        - "path": TOP operator path.
        - "savedTo": file path where the PNG was saved.
        - "fileSize": file size in bytes.
        - "width": pixel width.
        - "height": pixel height.
    """
    bridge = ctx.request_context.lifespan_context["bridge"]
    if not bridge.connected:
        raise TDConnectionError("Not connected to TouchDesigner.")
    result = await bridge.request(
        "render.screenshot",
        {"path": path, "save_path": save_path},
    )
    return json.dumps(result)


@mcp.tool()
async def td_export_render(
    path: str,
    output_path: str,
    format: str = "png",
    ctx: Context = None,
) -> str:
    """Export a rendered frame from a TouchDesigner TOP to a file on disk.

    Renders the TOP at *path* and writes the result to *output_path* on the
    machine running TouchDesigner (not the MCP host, unless they are the
    same machine).

    Args:
        path: Full path of the source TOP node (e.g. "/project1/render1").
        output_path: Absolute file path on the TouchDesigner machine where the
                     image should be saved (e.g. "C:/renders/frame001.png" or
                     "/Users/me/renders/frame001.png").
        format: File format to write — "png", "jpeg", "tiff", or "exr"
                (default: "png").  EXR is only available when the TOP outputs
                floating-point data.

    Returns:
        JSON object with:
        - "outputPath": the path the file was written to.
        - "width": pixel width of the exported image.
        - "height": pixel height of the exported image.
        - "format": file format used.
    """
    bridge = ctx.request_context.lifespan_context["bridge"]
    if not bridge.connected:
        raise TDConnectionError("Not connected to TouchDesigner.")
    result = await bridge.request(
        "render.export",
        {"path": path, "outputPath": output_path, "format": format},
    )
    return json.dumps(result)
