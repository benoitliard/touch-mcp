"""
WebServer DAT Callbacks for touch-mcp bridge.

This script runs on the WebSocket thread. NEVER call op() or any TD API directly.
Use td.run() with endFrame=True to execute code on the main thread.
"""

import json


def onWebSocketOpen(webServerDAT, client, uri):
    td.run(
        'op("command_router").module._on_client_connect(' + repr(client) + ')',
        endFrame=True, fromOP=webServerDAT
    )


def onWebSocketClose(webServerDAT, client):
    td.run(
        'op("command_router").module._on_client_disconnect(' + repr(client) + ')',
        endFrame=True, fromOP=webServerDAT
    )


def onWebSocketReceiveText(webServerDAT, client, data):
    td.run(
        'op("command_router").module.process_request('
        + repr(client) + ', ' + repr(data) + ')',
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
    td.run(
        'op("command_router").module._log("Server started")',
        endFrame=True, fromOP=webServerDAT
    )


def onServerStop(webServerDAT):
    td.run(
        'op("command_router").module._log("Server stopped")',
        endFrame=True, fromOP=webServerDAT
    )
