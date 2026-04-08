"""Quick live test — run with: python test_live.py"""

import asyncio
import json

from touch_mcp.bridge.connection import TDBridge


async def main():
    bridge = TDBridge("localhost", 9980, 5.0)
    await bridge.connect()
    print("Connected!\n")

    result = await bridge.request("system.ping", {})
    print("Ping:", json.dumps(result, indent=2))

    result = await bridge.request("project.info", {})
    print("\nProject:", json.dumps(result, indent=2))

    await bridge.disconnect()
    print("\nDone.")


asyncio.run(main())
