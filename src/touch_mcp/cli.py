"""CLI entry point for the touch-mcp server."""

from __future__ import annotations

import argparse
import logging


def main() -> None:
    """Parse CLI arguments and start the MCP server."""
    parser = argparse.ArgumentParser(
        prog="touch-mcp",
        description="High-performance MCP server for TouchDesigner — live control via WebSocket",
    )
    parser.add_argument(
        "--td-host",
        default="localhost",
        help="TouchDesigner WebSocket host (default: localhost)",
    )
    parser.add_argument(
        "--td-port",
        default=9980,
        type=int,
        help="TouchDesigner WebSocket port (default: 9980)",
    )
    parser.add_argument(
        "--timeout",
        default=30.0,
        type=float,
        help="Request timeout in seconds (default: 30.0)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    from touch_mcp.server import run_server

    run_server(args.td_host, args.td_port, args.timeout)
