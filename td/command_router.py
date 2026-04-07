"""
Command router for touch-mcp — main thread handler.

This module runs inside TouchDesigner on the main thread. All TouchDesigner
globals (op, ops, parent, project, absTime, app, ui, me, td, tdu) are
available without import.

Protocol:  JSON-RPC-style envelopes
  Request:  {"id": <int>, "method": "<domain>.<action>", "params": {...}}
  Batch:    [<request>, ...]
  Response: {"id": <int>, "ok": true,  "result": {...}}
  Error:    {"id": <int>, "ok": false, "error": {"code": "<CODE>", "message": "<text>"}}

The WebServer DAT is expected to be a sibling op named "webserver1".
The log Table DAT is expected to be a sibling op named "log".
"""

import base64
import inspect
import io
import json
import traceback

# ---------------------------------------------------------------------------
# Error codes
# ---------------------------------------------------------------------------

NODE_NOT_FOUND   = "NODE_NOT_FOUND"
OP_CREATE_FAILED = "OP_CREATE_FAILED"
INVALID_PARAMS   = "INVALID_PARAMS"
PARAMETER_ERROR  = "PARAMETER_ERROR"
CONNECTION_ERROR = "CONNECTION_ERROR"
DATA_ACCESS_ERROR = "DATA_ACCESS_ERROR"
TIMELINE_ERROR   = "TIMELINE_ERROR"
PROJECT_ERROR    = "PROJECT_ERROR"
SCRIPT_ERROR     = "SCRIPT_ERROR"
INTERNAL_ERROR   = "INTERNAL_ERROR"
PARSE_ERROR      = "PARSE_ERROR"
METHOD_NOT_FOUND = "METHOD_NOT_FOUND"
INVALID_REQUEST  = "INVALID_REQUEST"


