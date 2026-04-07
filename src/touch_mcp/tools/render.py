"""Render and screenshot tools for TouchDesigner — capture and export imagery."""

from __future__ import annotations

import json

from mcp.server.fastmcp import Context

from touch_mcp.errors import TDConnectionError
from touch_mcp.server import mcp


@mcp.tool()
async def td_screenshot(
    path: str | None = None,
    width: int = 1920,
    height: int = 1080,
    ctx: Context = None,
) -> str:
    """Capture a screenshot of a TouchDesigner TOP or network pane.

    When *path* is a TOP operator path the texture is rendered directly at the
    requested resolution.  When *path* is a network path (COMP) the network
    editor view for that component is captured.  Omitting *path* captures the
    main TouchDesigner window.

    Args:
        path: Full path of the TOP or COMP to capture.  Omit to screenshot
              the main window.
        width: Output image width in pixels (default: 1920).
        height: Output image height in pixels (default: 1080).

    Returns:
        JSON object with:
        - "width": actual pixel width of the captured image.
        - "height": actual pixel height of the captured image.
        - "format": image encoding format (always "png").
        - "data": base64-encoded PNG image bytes.
    """
    bridge = ctx.request_context.lifespan_context["bridge"]
    if not bridge.connected:
        raise TDConnectionError("Not connected to TouchDesigner.")
    result = await bridge.request(
        "render.screenshot",
        {"path": path, "width": width, "height": height},
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
