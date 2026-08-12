from __future__ import annotations

import json
import sys
from typing import Any

from .smriti_client import SmritiClient


TOOLS = [
    {
        "name": "smriti_task_get",
        "description": "Read one derived Smriti task by immutable id.",
        "inputSchema": {"type": "object", "properties": {"task_id": {"type": "string"}}, "required": ["task_id"]},
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "smriti_evidence_capture",
        "description": "Capture a user-authored derived evidence summary; never send raw source content.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string"},
                "kind": {"type": "string"},
                "summary": {"type": "string"},
                "source_refs": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["task_id", "kind", "summary"],
        },
        "annotations": {"readOnlyHint": False, "destructiveHint": False},
    },
    {
        "name": "smriti_handoff_put",
        "description": "Store a compact task handoff in Smriti; this does not perform an external work action.",
        "inputSchema": {
            "type": "object",
            "properties": {"task_id": {"type": "string"}, "summary": {"type": "string"}, "next": {"type": "array", "items": {"type": "string"}}},
            "required": ["task_id", "summary"],
        },
        "annotations": {"readOnlyHint": False, "destructiveHint": False},
    },
]


def _result(value: Any) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(value, sort_keys=True)}], "structuredContent": value}


def handle(message: dict[str, Any], client: SmritiClient | None) -> dict[str, Any] | None:
    method = message.get("method")
    request_id = message.get("id")
    if request_id is None:
        return None
    if method == "initialize":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}}, "serverInfo": {"name": "sarathi-smriti", "version": "0.1.0"}}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}}
    if method != "tools/call":
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": "method not found"}}
    if client is None:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32000, "message": "SMRITI_URL is not configured"}}
    params = message.get("params", {})
    name = params.get("name")
    args = params.get("arguments", {})
    if name == "smriti_task_get":
        value = client.get_task(args["task_id"])
    elif name == "smriti_evidence_capture":
        value = client.capture_evidence({**args, "redaction_state": "derived-no-raw-content", "provenance": {"producer": "sarathi-mcp"}})
    elif name == "smriti_handoff_put":
        value = client.put_handoff(args["task_id"], {"summary": args["summary"], "next": args.get("next", [])})
    else:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32602, "message": "unknown tool"}}
    return {"jsonrpc": "2.0", "id": request_id, "result": _result(value)}


def main() -> int:
    client = SmritiClient.from_environment()
    for line in sys.stdin:
        try:
            response = handle(json.loads(line), client)
            if response is not None:
                print(json.dumps(response), flush=True)
        except Exception as exc:  # MCP boundary: return a structured error, never a traceback.
            message_id = None
            try:
                message_id = json.loads(line).get("id")
            except Exception:
                pass
            print(json.dumps({"jsonrpc": "2.0", "id": message_id, "error": {"code": -32001, "message": str(exc)}}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
