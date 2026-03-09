"""
reference/server.py — Minimal jMRI-compliant MCP server.

Wraps jcodemunch-mcp and jdocmunch-mcp to expose the four canonical
jMRI method names: list_repos, search, retrieve, metadata.

This server is a thin routing layer. It requires jCodeMunch and jDocMunch
to be installed for the actual retrieval work.

LICENSE NOTE:
  This file is Apache 2.0.
  Running it in production requires a valid jMunch license for the
  underlying retrieval engines.
  Licenses: https://j.gravelle.us/jCodeMunch/
"""

import json
import subprocess
import shutil
from mcp.server import Server
from mcp.types import Tool, TextContent

server = Server("jmri-reference")

# -------------------------------------------------------------------------
# Tool routing: jMRI method names → jMunch tool names
# -------------------------------------------------------------------------

CODE_TOOL_MAP = {
    "list_repos": ("code", "list_repos"),
    "search":     ("code", "search_symbols"),
    "retrieve":   ("code", "get_symbol"),
    "metadata":   ("code", "get_repo_outline"),
}

DOC_TOOL_MAP = {
    "list_repos": ("docs", "list_repos"),
    "search":     ("docs", "search_sections"),
    "retrieve":   ("docs", "get_section"),
    "metadata":   ("docs", "get_toc"),
}


def _jmunch_call(server_name: str, tool_name: str, args: dict) -> dict:
    """Call a jMunch server via JSON-RPC stdin/stdout."""
    cmd = shutil.which(server_name) or None
    if cmd is None:
        # Try uvx fallback
        if shutil.which("uvx"):
            cmd_list = ["uvx", server_name]
        else:
            return {"error": {"code": "NOT_INSTALLED", "message": f"{server_name} not found"}}
    else:
        cmd_list = [cmd]

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
            capture_output=True, text=True, timeout=60
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


# -------------------------------------------------------------------------
# jMRI tools
# -------------------------------------------------------------------------

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="list_repos",
            description="[jMRI: discover()] List all indexed knowledge sources (code repos and doc trees).",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "enum": ["code", "docs", "both"],
                        "default": "both",
                        "description": "Which knowledge domain to query"
                    }
                }
            }
        ),
        Tool(
            name="search",
            description="[jMRI: search(query, scope?)] Search for relevant symbols or sections. Returns IDs and summaries only.",
            inputSchema={
                "type": "object",
                "required": ["repo", "query"],
                "properties": {
                    "repo":        {"type": "string", "description": "Repository identifier"},
                    "query":       {"type": "string", "description": "Search query"},
                    "scope":       {"type": "string", "description": "File path or prefix to narrow search"},
                    "kind":        {"type": "string", "description": "Symbol kind filter (function, class, method, section)"},
                    "max_results": {"type": "integer", "default": 10},
                    "domain":      {"type": "string", "enum": ["code", "docs"], "default": "code"}
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
                    "id":            {"type": "string", "description": "Stable ID from search()"},
                    "verify":        {"type": "boolean", "default": False},
                    "context_lines": {"type": "integer", "default": 0},
                    "domain":        {"type": "string", "enum": ["code", "docs"], "default": "code"}
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
                    "id":     {"type": "string", "description": "Optional: file or section ID for granular stats"},
                    "domain": {"type": "string", "enum": ["code", "docs"], "default": "code"}
                }
            }
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    domain = arguments.pop("domain", "code")

    if name == "list_repos":
        if domain == "both":
            code_result = _jmunch_call("jcodemunch-mcp", "list_repos", {})
            doc_result = _jmunch_call("jdocmunch-mcp", "list_repos", {})
            result = {
                "code": code_result.get("repos", []),
                "docs": doc_result.get("repos", []),
                "_meta": code_result.get("_meta", {})
            }
        else:
            server_name = "jcodemunch-mcp" if domain == "code" else "jdocmunch-mcp"
            result = _jmunch_call(server_name, "list_repos", {})

    elif name == "search":
        if domain == "code":
            args = {
                "repo": arguments["repo"],
                "query": arguments["query"],
                "max_results": arguments.get("max_results", 10),
            }
            if "kind" in arguments:
                args["kind"] = arguments["kind"]
            if "scope" in arguments:
                args["file_pattern"] = arguments["scope"]
            result = _jmunch_call("jcodemunch-mcp", "search_symbols", args)
        else:
            args = {
                "repo": arguments["repo"],
                "query": arguments["query"],
                "max_results": arguments.get("max_results", 10),
            }
            if "scope" in arguments:
                args["doc_path"] = arguments["scope"]
            result = _jmunch_call("jdocmunch-mcp", "search_sections", args)

    elif name == "retrieve":
        if domain == "code":
            args = {
                "repo": arguments["repo"],
                "symbol_id": arguments["id"],
                "verify": arguments.get("verify", False),
                "context_lines": arguments.get("context_lines", 0),
            }
            result = _jmunch_call("jcodemunch-mcp", "get_symbol", args)
        else:
            args = {
                "repo": arguments["repo"],
                "section_id": arguments["id"],
                "verify": arguments.get("verify", False),
            }
            result = _jmunch_call("jdocmunch-mcp", "get_section", args)

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
