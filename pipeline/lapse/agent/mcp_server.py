"""Serve the tools to any MCP client (Claude Desktop, Claude Code, other agents).

    python -m lapse mcp

The Model Context Protocol lets an AI assistant use outside tools. This server
speaks it over stdin/stdout with nothing but the standard library: one JSON
message per line. It offers the same read-only tools as the built-in harness,
plus check_answer, which runs the number guard on a drafted answer.

A client that is not our harness cannot be forced to obey the guard. The server
therefore states the rules in its instructions and gives the client the means to
check itself.
"""

from __future__ import annotations

import json
import sys

from . import guard, tools

VERSIONS = ("2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25")     # revisions that start with "initialize"
NAME, VERSION = "lapse", "0.1.0"

INSTRUCTIONS = (
    "Lapse answers one kind of question: how air temperature, water vapor and ozone are changing at different "
    "heights, from two NASA records (AIRS, 2002 onward; MERRA-2, 1980 onward). Rules for using it: "
    "(1) Take every number from a tool result. Copy it as written, or round it keeping at least two significant "
    "digits. Do not calculate new numbers. "
    "(2) Always report the label a tool gives (Clear change, Likely change, Not proven yet, Disputed) and never a "
    "stronger one. \"Not proven yet\" does not mean nothing changed. "
    "(3) A trend says what changed, not why and not what happens next. "
    "(4) Before you show an answer, pass it to check_answer and fix whatever it reports. "
    "(5) Tell the reader which NASA product and file each answer came from (the source field)."
)

CHECK = {
    "name": "check_answer",
    "description": "Checks a drafted answer before you show it. Reports every number in the text that does not come "
                   "from a tool result in this session (or from the person's own question).",
    "parameters": {"type": "object", "additionalProperties": False, "required": ["text"], "properties": {
        "text": {"type": "string", "description": "The answer you intend to show."},
        "question": {"type": "string", "description": "The person's question, so numbers they typed are allowed."}}},
}


class Server:
    def __init__(self, site: tools.Site | None = None):
        self.site = site or tools.Site()
        self.results = []                # every tool result given out in this session

    def tool_list(self) -> list:
        return [{"name": s["name"], "description": s["description"], "inputSchema": s["parameters"],
                 "annotations": {"readOnlyHint": True, "openWorldHint": False}}
                for s in tools.specs(self.site) + [CHECK]]

    def call_tool(self, name: str, args: dict) -> dict:
        if name == "check_answer":
            if not isinstance(args.get("text"), str) or not args["text"].strip():
                out = {"ok": False, "error": "check_answer needs the text of the answer."}
            else:
                problems = guard.check(args["text"], str(args.get("question") or ""), self.results)
                out = {"ok": True, "result": {"passed": not problems, "problems": problems,
                                              "checked_against": f"{len(self.results)} tool results from this session"}}
        else:
            out = tools.call(self.site, name, args)
            if out["ok"]:
                self.results.append(out["result"])
        payload = out["result"] if out["ok"] else {"error": out["error"]}
        return {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}], "isError": not out["ok"]}

    def handle(self, msg: dict) -> dict | None:
        """One JSON-RPC message in, one out. Notifications get no reply."""
        method, mid = msg.get("method"), msg.get("id")
        if mid is None or method is None:                 # a notification, or a reply to something we never sent
            return None

        def ok(result):
            return {"jsonrpc": "2.0", "id": mid, "result": result}

        def fail(code, text):
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": text}}

        params = msg.get("params") or {}
        if method == "initialize":
            asked = params.get("protocolVersion")
            return ok({"protocolVersion": asked if asked in VERSIONS else VERSIONS[-1],
                       "capabilities": {"tools": {"listChanged": False}},
                       "serverInfo": {"name": NAME, "version": VERSION}, "instructions": INSTRUCTIONS})
        if method == "ping":
            return ok({})
        if method == "tools/list":
            return ok({"tools": self.tool_list()})
        if method == "tools/call":
            name, args = params.get("name"), params.get("arguments") or {}
            if not isinstance(name, str) or not isinstance(args, dict):
                return fail(-32602, "tools/call needs a tool name and an object of arguments")
            return ok(self.call_tool(name, args))
        return fail(-32601, f"Method not found: {method}")


def serve(stdin=None, stdout=None, site: tools.Site | None = None) -> None:
    """Read one JSON message per line until the input closes. Only protocol messages go to stdout."""
    stdin, stdout = stdin or sys.stdin, stdout or sys.stdout
    server = Server(site)
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            reply = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
        else:
            try:
                reply = server.handle(msg) if isinstance(msg, dict) else {
                    "jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Invalid request"}}
            except Exception as exc:                      # never let one bad request end the session
                print(f"lapse mcp: {type(exc).__name__}: {exc}", file=sys.stderr)
                reply = {"jsonrpc": "2.0", "id": msg.get("id"), "error": {"code": -32603, "message": "Internal error"}}
        if reply is not None:
            stdout.write(json.dumps(reply, ensure_ascii=False) + "\n")
            stdout.flush()
