"""Quick live test — run with: python test_live.py"""

import asyncio
import json

from touch_mcp.bridge.connection import TDBridge


def pp(label, result):
    print(f"\n{'='*50}")
    print(f"  {label}")
    print(f"{'='*50}")
    print(json.dumps(result, indent=2))


async def main():
    bridge = TDBridge("localhost", 9980, 5.0)
    await bridge.connect()
    print("Connected to TouchDesigner!\n")

    # --- System ---
    r = await bridge.request("system.ping", {})
    pp("system.ping", r)

    r = await bridge.request("project.info", {})
    pp("project.info", r)

    # --- Create nodes ---
    r = await bridge.request("node.create", {
        "parentPath": "/project1",
        "type": "noiseCHOP",
        "name": "my_noise",
    })
    pp("node.create (noiseCHOP)", r)

    r = await bridge.request("node.create", {
        "parentPath": "/project1",
        "type": "filterCHOP",
        "name": "my_filter",
    })
    pp("node.create (filterCHOP)", r)

    # --- Wire them ---
    r = await bridge.request("conn.create", {
        "fromPath": "/project1/my_noise",
        "toPath": "/project1/my_filter",
        "fromOutput": 0,
        "toInput": 0,
    })
    pp("conn.create (noise -> filter)", r)

    # --- Read connections ---
    r = await bridge.request("conn.get", {
        "path": "/project1/my_filter",
    })
    pp("conn.get (my_filter)", r)

    # --- Read CHOP data ---
    r = await bridge.request("data.chop", {
        "path": "/project1/my_noise",
        "max_samples": 10,
    })
    pp("data.chop (my_noise, 10 samples)", r)

    # --- Set parameters ---
    r = await bridge.request("par.set", {
        "path": "/project1/my_noise",
        "values": {"roughness": 0.5, "amp": 2.0},
    })
    pp("par.set (roughness=0.5, amp=2.0)", r)

    # --- Get parameters ---
    r = await bridge.request("par.get", {
        "path": "/project1/my_noise",
        "pattern": "rough*",
    })
    pp("par.get (rough*)", r)

    # --- List nodes ---
    r = await bridge.request("node.list", {
        "path": "/project1",
    })
    pp("node.list (/project1)", r)

    # --- Batch: create + wire 3 nodes in one round-trip ---
    r = await bridge.batch([
        {"id": 100, "method": "node.create", "params": {
            "parentPath": "/project1", "type": "waveCHOP", "name": "wave1"}},
        {"id": 101, "method": "node.create", "params": {
            "parentPath": "/project1", "type": "mathCHOP", "name": "math1"}},
        {"id": 102, "method": "conn.create", "params": {
            "fromPath": "/project1/wave1",
            "toPath": "/project1/math1",
            "fromOutput": 0, "toInput": 0}},
    ])
    pp("BATCH (create wave + math + wire)", r)

    # --- Timeline ---
    r = await bridge.request("timeline.get", {})
    pp("timeline.get", r)

    # --- Cleanup: delete test nodes ---
    for name in ["my_filter", "my_noise", "math1", "wave1"]:
        await bridge.request("node.delete", {"path": f"/project1/{name}"})
    print("\n  Cleanup: deleted test nodes")

    await bridge.disconnect()
    print("\nDone!")


asyncio.run(main())
