"""Data-reading tools for TouchDesigner — CHOP, TOP, SOP, and DAT operators."""

from __future__ import annotations

import json

from mcp.server.fastmcp import Context

from touch_mcp.errors import TDConnectionError
from touch_mcp.server import mcp


@mcp.tool()
async def td_read_chop(
    path: str,
    channels: str | None = None,
    max_samples: int = 1000,
    ctx: Context = None,
) -> str:
    """Read channel data from a CHOP (Channel Operator) node.

    Retrieves sample values for one or more channels up to *max_samples*
    samples.  For time-sliced CHOPs only the current slice is returned.

    Args:
        path: Full path of the CHOP node (e.g. "/project1/noise1").
        channels: Comma-separated list of channel names to retrieve
                  (e.g. "chan1,tx,ty").  Omit to return all channels.
        max_samples: Maximum number of samples to return per channel
                     (default: 1000).  Capped server-side if the CHOP has
                     fewer samples.

    Returns:
        JSON object with:
        - "sampleRate": samples per second.
        - "numSamples": actual number of samples returned.
        - "channels": dict mapping channel name to list of float values.
    """
    bridge = ctx.request_context.lifespan_context["bridge"]
    if not bridge.connected:
        raise TDConnectionError("Not connected to TouchDesigner.")
    channel_list: list[str] | None = None
    if channels is not None:
        channel_list = [c.strip() for c in channels.split(",") if c.strip()]
    result = await bridge.request(
        "chop.read",
        {"path": path, "channels": channel_list, "maxSamples": max_samples},
    )
    return json.dumps(result)


@mcp.tool()
async def td_read_top(
    path: str,
    format: str = "png",
    max_width: int = 256,
    max_height: int = 256,
    ctx: Context = None,
) -> str:
    """Read pixel data from a TOP (Texture Operator) node as base64-encoded image data.

    The texture is rescaled to fit within *max_width* x *max_height* before
    encoding, preserving aspect ratio.  Use smaller dimensions for quick
    previews and larger ones when pixel accuracy is required.

    Args:
        path: Full path of the TOP node (e.g. "/project1/moviefilein1").
        format: Image encoding format — "png" (lossless) or "jpeg" (smaller,
                lossy).  Default: "png".
        max_width: Maximum output width in pixels (default: 256).
        max_height: Maximum output height in pixels (default: 256).

    Returns:
        JSON object with:
        - "width": actual pixel width of the returned image.
        - "height": actual pixel height of the returned image.
        - "format": encoding format used.
        - "data": base64-encoded image bytes.
    """
    bridge = ctx.request_context.lifespan_context["bridge"]
    if not bridge.connected:
        raise TDConnectionError("Not connected to TouchDesigner.")
    result = await bridge.request(
        "top.read",
        {"path": path, "format": format, "maxWidth": max_width, "maxHeight": max_height},
    )
    return json.dumps(result)


@mcp.tool()
async def td_read_sop(
    path: str,
    max_points: int = 1000,
    ctx: Context = None,
) -> str:
    """Read geometry data from a SOP (Surface Operator) node.

    Returns point positions, primitive counts, and normals/UVs where
    available.  Data is truncated to *max_points* points to avoid large
    payloads.

    Args:
        path: Full path of the SOP node (e.g. "/project1/sphere1").
        max_points: Maximum number of points to return (default: 1000).

    Returns:
        JSON object with:
        - "numPoints": total point count in the geometry.
        - "numPrimitives": total primitive count.
        - "points": list of {x, y, z} position objects (up to max_points).
        - "normals": list of {nx, ny, nz} objects if normals are present.
        - "uvs": list of {u, v, w} objects if texture coordinates are present.
    """
    bridge = ctx.request_context.lifespan_context["bridge"]
    if not bridge.connected:
        raise TDConnectionError("Not connected to TouchDesigner.")
    result = await bridge.request(
        "sop.read",
        {"path": path, "maxPoints": max_points},
    )
    return json.dumps(result)


@mcp.tool()
async def td_read_dat(
    path: str,
    row_range: str | None = None,
    ctx: Context = None,
) -> str:
    """Read text or table data from a DAT (Data Operator) node.

    For table DATs each row is returned as a list of cell strings.  For
    text DATs the full text content is returned as a single string.

    Args:
        path: Full path of the DAT node (e.g. "/project1/table1").
        row_range: Optional row slice in "start:end" format (zero-based,
                   exclusive end).  Examples:
                   - "0:10" returns the first 10 rows.
                   - "5:15" returns rows 5 through 14.
                   Omit to return all rows.

    Returns:
        JSON object with:
        - "type": "table" or "text".
        - "numRows": total number of rows (table DATs only).
        - "numCols": total number of columns (table DATs only).
        - "rows": list of row lists for table DATs, or plain string for
                  text DATs.
    """
    bridge = ctx.request_context.lifespan_context["bridge"]
    if not bridge.connected:
        raise TDConnectionError("Not connected to TouchDesigner.")
    start: int | None = None
    end: int | None = None
    if row_range is not None:
        parts = row_range.split(":")
        if len(parts) != 2:
            raise ValueError(
                f"'row_range' must be in 'start:end' format (e.g. '0:10'). Got: {row_range!r}"
            )
        try:
            start = int(parts[0])
            end = int(parts[1])
        except ValueError as exc:
            raise ValueError(
                f"'row_range' start and end must be integers. Got: {row_range!r}"
            ) from exc
    result = await bridge.request(
        "dat.read",
        {"path": path, "rowStart": start, "rowEnd": end},
    )
    return json.dumps(result)
