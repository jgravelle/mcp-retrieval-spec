"""
jmri.client — MRIClient for jMRI-compliant MCP servers.

This is the installed package entry point. The standalone version of this
file lives at sdk/python/mri_client.py for use without pip install.
"""

import json
import subprocess
import shutil
from typing import Optional

__version__ = "1.0.0"


class MRIError(Exception):
    def __init__(self, code: str, message: str, detail: dict = None):
        self.code = code
        self.detail = detail or {}
        super().__init__(f"[{code}] {message}")


class MRIClient:
    """
    Client for a jMRI-compliant MCP server.

    By default, connects to jcodemunch-mcp for code and jdocmunch-mcp for docs.
    Pass custom server commands to override.

    Usage:
        client = MRIClient()
        sources = client.discover()
        results = client.search("database session", repo="fastapi/fastapi")
        symbol = client.retrieve(results[0]["id"], repo="fastapi/fastapi")
        print(f"Tokens saved: {symbol['_meta']['tokens_saved']:,}")
    """

    def __init__(
        self,
        code_server_cmd: list[str] = None,
        doc_server_cmd: list[str] = None,
        timeout: int = 60,
    ):
        self._code_cmd = code_server_cmd or self._find_server("jcodemunch-mcp")
        self._doc_cmd = doc_server_cmd or self._find_server("jdocmunch-mcp")
        self._timeout = timeout
        self._call_id = 0

    def discover(self, domain: str = "code") -> list[dict]:
        """List all available knowledge sources (jMRI: discover())."""
        result = self._call(domain, "list_repos", {})
        return result.get("repos", result) if isinstance(result, dict) else result

    def search(
        self,
        query: str,
        repo: str,
        scope: str = None,
        kind: str = None,
        max_results: int = 10,
        domain: str = "code",
    ) -> list[dict]:
        """Search for relevant symbols or sections (jMRI: search())."""
        if domain == "code":
            args = {"repo": repo, "query": query, "max_results": max_results}
            if kind:
                args["kind"] = kind
            if scope:
                args["file_pattern"] = scope
            return self._call("code", "search_symbols", args).get("symbols", [])
        else:
            args = {"repo": repo, "query": query, "max_results": max_results}
            if scope:
                args["doc_path"] = scope
            return self._call("docs", "search_sections", args).get("sections", [])

    def retrieve(
        self,
        id: str,
        repo: str,
        verify: bool = False,
        context_lines: int = 0,
        domain: str = "code",
    ) -> dict:
        """Fetch full content of a symbol or section by stable ID (jMRI: retrieve())."""
        if domain == "code":
            return self._call("code", "get_symbol", {
                "repo": repo, "symbol_id": id,
                "verify": verify, "context_lines": context_lines,
            })
        else:
            return self._call("docs", "get_section", {
                "repo": repo, "section_id": id, "verify": verify,
            })

    def retrieve_batch(self, ids: list[str], repo: str, domain: str = "code") -> list[dict]:
        """Fetch multiple symbols or sections in one call (jMRI: retrieve batch)."""
        if domain == "code":
            return self._call("code", "get_symbols", {"repo": repo, "symbol_ids": ids}).get("symbols", [])
        else:
            return self._call("docs", "get_sections", {"repo": repo, "section_ids": ids}).get("sections", [])

    def metadata(self, repo: str, domain: str = "code") -> dict:
        """Get index statistics and token cost estimates (jMRI: metadata())."""
        tool = "get_repo_outline" if domain == "code" else "get_toc"
        return self._call(domain, tool, {"repo": repo})

    def _call(self, domain: str, tool_name: str, args: dict) -> dict:
        cmd = self._code_cmd if domain == "code" else self._doc_cmd
        if cmd is None:
            server = "jcodemunch-mcp" if domain == "code" else "jdocmunch-mcp"
            raise MRIError("NOT_INSTALLED", f"{server} not found. Install with: uvx {server}")

        self._call_id += 1
        init_msg = json.dumps({
            "jsonrpc": "2.0", "id": 0, "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05", "capabilities": {},
                "clientInfo": {"name": "mri-client", "version": __version__},
            }
        })
        call_msg = json.dumps({
            "jsonrpc": "2.0", "id": self._call_id, "method": "tools/call",
            "params": {"name": tool_name, "arguments": args},
        })

        try:
            proc = subprocess.run(
                cmd,
                input=f"{init_msg}\n{call_msg}\n",
                capture_output=True, text=True,
                timeout=self._timeout,
            )
        except subprocess.TimeoutExpired:
            raise MRIError("TIMEOUT", f"Server timed out after {self._timeout}s")
        except FileNotFoundError:
            raise MRIError("NOT_INSTALLED", f"Server command not found: {cmd}")

        for line in reversed(proc.stdout.strip().splitlines()):
            try:
                parsed = json.loads(line.strip())
                if "result" in parsed:
                    content = parsed["result"].get("content", [])
                    if content:
                        payload = json.loads(content[0].get("text", "{}"))
                        if "error" in payload:
                            e = payload["error"]
                            raise MRIError(e.get("code", "ERROR"), e.get("message", "Unknown"), e.get("detail"))
                        return payload
            except (json.JSONDecodeError, KeyError):
                continue

        raise MRIError("PARSE_ERROR", f"Could not parse server response. stderr: {proc.stderr[:200]}")

    @staticmethod
    def _find_server(name: str) -> Optional[list[str]]:
        if shutil.which(name):
            return [name]
        if shutil.which("uvx"):
            return ["uvx", name]
        return None