class MCPError(Exception):
    """Structured error raised by handlers, converted to an error envelope."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# ---------------------------------------------------------------------------
# Handler registry
# ---------------------------------------------------------------------------

_handlers = {}


def handler(method: str):
    """Decorator that registers a function as the handler for *method*."""
    def _decorator(fn):
        _handlers[method] = fn
        return fn
    return _decorator


# ---------------------------------------------------------------------------
# Connection state
# ---------------------------------------------------------------------------

_connected_clients = set()


def _on_client_connect(client):
    """Called (on the main thread) when a WebSocket client connects."""
    _connected_clients.add(client)
    _log(f"Client connected: {client}")


def _on_client_disconnect(client):
    """Called (on the main thread) when a WebSocket client disconnects."""
    _connected_clients.discard(client)
    _log(f"Client disconnected: {client}")


# ---------------------------------------------------------------------------
# Core dispatch
# ---------------------------------------------------------------------------

def process_request(client, data: str):
    """Entry-point called by td.run() from the WebSocket thread.

    Parses the incoming JSON payload, dispatches each request to its handler,
    and sends one response (or a batch of responses) back via the WebServer DAT.

    Args:
        client: Opaque client identifier passed by the WebServer DAT.
        data:   Raw JSON text received from the client.
    """
    try:
        payload = json.loads(data)
    except json.JSONDecodeError as exc:
        _send(client, _error_envelope(None, PARSE_ERROR, f"Invalid JSON: {exc}"))
        return

    if isinstance(payload, list):
        # Batch request
        responses = []
        for item in payload:
            responses.append(_dispatch_single(item))
        _send(client, json.dumps(responses))
    elif isinstance(payload, dict):
        _send(client, _dispatch_single(payload))
    else:
        _send(client, _error_envelope(None, INVALID_REQUEST, "Request must be an object or array."))


def _dispatch_single(request: dict) -> str:
    """Dispatch one request object; always returns a JSON string."""
    req_id  = request.get("id")
    method  = request.get("method")
    params  = request.get("params", {})

    if not isinstance(method, str) or not method:
        return _error_envelope(req_id, INVALID_REQUEST, "Missing or invalid 'method' field.")

    if not isinstance(params, dict):
        return _error_envelope(req_id, INVALID_PARAMS, "'params' must be an object.")

    handler_fn = _handlers.get(method)
    if handler_fn is None:
        return _error_envelope(req_id, METHOD_NOT_FOUND, f"Unknown method: {method!r}")

    try:
        result = handler_fn(params)
        return json.dumps({"id": req_id, "ok": True, "result": result}, default=_json_fallback)
    except MCPError as exc:
        return _error_envelope(req_id, exc.code, exc.message)
    except Exception as exc:
        tb = traceback.format_exc()
        _log(f"INTERNAL_ERROR in {method!r}: {exc}\n{tb}")
        return _error_envelope(req_id, INTERNAL_ERROR, f"Unhandled exception: {exc}")


def _error_envelope(req_id, code: str, message: str) -> str:
    return json.dumps({"id": req_id, "ok": False, "error": {"code": code, "message": message}})


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

def _resolve_op(path: str):
    """Return the operator at *path*, or raise MCPError if not found."""
    node = op(path)
    if node is None:
        raise MCPError(NODE_NOT_FOUND, f"No operator found at path: {path!r}")
    return node


def _serialize_node(node) -> dict:
    """Full node serialization including params, connections, children count."""
    try:
        inputs = []
        for i, conn in enumerate(node.inputConnectors):
            for c in conn.connections:
                inputs.append({
                    "inputIndex": i,
                    "fromPath": c.owner.path,
                    "fromOutput": c.index,
                })
        outputs = []
        for i, conn in enumerate(node.outputConnectors):
            for c in conn.connections:
                outputs.append({
                    "outputIndex": i,
                    "toPath": c.owner.path,
                    "toInput": c.index,
                })
    except Exception:
        inputs = []
        outputs = []

    try:
        params = {p.name: _serialize_par(p) for p in node.pars()}
    except Exception:
        params = {}

    try:
        children_count = len(node.children)
    except Exception:
        children_count = 0

    return {
        "path": node.path,
        "name": node.name,
        "type": node.type,
        "family": node.family,
        "nodeX": node.nodeX,
        "nodeY": node.nodeY,
        "inputs": inputs,
        "outputs": outputs,
        "params": params,
        "childrenCount": children_count,
    }


def _serialize_node_brief(node) -> dict:
    """Minimal node descriptor — used for list results."""
    return {
        "path": node.path,
        "name": node.name,
        "type": node.type,
        "family": node.family,
    }


def _serialize_par(par) -> dict:
    """Serialize a single parameter to a metadata dict."""
    try:
        val = par.eval()
    except Exception:
        val = None

    result = {
        "name": par.name,
        "label": par.label,
        "value": val,
        "mode": str(par.mode),
        "default": par.default,
        "page": par.page.name if par.page else None,
        "style": par.style,
    }

    # Numeric bounds — not every param exposes these
    try:
        result["min"] = par.min
        result["max"] = par.max
        result["clampMin"] = par.clampMin
        result["clampMax"] = par.clampMax
    except Exception:
        pass

    # Menu params — expose the option labels/names
    try:
        if par.style in ("Menu", "MenuIndex", "Str"):
            result["menuNames"]   = list(par.menuNames)
            result["menuLabels"]  = list(par.menuLabels)
    except Exception:
        pass

    return result


def _json_fallback(obj):
    """JSON serialiser for TD-specific types that are not natively serialisable."""
    # tdu.Vector / tdu.Position / tdu.Color — treat as list
    if hasattr(obj, '__iter__'):
        try:
            return list(obj)
        except Exception:
            pass
    # tdu.Matrix
    if hasattr(obj, 'vals'):
        try:
            return obj.vals
        except Exception:
            pass
    return str(obj)


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def _log(msg: str):
    """Append a timestamped message to the sibling log Table DAT."""
    try:
        log_dat = op("log")
        if log_dat is not None:
            log_dat.appendRow([absTime.frame, msg])
    except Exception:
        pass  # Never let logging crash the router


def _send(client, payload):
    """Send *payload* (a JSON string) to *client* via the WebServer DAT."""
    try:
        op("webserver1").webSocketSendText(client, payload)
    except Exception as exc:
        _log(f"Send error to {client}: {exc}")


# ---------------------------------------------------------------------------
# Domain: system
# ---------------------------------------------------------------------------

@handler("system.ping")
def h_system_ping(params: dict) -> dict:
    """Return a simple liveness check response."""
    return {"pong": True, "frame": absTime.frame}


@handler("system.info")
def h_system_info(params: dict) -> dict:
    """Return TouchDesigner runtime information and the list of registered methods."""
    try:
        os_name = app.osName
    except Exception:
        os_name = "unknown"

    try:
        realtime = project.realTime
    except Exception:
        realtime = None

    return {
        "version": app.version,
        "build":   app.build,
        "os":      os_name,
        "cookRate": project.cookRate,
        "frame":   absTime.frame,
        "realTime": realtime,
        "methods": sorted(_handlers.keys()),
    }


# ---------------------------------------------------------------------------
# Domain: node
# ---------------------------------------------------------------------------

@handler("node.create")
def h_node_create(params: dict) -> dict:
    """Create a new operator inside the given parent container.

    Params:
        parentPath (str): Path to the parent COMP.
        type (str):       Operator type string (e.g. "noiseCHOP").
        name (str|None):  Desired name; TD assigns one if omitted.
    """
    parent_path = params.get("parentPath")
    op_type     = params.get("type")
    name        = params.get("name")

    if not parent_path or not op_type:
        raise MCPError(INVALID_PARAMS, "'parentPath' and 'type' are required.")

    parent_node = _resolve_op(parent_path)

    try:
        if name:
            new_node = parent_node.create(op_type, name)
        else:
            new_node = parent_node.create(op_type)
    except Exception as exc:
        raise MCPError(OP_CREATE_FAILED, f"Failed to create {op_type!r} in {parent_path!r}: {exc}")

    if new_node is None:
        raise MCPError(OP_CREATE_FAILED, f"create() returned None for type {op_type!r}.")

    return _serialize_node_brief(new_node)


@handler("node.delete")
def h_node_delete(params: dict) -> dict:
    """Destroy the operator at the given path.

    Params:
        path (str): Full path of the operator to delete.
    """
    path = params.get("path")
    if not path:
        raise MCPError(INVALID_PARAMS, "'path' is required.")

    node = _resolve_op(path)
    node_path = node.path  # capture before destroy

    try:
        node.destroy()
    except Exception as exc:
        raise MCPError(INTERNAL_ERROR, f"Failed to destroy {path!r}: {exc}")

    return {"deleted": node_path}


@handler("node.list")
def h_node_list(params: dict) -> dict:
    """List children of a container, optionally filtered by family.

    Params:
        path   (str):      Parent container path. Defaults to "/".
        family (str|None): Filter by operator family (e.g. "CHOP", "TOP").
        depth  (int):      Recursion depth; 1 = direct children only.
    """
    path   = params.get("path", "/")
    family = params.get("family")
    depth  = int(params.get("depth", 1))

    root = _resolve_op(path)

    def _collect(node, remaining_depth: int):
        nodes = []
        try:
            children = node.children
        except Exception:
            return nodes
        for child in children:
            if family and child.family != family:
                pass  # don't include, but still recurse
            else:
                nodes.append(_serialize_node_brief(child))
            if remaining_depth > 1:
                nodes.extend(_collect(child, remaining_depth - 1))
        return nodes

    return {"nodes": _collect(root, depth)}


@handler("node.get")
def h_node_get(params: dict) -> dict:
    """Return full metadata for a single operator.

    Params:
        path (str): Full path of the operator.
    """
    path = params.get("path")
    if not path:
        raise MCPError(INVALID_PARAMS, "'path' is required.")

    node = _resolve_op(path)
    return _serialize_node(node)


# ---------------------------------------------------------------------------
# Domain: par
# ---------------------------------------------------------------------------

@handler("par.get")
def h_par_get(params: dict) -> dict:
    """Read parameter values, optionally filtered by a glob pattern.

    Params:
        path    (str):      Operator path.
        pattern (str|None): Glob pattern (e.g. "t[xyz]"). None = all params.
    """
    path    = params.get("path")
    pattern = params.get("pattern")

    if not path:
        raise MCPError(INVALID_PARAMS, "'path' is required.")

    node = _resolve_op(path)

    try:
        pars = node.pars(pattern) if pattern else node.pars()
    except Exception as exc:
        raise MCPError(PARAMETER_ERROR, f"Failed to read parameters: {exc}")

    result = {}
    for p in pars:
        try:
            result[p.name] = p.eval()
        except Exception:
            result[p.name] = None

    return result


@handler("par.set")
def h_par_set(params: dict) -> dict:
    """Set one or more parameter values on an operator.

    Params:
        path   (str):  Operator path.
        values (dict): Mapping of parameter name -> new value.
    """
    path   = params.get("path")
    values = params.get("values", {})

    if not path:
        raise MCPError(INVALID_PARAMS, "'path' is required.")
    if not isinstance(values, dict):
        raise MCPError(INVALID_PARAMS, "'values' must be a dict.")

    node = _resolve_op(path)

    updated = {}
    errors  = {}
    for name, value in values.items():
        try:
            p = getattr(node.par, name, None)
            if p is None:
                errors[name] = f"Parameter {name!r} not found."
                continue
            p.val = value
            updated[name] = p.eval()
        except Exception as exc:
            errors[name] = str(exc)

    result = {"updated": updated}
    if errors:
        result["errors"] = errors
    return result


@handler("par.get_all")
def h_par_get_all(params: dict) -> dict:
    """Return full parameter metadata for every parameter on an operator.

    Params:
        path (str): Operator path.
    """
    path = params.get("path")
    if not path:
        raise MCPError(INVALID_PARAMS, "'path' is required.")

    node = _resolve_op(path)

    try:
        pars = node.pars()
    except Exception as exc:
        raise MCPError(PARAMETER_ERROR, f"Failed to enumerate parameters: {exc}")

    return {"params": [_serialize_par(p) for p in pars]}


# Also accept the alternate name used by the MCP tools side
@handler("par.info")
def h_par_info(params: dict) -> dict:
    """Return metadata for specific named parameters (or all if names omitted).

    Params:
        path  (str):        Operator path.
        names (list|None):  List of parameter names; None = all.
    """
    path  = params.get("path")
    names = params.get("names")

    if not path:
        raise MCPError(INVALID_PARAMS, "'path' is required.")

    node = _resolve_op(path)

    if names:
        pars = []
        for name in names:
            p = getattr(node.par, name, None)
            if p is None:
                raise MCPError(PARAMETER_ERROR, f"Parameter {name!r} not found on {path!r}.")
            pars.append(p)
    else:
        try:
            pars = node.pars()
        except Exception as exc:
            raise MCPError(PARAMETER_ERROR, f"Failed to enumerate parameters: {exc}")

    return [_serialize_par(p) for p in pars]


# ---------------------------------------------------------------------------
# Domain: conn  (also aliased as connection.* for the MCP tools side)
# ---------------------------------------------------------------------------

def _do_conn_create(params: dict) -> dict:
    """Shared implementation for conn.create and connection.create."""
    from_path   = params.get("fromPath")
    to_path     = params.get("toPath")
    from_output = int(params.get("fromOutput", 0))
    to_input    = int(params.get("toInput",    0))

    if not from_path or not to_path:
        raise MCPError(INVALID_PARAMS, "'fromPath' and 'toPath' are required.")

    src  = _resolve_op(from_path)
    dest = _resolve_op(to_path)

    try:
        src.outputConnectors[from_output].connect(dest.inputConnectors[to_input])
    except Exception as exc:
        raise MCPError(
            CONNECTION_ERROR,
            f"Failed to connect {from_path}[out{from_output}] -> {to_path}[in{to_input}]: {exc}"
        )

    return {
        "fromPath": from_path,
        "fromOutput": from_output,
        "toPath": to_path,
        "toInput": to_input,
    }


def _do_conn_delete(params: dict) -> dict:
    """Shared implementation for conn.delete and connection.delete."""
    path         = params.get("path")
    input_index  = params.get("inputIndex")
    output_index = params.get("outputIndex")

    if not path:
        raise MCPError(INVALID_PARAMS, "'path' is required.")
    if input_index is None and output_index is None:
        raise MCPError(INVALID_PARAMS, "At least one of 'inputIndex' or 'outputIndex' is required.")

    node = _resolve_op(path)
    disconnected = []

    try:
        if input_index is not None:
            node.inputConnectors[int(input_index)].disconnect()
            disconnected.append({"type": "input", "index": int(input_index)})
        if output_index is not None:
            node.outputConnectors[int(output_index)].disconnect()
            disconnected.append({"type": "output", "index": int(output_index)})
    except Exception as exc:
        raise MCPError(CONNECTION_ERROR, f"Failed to disconnect: {exc}")

    return {"path": path, "disconnected": disconnected}


def _do_conn_get(params: dict) -> dict:
    """Shared implementation for conn.get and connection.get."""
    path = params.get("path")
    if not path:
        raise MCPError(INVALID_PARAMS, "'path' is required.")

    node = _resolve_op(path)

    inputs = []
    try:
        for i, conn in enumerate(node.inputConnectors):
            for c in conn.connections:
                inputs.append({
                    "inputIndex": i,
                    "fromPath": c.owner.path,
                    "fromOutput": c.index,
                })
    except Exception as exc:
        raise MCPError(CONNECTION_ERROR, f"Failed to read input connections: {exc}")

    outputs = []
    try:
        for i, conn in enumerate(node.outputConnectors):
            for c in conn.connections:
                outputs.append({
                    "outputIndex": i,
                    "toPath": c.owner.path,
                    "toInput": c.index,
                })
    except Exception as exc:
        raise MCPError(CONNECTION_ERROR, f"Failed to read output connections: {exc}")

    return {"inputs": inputs, "outputs": outputs}


@handler("conn.create")
def h_conn_create(params: dict) -> dict:
    return _do_conn_create(params)


@handler("conn.delete")
def h_conn_delete(params: dict) -> dict:
    return _do_conn_delete(params)


@handler("conn.get")
def h_conn_get(params: dict) -> dict:
    return _do_conn_get(params)


# Aliases used by the MCP tools side (connection.*)
@handler("connection.create")
def h_connection_create(params: dict) -> dict:
    return _do_conn_create(params)


@handler("connection.delete")
def h_connection_delete(params: dict) -> dict:
    return _do_conn_delete(params)


@handler("connection.get")
def h_connection_get(params: dict) -> dict:
    return _do_conn_get(params)


# ---------------------------------------------------------------------------
# Domain: data
# ---------------------------------------------------------------------------

@handler("data.chop")
def h_data_chop(params: dict) -> dict:
    """Read channel data from a CHOP operator.

    Params:
        path        (str):  CHOP operator path.
        max_samples (int):  Maximum number of samples to return per channel.
                            When the CHOP has more samples, values are
                            uniformly downsampled. Default: 1024.
    """
    path        = params.get("path")
    max_samples = int(params.get("max_samples", 1024))

    if not path:
        raise MCPError(INVALID_PARAMS, "'path' is required.")

    node = _resolve_op(path)

    try:
        chans = node.chans()
    except Exception as exc:
        raise MCPError(DATA_ACCESS_ERROR, f"Failed to read CHOP channels: {exc}")

    channels = {}
    for ch in chans:
        try:
            vals = ch.vals  # tuple of float
            n    = len(vals)
            if n <= max_samples:
                channels[ch.name] = list(vals)
            else:
                # Uniform downsample: pick evenly-spaced indices
                step    = n / max_samples
                indices = [int(i * step) for i in range(max_samples)]
                channels[ch.name] = [vals[i] for i in indices]
        except Exception:
            channels[ch.name] = []

    return {
        "path": node.path,
        "numChannels": len(chans),
        "numSamples": node.numSamples if hasattr(node, "numSamples") else 0,
        "sampleRate": node.rate if hasattr(node, "rate") else None,
        "channels": channels,
    }


@handler("data.top")
def h_data_top(params: dict) -> dict:
    """Read resolution info from a TOP, optionally returning pixel data as base64 PNG.

    Params:
        path       (str):      TOP operator path.
        pixels     (bool):     If true, capture pixel data as base64-encoded PNG.
                               Defaults to false.
        max_width  (int|None): Scale down if wider than this. Default: 512.
        max_height (int|None): Scale down if taller than this. Default: 512.
    """
    path       = params.get("path")
    want_pixels = bool(params.get("pixels", False))
    max_width  = params.get("max_width",  512)
    max_height = params.get("max_height", 512)

    if not path:
        raise MCPError(INVALID_PARAMS, "'path' is required.")

    node = _resolve_op(path)

    try:
        width  = node.width
        height = node.height
    except Exception as exc:
        raise MCPError(DATA_ACCESS_ERROR, f"Failed to read TOP dimensions: {exc}")

    result = {
        "path": node.path,
        "width": width,
        "height": height,
    }

    if not want_pixels:
        return result

    # Pixel capture via op.save() to a temp PNG file, then base64-encode
    try:
        import tempfile
        import os
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        tmp_path = tmp.name
        tmp.close()

        node.save(tmp_path)

        with open(tmp_path, "rb") as fh:
            raw = fh.read()
        os.unlink(tmp_path)

        result["encoding"] = "base64"
        result["mimeType"]  = "image/png"
        result["data"]      = base64.b64encode(raw).decode("ascii")
    except Exception as exc:
        raise MCPError(DATA_ACCESS_ERROR, f"Failed to capture TOP pixel data: {exc}")

    return result


@handler("data.sop")
def h_data_sop(params: dict) -> dict:
    """Read geometry data from a SOP operator.

    Params:
        path (str): SOP operator path.
    """
    path = params.get("path")
    if not path:
        raise MCPError(INVALID_PARAMS, "'path' is required.")

    node = _resolve_op(path)

    try:
        num_points = node.numPoints
        num_prims  = node.numPrims
    except Exception as exc:
        raise MCPError(DATA_ACCESS_ERROR, f"Failed to read SOP geometry counts: {exc}")

    # Sample up to 256 points to keep the response size manageable
    points_data = []
    try:
        for pt in node.points:
            p = pt.P
            points_data.append([p[0], p[1], p[2]])
            if len(points_data) >= 256:
                break
    except Exception:
        pass

    bounds = None
    try:
        b = node.bounds
        bounds = {
            "min": [b.min.x, b.min.y, b.min.z],
            "max": [b.max.x, b.max.y, b.max.z],
            "size": [b.size.x, b.size.y, b.size.z],
            "center": [b.center.x, b.center.y, b.center.z],
        }
    except Exception:
        pass

    return {
        "path": node.path,
        "numPoints": num_points,
        "numPrims": num_prims,
        "points": points_data,
        "bounds": bounds,
    }


@handler("data.dat")
def h_data_dat(params: dict) -> dict:
    """Read text or table data from a DAT operator.

    Params:
        path       (str):      DAT operator path.
        row_start  (int|None): First table row to return (0-indexed). Default: 0.
        row_end    (int|None): Last table row to return (exclusive). Default: all.
    """
    path      = params.get("path")
    row_start = params.get("row_start", 0)
    row_end   = params.get("row_end")

    if not path:
        raise MCPError(INVALID_PARAMS, "'path' is required.")

    node = _resolve_op(path)

    # Determine whether this is a table or text DAT
    is_table = False
    try:
        # Table DATs have a numRows attribute > 0 or expose rows()
        is_table = node.isTable
    except Exception:
        try:
            # Fallback: attempt to access rows()
            _ = node.numRows
            is_table = True
        except Exception:
            pass

    if is_table:
        try:
            all_rows = node.rows()
            if row_end is not None:
                rows = all_rows[int(row_start):int(row_end)]
            else:
                rows = all_rows[int(row_start):]
            table_data = [[cell.val for cell in row] for row in rows]
        except Exception as exc:
            raise MCPError(DATA_ACCESS_ERROR, f"Failed to read DAT table: {exc}")

        return {
            "path": node.path,
            "type": "table",
            "numRows": node.numRows,
            "numCols": node.numCols,
            "rows": table_data,
        }
    else:
        try:
            text = node.text
        except Exception as exc:
            raise MCPError(DATA_ACCESS_ERROR, f"Failed to read DAT text: {exc}")

        return {
            "path": node.path,
            "type": "text",
            "text": text,
        }


# ---------------------------------------------------------------------------
# Domain: script
# ---------------------------------------------------------------------------

@handler("script.exec")
def h_script_exec(params: dict) -> dict:
    """Execute arbitrary Python code in the TD global namespace.

    The variable ``result`` in the executed code is captured and returned.

    Params:
        code (str): Python source code to execute.

    WARNING: This handler grants full access to the TouchDesigner environment.
             Use only in trusted, local development contexts.
    """
    code = params.get("code")
    if not isinstance(code, str) or not code.strip():
        raise MCPError(INVALID_PARAMS, "'code' must be a non-empty string.")

    # Build a namespace that includes the standard TD globals
    namespace = {
        "op":      op,
        "ops":     ops,
        "parent":  parent,
        "project": project,
        "absTime": absTime,
        "ui":      ui,
        "me":      me,
        "td":      td,
        "tdu":     tdu,
        "app":     app,
        "result":  None,
    }

    stdout_capture = io.StringIO()
    try:
        import sys
        old_stdout = sys.stdout
        sys.stdout = stdout_capture
        try:
            exec(code, namespace)  # noqa: S102
        finally:
            sys.stdout = old_stdout
    except Exception as exc:
        tb = traceback.format_exc()
        raise MCPError(SCRIPT_ERROR, f"Script error: {exc}\n{tb}")

    return {
        "result": namespace.get("result"),
        "stdout": stdout_capture.getvalue(),
    }


@handler("script.class_list")
def h_script_class_list(params: dict) -> dict:
    """List names in the td module, optionally filtered by a pattern substring.

    Params:
        pattern (str|None): Case-insensitive substring filter. None = all names.
    """
    pattern = params.get("pattern", "")
    names   = dir(td)
    if pattern:
        low = pattern.lower()
        names = [n for n in names if low in n.lower()]
    return {"names": sorted(names)}


@handler("script.class_detail")
def h_script_class_detail(params: dict) -> dict:
    """Return methods and properties for a TD class by name.

    Params:
        name (str): Class or attribute name in the td module.
    """
    name = params.get("name")
    if not name:
        raise MCPError(INVALID_PARAMS, "'name' is required.")

    obj = getattr(td, name, None)
    if obj is None:
        # Try looking it up in builtins
        import builtins
        obj = getattr(builtins, name, None)
    if obj is None:
        raise MCPError(SCRIPT_ERROR, f"Name {name!r} not found in td module or builtins.")

    methods    = []
    properties = []

    for attr in sorted(dir(obj)):
        if attr.startswith("__"):
            continue
        try:
            member = getattr(obj, attr)
            if callable(member):
                sig = ""
                try:
                    sig = str(inspect.signature(member))
                except Exception:
                    pass
                methods.append({"name": attr, "signature": sig})
            else:
                properties.append({"name": attr, "value": repr(member)[:200]})
        except Exception:
            pass

    return {
        "name": name,
        "type": type(obj).__name__,
        "doc": inspect.getdoc(obj) or "",
        "methods": methods,
        "properties": properties,
    }


@handler("script.module_help")
def h_script_module_help(params: dict) -> dict:
    """Capture the help() output for a name in the td module.

    Params:
        name (str): Name of the class or attribute to look up.
    """
    name = params.get("name")
    if not name:
        raise MCPError(INVALID_PARAMS, "'name' is required.")

    obj = getattr(td, name, None)
    if obj is None:
        raise MCPError(SCRIPT_ERROR, f"Name {name!r} not found in td module.")

    buf = io.StringIO()
    try:
        import sys
        old_stdout = sys.stdout
        sys.stdout = buf
        try:
            help(obj)
        finally:
            sys.stdout = old_stdout
    except Exception as exc:
        raise MCPError(SCRIPT_ERROR, f"Failed to generate help for {name!r}: {exc}")

    return {"name": name, "help": buf.getvalue()}


# ---------------------------------------------------------------------------
# Domain: timeline
# ---------------------------------------------------------------------------

@handler("timeline.get")
def h_timeline_get(params: dict) -> dict:
    """Return the current timeline / playback state."""
    playing = False
    try:
        playing = project.play
    except Exception:
        pass

    realtime = None
    try:
        realtime = project.realTime
    except Exception:
        pass

    return {
        "frame":    absTime.frame,
        "seconds":  absTime.seconds,
        "cookRate": project.cookRate,
        "realTime": realtime,
        "playing":  playing,
    }


@handler("timeline.set")
def h_timeline_set(params: dict) -> dict:
    """Set timeline properties.

    Params:
        cookRate (float|None): Desired cook rate (frames per second).
        realTime (bool|None):  Enable or disable real-time playback.
        frame    (int|None):   Jump to this absolute frame.
    """
    updated = {}

    cook_rate = params.get("cookRate")
    if cook_rate is not None:
        try:
            project.cookRate = float(cook_rate)
            updated["cookRate"] = project.cookRate
        except Exception as exc:
            raise MCPError(TIMELINE_ERROR, f"Failed to set cookRate: {exc}")

    realtime = params.get("realTime")
    if realtime is not None:
        try:
            project.realTime = bool(realtime)
            updated["realTime"] = project.realTime
        except Exception as exc:
            raise MCPError(TIMELINE_ERROR, f"Failed to set realTime: {exc}")

    frame = params.get("frame")
    if frame is not None:
        try:
            absTime.frame = int(frame)
            updated["frame"] = absTime.frame
        except Exception as exc:
            raise MCPError(TIMELINE_ERROR, f"Failed to set frame: {exc}")

    return {"updated": updated}


@handler("timeline.play")
def h_timeline_play(params: dict) -> dict:
    """Start timeline playback."""
    try:
        project.play = True
    except Exception as exc:
        raise MCPError(TIMELINE_ERROR, f"Failed to start playback: {exc}")
    return {"playing": True, "frame": absTime.frame}


@handler("timeline.pause")
def h_timeline_pause(params: dict) -> dict:
    """Pause timeline playback."""
    try:
        project.play = False
    except Exception as exc:
        raise MCPError(TIMELINE_ERROR, f"Failed to pause playback: {exc}")
    return {"playing": False, "frame": absTime.frame}


# ---------------------------------------------------------------------------
# Domain: render
# ---------------------------------------------------------------------------

@handler("render.screenshot")
def h_render_screenshot(params: dict) -> dict:
    """Save a TOP's current frame to disk and return it as a base64-encoded PNG.

    Params:
        path      (str):      TOP operator path.
        save_path (str|None): Optional filesystem path to also save the file.
                              If omitted a temporary file is used and then deleted.
    """
    path      = params.get("path")
    save_path = params.get("save_path")

    if not path:
        raise MCPError(INVALID_PARAMS, "'path' is required.")

    node = _resolve_op(path)

    import os
    import tempfile

    cleanup = False
    if save_path:
        file_path = save_path
    else:
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        file_path = tmp.name
        tmp.close()
        cleanup = True

    try:
        node.save(file_path)
        with open(file_path, "rb") as fh:
            raw = fh.read()
    except Exception as exc:
        raise MCPError(DATA_ACCESS_ERROR, f"Failed to save/read screenshot: {exc}")
    finally:
        if cleanup:
            try:
                os.unlink(file_path)
            except Exception:
                pass

    return {
        "path": node.path,
        "savedTo": None if cleanup else file_path,
        "encoding": "base64",
        "mimeType": "image/png",
        "data": base64.b64encode(raw).decode("ascii"),
    }


@handler("render.export")
def h_render_export(params: dict) -> dict:
    """Export a TOP frame to a specified file path with optional format control.

    Params:
        path      (str): TOP operator path.
        save_path (str): Filesystem path for the exported file. The file
                         extension controls the format (e.g. ".jpg", ".png",
                         ".exr").
        quality   (int): JPEG quality 0-100 (ignored for lossless formats).
                         Default: 90.
    """
    path      = params.get("path")
    save_path = params.get("save_path")
    quality   = int(params.get("quality", 90))

    if not path or not save_path:
        raise MCPError(INVALID_PARAMS, "'path' and 'save_path' are required.")

    node = _resolve_op(path)

    try:
        # TD's save() respects the file extension for format selection.
        # Quality is passed where supported.
        node.save(save_path, quality=quality)
    except TypeError:
        # Older TD builds may not accept quality kwarg
        try:
            node.save(save_path)
        except Exception as exc:
            raise MCPError(DATA_ACCESS_ERROR, f"Failed to export: {exc}")
    except Exception as exc:
        raise MCPError(DATA_ACCESS_ERROR, f"Failed to export to {save_path!r}: {exc}")

    return {
        "path": node.path,
        "savedTo": save_path,
        "quality": quality,
    }


# ---------------------------------------------------------------------------
# Domain: project
# ---------------------------------------------------------------------------

@handler("project.info")
def h_project_info(params: dict) -> dict:
    """Return project and application metadata."""
    try:
        proj_name = project.name
    except Exception:
        proj_name = None

    try:
        proj_folder = project.folder
    except Exception:
        proj_folder = None

    try:
        cook_rate = project.cookRate
    except Exception:
        cook_rate = None

    return {
        "projectName":   proj_name,
        "projectFolder": proj_folder,
        "appVersion":    app.version,
        "appBuild":      app.build,
        "cookRate":      cook_rate,
        "frame":         absTime.frame,
    }


@handler("project.save")
def h_project_save(params: dict) -> dict:
    """Save the current TouchDesigner project.

    Params:
        path (str|None): File path to save to. If omitted saves to the current
                         project file.
    """
    save_path = params.get("path")

    try:
        if save_path:
            project.save(save_path)
            saved_to = save_path
        else:
            project.save()
            saved_to = project.name
    except Exception as exc:
        raise MCPError(PROJECT_ERROR, f"Failed to save project: {exc}")

    return {"savedTo": saved_to}


# ---------------------------------------------------------------------------
# Domain: layout
# ---------------------------------------------------------------------------

@handler("layout.set_position")
def h_layout_set_position(params: dict) -> dict:
    """Set the network-editor position of one or more nodes.

    Params:
        nodes (list): List of objects each with:
                      - path (str): Operator path.
                      - x    (float): Horizontal position in network units.
                      - y    (float): Vertical position in network units.
    """
    nodes_spec = params.get("nodes")
    if not isinstance(nodes_spec, list) or not nodes_spec:
        raise MCPError(INVALID_PARAMS, "'nodes' must be a non-empty list.")

    updated = []
    errors  = []

    for spec in nodes_spec:
        path = spec.get("path")
        x    = spec.get("x")
        y    = spec.get("y")

        if not path:
            errors.append({"spec": spec, "error": "Missing 'path'."})
            continue

        try:
            node = _resolve_op(path)
            if x is not None:
                node.nodeX = float(x)
            if y is not None:
                node.nodeY = float(y)
            updated.append({"path": node.path, "x": node.nodeX, "y": node.nodeY})
        except MCPError as exc:
            errors.append({"path": path, "error": exc.message})
        except Exception as exc:
            errors.append({"path": path, "error": str(exc)})

    result = {"updated": updated}
    if errors:
        result["errors"] = errors
    return result


@handler("layout.align")
def h_layout_align(params: dict) -> dict:
    """Distribute a list of nodes along a horizontal or vertical axis.

    Params:
        paths     (list[str]): Ordered list of operator paths.
        axis      (str):       "horizontal" or "vertical". Default: "horizontal".
        start_x   (float):     X coordinate of the first node. Default: 0.
        start_y   (float):     Y coordinate of the first node. Default: 0.
        spacing   (float):     Distance between node centres. Default: 200.
    """
    paths   = params.get("paths")
    axis    = params.get("axis", "horizontal").lower()
    start_x = float(params.get("start_x", 0))
    start_y = float(params.get("start_y", 0))
    spacing = float(params.get("spacing", 200))

    if not isinstance(paths, list) or not paths:
        raise MCPError(INVALID_PARAMS, "'paths' must be a non-empty list of operator paths.")

    if axis not in ("horizontal", "vertical"):
        raise MCPError(INVALID_PARAMS, "'axis' must be 'horizontal' or 'vertical'.")

    updated = []
    for i, path in enumerate(paths):
        try:
            node = _resolve_op(path)
            if axis == "horizontal":
                node.nodeX = start_x + i * spacing
                node.nodeY = start_y
            else:
                node.nodeX = start_x
                node.nodeY = start_y + i * spacing
            updated.append({"path": node.path, "x": node.nodeX, "y": node.nodeY})
        except MCPError:
            raise
        except Exception as exc:
            raise MCPError(INTERNAL_ERROR, f"Failed to position {path!r}: {exc}")

    return {"aligned": updated, "axis": axis}
