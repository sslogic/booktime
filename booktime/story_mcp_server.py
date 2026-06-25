#!/usr/bin/env python
"""Minimal local Book Time MCP-style stdio server.

This is intentionally small and file-backed. It exposes Book Time story memory
inside the package folder so LM Studio or another MCP client can be pointed at
this script without using the Oracle server.
"""
import json
import sys

from story_memory import list_characters, read_text, seed_path, upsert_custom_character


TOOLS = [
    {
        "name": "booktime_get_seed",
        "description": "Read the latest Book Time continuation seed.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "booktime_list_characters",
        "description": "List local Book Time character cards.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "booktime_save_character",
        "description": "Save or update a local Book Time character card.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "role": {"type": "string"},
                "personality": {"type": "array", "items": {"type": "string"}},
                "relationships": {"type": "array", "items": {"type": "string"}},
                "voice_rules": {"type": "array", "items": {"type": "string"}},
                "do_not_change": {"type": "array", "items": {"type": "string"}},
                "notes": {"type": "string"},
            },
            "required": ["name"],
        },
    },
]


def result(request_id, payload):
    print(json.dumps({"jsonrpc": "2.0", "id": request_id, "result": payload}), flush=True)


def error(request_id, code, message):
    print(json.dumps({"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}), flush=True)


def handle(request):
    method = request.get("method")
    request_id = request.get("id")
    params = request.get("params") or {}
    if method == "initialize":
        result(request_id, {
            "protocolVersion": "2024-11-05",
            "serverInfo": {"name": "booktime-story-memory", "version": "0.1.0"},
            "capabilities": {"tools": {}},
        })
    elif method == "tools/list":
        result(request_id, {"tools": TOOLS})
    elif method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        if name == "booktime_get_seed":
            result(request_id, {"content": [{"type": "text", "text": read_text(seed_path())}]})
        elif name == "booktime_list_characters":
            result(request_id, {"content": [{"type": "text", "text": json.dumps(list_characters(), indent=2, ensure_ascii=False)}]})
        elif name == "booktime_save_character":
            card = upsert_custom_character(args)
            result(request_id, {"content": [{"type": "text", "text": json.dumps(card, indent=2, ensure_ascii=False)}]})
        else:
            error(request_id, -32601, f"Unknown tool: {name}")
    elif method == "notifications/initialized":
        return
    else:
        error(request_id, -32601, f"Unknown method: {method}")


def main():
    for line in sys.stdin:
        line = line.lstrip("\ufeffï»¿").strip()
        if not line:
            continue
        try:
            handle(json.loads(line))
        except Exception as exc:
            error(None, -32000, str(exc))


if __name__ == "__main__":
    main()
