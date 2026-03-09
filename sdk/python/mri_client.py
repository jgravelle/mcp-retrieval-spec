"""
mri_client.py — Python client for jMRI-compliant MCP servers.

Talks to jcodemunch-mcp and jdocmunch-mcp via JSON-RPC over stdin/stdout.
Works with any jMRI-compliant server that exposes the four core methods.

License: Apache 2.0
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

    # ------------------------------------------------------------------
    # jMRI Core Interface
    # ------------------------------------------------------------------

    def discover(self, domain: str = "code") -> list[dict]:
        """
        List all available knowledge sources.

        jMRI method: discover()
        Maps to: list_repos (both servers)

        Args:
            domain: "code" or "docs"

        Returns:
            List of source dicts with repo, indexed_at, file/symbol counts.
        """
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
        """
        Search for relevant symbols or sections.

        jMRI method: search(query, scope?)
        Maps to: search_symbols (code) or search_sections (docs)

        Args:
            query: Natural language or keyword query.
            repo: Repository identifier from discover().
            scope: Optional file path or path prefix to narrow search.
            kind: Filter by kind (function, class, method, etc.).
            max_results: Maximum results to return.
            domain: "code" or "docs".

        Returns:
            List of result dicts with id, summary, score.
        """
        if domain == "code":
            args = {"repo": repo, "query": query, "max_results": max_results}
            if kind:
                args["kind"] = kind
            if scope:
                args["file_pattern"] = scope
            result = self._call("code", "search_symbols", args)
            return result.get("symbols", [])
        else:
            args = {"repo": repo, "query": query, "max_results": max_results}
            if scope:
                args["doc_path"] = scope
            result = self._call("docs", "search_sections", args)
            return result.get("sections", [])

    def retrieve(
        self,
        id: str,
        repo: str,
        verify: bool = False,
        context_lines: int = 0,
        domain: str = "code",
    ) -> dict:
        """
        Fetch the full content of a symbol or section by stable ID.

        jMRI method: retrieve(id)
        Maps to: get_symbol (code) or get_section (docs)

        Args:
            id: Stable identifier from search() results.
            repo: Repository identifier.
            verify: Check content hash for source drift.
            context_lines: Surrounding lines to include (code only).
            domain: "code" or "docs".

        Returns:
            Dict with source/content, _meta with tokens_saved.
        """
        if domain == "code":
            args = {"repo": repo, "symbol_id": id, "verify": verify, "context_lines": context_lines}
            return self._call("code", "get_symbol", args)
        else:
            args = {"repo": repo, "section_id": id, "verify": verify}
            return self._call("docs", "get_section", args)

    def retrieve_batch(self, ids: list[str], repo: str, domain: str = "code") -> list[dict]:
        """
        Fetch multiple symbols or sections in one call.

        jMRI method: retrieve(ids) — batch variant
        Maps to: get_symbols (code) or get_sections (docs)
        """
        if domain == "code":
            result = self._call("code", "get_symbols", {"repo": repo, "symbol_ids": ids})
            return result.get("symbols", [])
        else:
            result = self._call("docs", "get_sections", {"repo": repo, "section_ids": ids})
            return result.get("sections", [])

    def metadata(self, repo: str, id: str = None, domain: str = "code") -> dict:
        """
        Get index statistics and token cost estimates.

        jMRI method: metadata(id?)
        Maps to: get_repo_outline (code) or get_toc (docs)
        """
        if domain == "code":
            result = self._call("code", "get_repo_outline", {"repo": repo})
        else:
            result = self._call("docs", "get_toc", {"repo": repo})
        return result

    # ------------------------------------------------------------------
    # Convenience methods (beyond jMRI minimum)
    # ------------------------------------------------------------------

    def index(self, path: str, domain: str = "code", use_ai_summaries: bool = False) -> dict:
        """Index a local folder."""
        if domain == "code":
            return self._call("code", "index_folder", {"path": path, "use_ai_summaries": use_ai_summaries})
        else:
            return self._call("docs", "index_local", {"path": path, "use_ai_summaries": use_ai_summaries})

    def toc(self, repo: str, nested: bool = False) -> dict:
        """Get table of contents for a doc repo."""
        tool = "get_toc_tree" if nested else "get_toc"
        return self._call("docs", tool, {"repo": repo})

    def file_outline(self, repo: str, file_path: str) -> dict:
        """Get all symbols in a file."""
        return self._call("code", "get_file_outline", {"repo": repo, "file_path": file_path})

    # ------------------------------------------------------------------
    # Transport
    # ------------------------------------------------------------------

    def _call(self, domain: str, tool_name: str, args: dict) -> dict:
        cmd = self._code_cmd if domain == "code" else self._doc_cmd
        if cmd is None:
            server = "jcodemunch-mcp" if domain == "code" else "jdocmunch-mcp"
            raise MRIError("NOT_INSTALLED", f"{server} not found. Install with: uvx {server}")

        self._call_id += 1
        init_msg = json.dumps({
            "jsonrpc": "2.0", "id": 0, "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "mri-client", "version": __version__}
            }
        })
        call_msg = json.dumps({
            "jsonrpc": "2.0", "id": self._call_id, "method": "tools/call",
            "params": {"name": tool_name, "arguments": args}
        })

        try:
            proc = subprocess.run(
                cmd,
                input=f"{init_msg}\n{call_msg}\n",
                capture_output=True, text=True,
                timeout=self._timeout
            )
        except subprocess.TimeoutExpired:
            raise MRIError("TIMEOUT", f"Server timed out after {self._timeout}s")
        except FileNotFoundError:
            raise MRIError("NOT_INSTALLED", f"Server command not found: {cmd}")

        lines = [l.strip() for l in proc.stdout.strip().splitlines() if l.strip()]
        for line in reversed(lines):
            try:
                parsed = json.loads(line)
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


# ------------------------------------------------------------------
# CLI convenience
# ------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser(description="mri_client CLI")
    sub = parser.add_subparsers(dest="cmd")

    disc = sub.add_parser("discover", help="List indexed repos")
    disc.add_argument("--domain", default="code", choices=["code", "docs"])

    srch = sub.add_parser("search", help="Search for symbols/sections")
    srch.add_argument("query")
    srch.add_argument("--repo", required=True)
    srch.add_argument("--domain", default="code", choices=["code", "docs"])
    srch.add_argument("--max", type=int, default=5)

    retr = sub.add_parser("retrieve", help="Retrieve a symbol/section by ID")
    retr.add_argument("id")
    retr.add_argument("--repo", required=True)
    retr.add_argument("--domain", default="code", choices=["code", "docs"])

    args = parser.parse_args()
    client = MRIClient()

    if args.cmd == "discover":
        sources = client.discover(args.domain)
        for s in sources:
            print(f"  {s.get('repo')} — {s.get('symbol_count', s.get('section_count', '?'))} items")

    elif args.cmd == "search":
        results = client.search(args.query, args.repo, max_results=args.max, domain=args.domain)
        for r in results:
            print(f"  {r.get('id')}")
            print(f"    {r.get('summary', r.get('title', ''))}")

    elif args.cmd == "retrieve":
        result = client.retrieve(args.id, args.repo, domain=args.domain)
        print(result.get("source", result.get("content", "")))
        meta = result.get("_meta", {})
        if meta:
            print(f"\n[tokens saved: {meta.get('tokens_saved', '?'):,}]")

    else:
        parser.print_help()
