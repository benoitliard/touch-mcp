"""
WebServer DAT Callbacks for touch-mcp bridge.

This script runs on the WebSocket thread. NEVER call op() or any TD API directly.
Use td.run() with endFrame=True to execute code on the main thread.
"""

import json


def _router_path(webServerDAT):
    """Get the absolute path to the command_router DAT."""
    return webServerDAT.parent().path + '/command_router'


def onWebSocketOpen(webServerDAT, client, uri):
    path = _router_path(webServerDAT)
    td.run(
        f'op("{path}").module._on_client_connect({repr(client)})',
        endFrame=True, fromOP=webServerDAT
    )


def onWebSocketClose(webServerDAT, client):
    path = _router_path(webServerDAT)
    td.run(
        f'op("{path}").module._on_client_disconnect({repr(client)})',
        endFrame=True, fromOP=webServerDAT
    )


def onWebSocketReceiveText(webServerDAT, client, data):
    path = _router_path(webServerDAT)
    td.run(
        f'op("{path}").module.process_request({repr(client)}, {repr(data)})',
        endFrame=True, fromOP=webServerDAT
    )


def onWebSocketReceiveBinary(webServerDAT, client, data):
    pass  # Binary protocol not supported


def onHTTPRequest(webServerDAT, request, response):
    """Health check endpoint."""
    response['statusCode'] = 200
    response['statusReason'] = 'OK'
    response['data'] = json.dumps({"status": "ok", "server": "touch-mcp"})
    return response


def onServerStart(webServerDAT):
    path = _router_path(webServerDAT)
    td.run(
        f'op("{path}").module._log("Server started")',
        endFrame=True, fromOP=webServerDAT
    )


def onServerStop(webServerDAT):
    path = _router_path(webServerDAT)
    td.run(
        f'op("{path}").module._log("Server stopped")',
        endFrame=True, fromOP=webServerDAT
    )
