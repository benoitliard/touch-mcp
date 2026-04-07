# Building TouchMCPBridge.tox

This guide walks through assembling the TouchDesigner bridge component from the source files in this directory and exporting it as a reusable `.tox` file.

The finished `.tox` hosts a WebSocket server inside TouchDesigner. touch-mcp connects to it over a persistent socket and routes every tool call through it.

---

## Prerequisites

- TouchDesigner 2024 or later (free non-commercial licence is sufficient)
- `callbacks.py` and `command_router.py` from this directory

---

## Step 1 — Create the container

1. Open TouchDesigner and create a new project (or open an existing one).
2. In the network editor, press **Tab** to open the operator palette.
3. Select **Base COMP** and place it in the network.
4. Double-click the new COMP to rename it `touch_mcp`.

---

## Step 2 — Add the WebSocket server

1. Double-click `touch_mcp` to enter the component.
2. Press **Tab**, search for **Web Server DAT**, and place it inside the COMP.
3. Rename it `webserver1`.
4. In the **Web Server DAT** parameter panel set:
   - **Port**: `9980`
   - **Active**: `On`

---

## Step 3 — Wire in the callback script

1. Press **Tab**, search for **Text DAT**, and place it inside the COMP.
2. Rename it `callbacks`.
3. Open `callbacks.py` from this directory, copy its entire contents, and paste them into the Text DAT's editor pane.
4. In the **Web Server DAT** (`webserver1`) parameter panel, set the **Callbacks DAT** field to `callbacks`.

---

## Step 4 — Add the command router module

1. Press **Tab**, add a second **Text DAT** inside the COMP.
2. Rename it `command_router`.
3. Open `command_router.py` from this directory, copy its contents, and paste them into this Text DAT.
4. In the Text DAT's parameter panel, enable **Module on Demand** (the toggle labelled **Module**). This makes the DAT importable as `mod.command_router` inside TouchDesigner Python.

---

## Step 5 — Add the log table

1. Press **Tab**, add a **Table DAT** inside the COMP.
2. Rename it `log`.
3. In the table, set the first row (the header row) to two cells: `timestamp` and `message`.

This table is written to by the callback script whenever the server starts, receives a message, or encounters an error. It is useful for debugging.

---

## Step 6 — Add custom parameters to the COMP

Custom parameters let you control the server from the COMP's parameter panel without diving into the network.

1. Navigate back up to the parent network so that `touch_mcp` is visible.
2. Right-click `touch_mcp` and choose **Edit Custom Parameters**.
3. Add the following parameters in a new page (name it, for example, `Server`):

   | Name | Type | Default | Purpose |
   |---|---|---|---|
   | `Port` | Int | `9980` | WebSocket port number |
   | `Active` | Toggle | `On` | Enable or disable the server |

4. Wire `Port` to the **Web Server DAT**:
   - Select `webserver1`, go to the **Port** parameter field, click the expression toggle (the small `=` button), and enter: `parent().par.Port`
5. Wire `Active` to the **Web Server DAT**:
   - Select `webserver1`, go to the **Active** parameter field, enable the expression, and enter: `parent().par.Active`

---

## Step 7 — Export the .tox file

1. Navigate back to the network containing `touch_mcp`.
2. Right-click the `touch_mcp` COMP.
3. Choose **Save Component .tox...**.
4. Save the file as `TouchMCPBridge.tox` in a location of your choice (for example, the project root alongside `pyproject.toml`).

---

## Step 8 — Verify

1. Ensure no other process is using port 9980.
2. The **Web Server DAT** (`webserver1`) should show **Active** in green.
3. Open the `log` Table DAT. Within a second or two it should display a row similar to:

   ```
   timestamp          message
   2024-01-15 12:00   Server started on port 9980
   ```

4. In a terminal, start the touch-mcp server:

   ```bash
   touch-mcp --debug
   ```

   You should see a log line confirming the WebSocket connection was established.

---

## Distributing the .tox

Once exported, `TouchMCPBridge.tox` is self-contained. Any TouchDesigner user can drag it into their project — no manual network-building required. The custom `Port` and `Active` parameters on the COMP surface are the only controls they need.
