"""
jmri.reference.server — Minimal jMRI-compliant MCP server.

Wraps jcodemunch-mcp and jdocmunch-mcp to expose the four canonical
jMRI method names: list_repos, search, retrieve, metadata.

Entry point: jmri-server (installed via pip install jmri-sdk)

LICENSE NOTE:
  This file is Apache 2.0.
  Running it in production requires a valid jMunch license.
  Licenses: https://j.gravelle.us/jCodeMunch/
"""

import json
import subprocess
import shutil
from mcp.server import Server
from mcp.types import Tool, TextContent

server = Server("jmri-reference")


def _jmunch_call(server_name: str, tool_name: str, args: dict) -> dict:
    """Call a jMunch server via JSON-RPC stdin/stdout."""
    if shutil.which(server_name):
        cmd_list = [server_name]
    elif shutil.which("uvx"):
        cmd_list = ["uvx", server_name]
    else:
        return {"error": {"code": "NOT_INSTALLED", "message": f"{server_name} not found"}}

    init_msg = json.dumps({
        "jsonrpc": "2.0", "id": 0, "method": "initialize",
        "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                   "clientInfo": {"name": "jmri-reference", "version": "1.0"}}
    })
    call_msg = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": tool_name, "arguments": args}
    })

    try:
        proc = subprocess.run(
            cmd_list,
            input=f"{init_msg}\n{call_msg}\n",
            capture_output=True, text=True, timeout=60,
        )
        for line in reversed(proc.stdout.strip().splitlines()):
            try:
                parsed = json.loads(line.strip())
                if "result" in parsed:
                    content = parsed["result"].get("content", [])
                    if content:
                        return json.loads(content[0].get("text", "{}"))
            except (json.JSONDecodeError, KeyError):
                continue
    except subprocess.TimeoutExpired:
        return {"error": {"code": "TIMEOUT", "message": "Server timed out"}}
    except FileNotFoundError:
        return {"error": {"code": "NOT_INSTALLED", "message": f"Cannot run {cmd_list}"}}

    return {"error": {"code": "PARSE_ERROR", "message": "No parseable response"}}


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="list_repos",
            description="[jMRI: discover()] List all indexed knowledge sources.",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "enum": ["code", "docs", "both"],
                        "default": "both",
                    }
                }
            }
        ),
        Tool(
            name="search",
            description="[jMRI: search(query, scope?)] Search for relevant symbols or sections.",
            inputSchema={
                "type": "object",
                "required": ["repo", "query"],
                "properties": {
                    "repo":        {"type": "string"},
                    "query":       {"type": "string"},
                    "scope":       {"type": "string"},
                    "kind":        {"type": "string"},
                    "max_results": {"type": "integer", "default": 10},
                    "domain":      {"type": "string", "enum": ["code", "docs"], "default": "code"},
                }
            }
        ),
        Tool(
            name="retrieve",
            description="[jMRI: retrieve(id)] Fetch full source or section content by stable ID.",
            inputSchema={
                "type": "object",
                "required": ["repo", "id"],
                "properties": {
                    "repo":          {"type": "string"},
                    "id":            {"type": "string"},
                    "verify":        {"type": "boolean", "default": False},
                    "context_lines": {"type": "integer", "default": 0},
                    "domain":        {"type": "string", "enum": ["code", "docs"], "default": "code"},
                }
            }
        ),
        Tool(
            name="metadata",
            description="[jMRI: metadata(id?)] Index statistics and token cost estimates.",
            inputSchema={
                "type": "object",
                "required": ["repo"],
                "properties": {
                    "repo":   {"type": "string"},
                    "domain": {"type": "string", "enum": ["code", "docs"], "default": "code"},
                }
            }
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    domain = arguments.pop("domain", "code")

    if name == "list_repos":
        if domain == "both":
            code_r = _jmunch_call("jcodemunch-mcp", "list_repos", {})
            doc_r = _jmunch_call("jdocmunch-mcp", "list_repos", {})
            result = {"code": code_r.get("repos", []), "docs": doc_r.get("repos", []),
                      "_meta": code_r.get("_meta", {})}
        else:
            srv = "jcodemunch-mcp" if domain == "code" else "jdocmunch-mcp"
            result = _jmunch_call(srv, "list_repos", {})

    elif name == "search":
        if domain == "code":
            args = {"repo": arguments["repo"], "query": arguments["query"],
                    "max_results": arguments.get("max_results", 10)}
            if "kind" in arguments:
                args["kind"] = arguments["kind"]
            if "scope" in arguments:
                args["file_pattern"] = arguments["scope"]
            result = _jmunch_call("jcodemunch-mcp", "search_symbols", args)
        else:
            args = {"repo": arguments["repo"], "query": arguments["query"],
                    "max_results": arguments.get("max_results", 10)}
            if "scope" in arguments:
                args["doc_path"] = arguments["scope"]
            result = _jmunch_call("jdocmunch-mcp", "search_sections", args)

    elif name == "retrieve":
        if domain == "code":
            result = _jmunch_call("jcodemunch-mcp", "get_symbol", {
                "repo": arguments["repo"], "symbol_id": arguments["id"],
                "verify": arguments.get("verify", False),
                "context_lines": arguments.get("context_lines", 0),
            })
        else:
            result = _jmunch_call("jdocmunch-mcp", "get_section", {
                "repo": arguments["repo"], "section_id": arguments["id"],
                "verify": arguments.get("verify", False),
            })

    elif name == "metadata":
        if domain == "code":
            result = _jmunch_call("jcodemunch-mcp", "get_repo_outline", {"repo": arguments["repo"]})
        else:
            result = _jmunch_call("jdocmunch-mcp", "get_toc", {"repo": arguments["repo"]})

    else:
        result = {"error": {"code": "UNKNOWN_TOOL", "message": f"Unknown jMRI method: {name}"}}

    return [TextContent(type="text", text=json.dumps(result, indent=2))]


async def run():
    import mcp
    async with mcp.stdio_server() as (r, w):
        await server.run(r, w, server.create_initialization_options())


def main():
    import asyncio
    asyncio.run(run())


if __name__ == "__main__":
    main()
