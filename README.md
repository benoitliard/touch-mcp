# touch-mcp

![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
![License MIT](https://img.shields.io/badge/license-MIT-green)

**High-performance MCP server for TouchDesigner — live control via WebSocket from any MCP-compatible AI (Claude, etc.)**

```
Claude/LLM ←── stdio (MCP) ──→ touch-mcp ←── WebSocket ──→ TouchDesigner (.tox)
```

---

## Why touch-mcp

The most comprehensive MCP server for TouchDesigner available. Unlike simpler alternatives, touch-mcp offers:

- **Persistent WebSocket connection** — every tool call is a lightweight message, not a full HTTP round-trip
- **29 tools** covering nodes, parameters, connections, data access, scripting, timeline, rendering, layout, and more
- **Batching** — bundle multiple operations into a single round-trip with `td_batch`, critical for building complex networks fast
- **Auto-reconnection** — survives TD restarts and network hiccups
- **Auto-positioning** — new nodes are placed intelligently in the network editor
- **Full Python access** — execute arbitrary Python inside TD with `td_execute_script`, with access to all operator types and globals

---

## Quick Start

**1. Install touch-mcp**

```bash
pip install touch-mcp
```

Or from source:

```bash
git clone https://github.com/benoitliard/touch-mcp.git
cd touch-mcp
pip install -e ".[dev]"
```

**2. Install the TouchDesigner bridge component**

Open TouchDesigner (2024+), then drag `TouchMCPBridge.tox` from the `td/` folder into your project. The component starts a WebSocket server on port 9980 automatically.

For instructions on building the `.tox` from source, see [`td/BUILD_TOX.md`](td/BUILD_TOX.md).

**3. Configure your MCP client**

See the configuration sections below, then start a conversation — touch-mcp connects to TouchDesigner on first use.

---

## Configuration

### Claude Desktop

Add the following to your `claude_desktop_config.json`:

```json
{
    "mcpServers": {
        "touchdesigner": {
            "command": "touch-mcp",
            "args": ["--td-port", "9980"]
        }
    }
}
```

The config file is located at:
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

### Claude Code

Create or edit `.mcp.json` in your project root:

```json
{
    "mcpServers": {
        "touchdesigner": {
            "command": "touch-mcp",
            "args": ["--td-host", "localhost", "--td-port", "9980", "--timeout", "30"]
        }
    }
}
```

---

## Available Tools

29 tools organised by category.

### Nodes

| Tool | Description |
|---|---|
| `td_create_node` | Create a new operator node inside a parent container |
| `td_delete_node` | Delete a node and all its children |
| `td_list_nodes` | List child nodes under a path, optionally filtered by family |
| `td_get_node` | Get detailed metadata for a node (type, position, connections) |

### Parameters

| Tool | Description |
|---|---|
| `td_get_parameters` | Read current parameter values for a node |
| `td_set_parameters` | Set one or more parameter values on a node |
| `td_get_parameter_info` | Get parameter schema (style, range, menu options, defaults) |

### Connections

| Tool | Description |
|---|---|
| `td_create_connection` | Wire two nodes together by output and input index |
| `td_delete_connection` | Disconnect a node's input or output connector |
| `td_get_connections` | List all wires entering and leaving a node |

### Data

| Tool | Description |
|---|---|
| `td_read_chop` | Read channel sample data from a CHOP node |
| `td_read_top` | Read a TOP texture as base64-encoded image data |
| `td_read_sop` | Read point and primitive geometry from a SOP node |
| `td_read_dat` | Read text or table contents from a DAT node |

### Scripts

| Tool | Description |
|---|---|
| `td_execute_script` | Execute arbitrary Python inside the live TouchDesigner instance |
| `td_class_list` | List all TD Python classes available in the environment |
| `td_class_detail` | Inspect methods and properties of a TD Python class |
| `td_module_help` | Get `help()` output for any TD Python module |

### Timeline

| Tool | Description |
|---|---|
| `td_timeline_get` | Get the current timeline state (frame, fps, range, loop) |
| `td_timeline_set` | Set one or more timeline properties (frame, fps, range, loop) |
| `td_timeline_play` | Start timeline playback |
| `td_timeline_pause` | Pause timeline playback |

### Render

| Tool | Description |
|---|---|
| `td_screenshot` | Save a TOP's current frame as a PNG file on disk |
| `td_export_render` | Export a rendered TOP frame to a file on disk |

### Project

| Tool | Description |
|---|---|
| `td_project_info` | Get project metadata (name, path, fps, TD build/version) |
| `td_project_save` | Save the project in place or to a new path |

### Layout

| Tool | Description |
|---|---|
| `td_set_node_position` | Set network-editor x/y positions for one or more nodes |
| `td_align_nodes` | Evenly distribute nodes along a horizontal or vertical axis |

### Batch

| Tool | Description |
|---|---|
| `td_batch` | Execute multiple operations in a single WebSocket round-trip |

---

## CLI Options

```
touch-mcp [OPTIONS]

Options:
  --td-host TEXT    TouchDesigner WebSocket host (default: localhost)
  --td-port INT     TouchDesigner WebSocket port (default: 9980)
  --timeout FLOAT   Per-request timeout in seconds (default: 30.0)
  --debug           Enable debug logging
```

---

## Development

```bash
git clone https://github.com/benoitliard/touch-mcp.git
cd touch-mcp
pip install -e ".[dev]"
pytest
```

Static analysis:

```bash
ruff check src/
```

---

## License

MIT
