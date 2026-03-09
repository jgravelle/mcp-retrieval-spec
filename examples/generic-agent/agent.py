"""
generic-agent/agent.py — Minimal jMRI-powered agent.

Demonstrates the canonical jMRI workflow:
  discover → search → retrieve → use

Requires: pip install anthropic
And a jMRI-compliant server (jcodemunch-mcp).
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../sdk/python"))

from mri_client import MRIClient, MRIError
import anthropic

SYSTEM_PROMPT = """You are a code assistant with access to token-efficient retrieval tools.

When asked about code:
1. Call discover() to see what repos are available.
2. Call search() to find relevant symbols by intent.
3. Call retrieve() to get exact source for the top result.
4. Answer based on what you retrieved — not general knowledge.

Always report the tokens_saved from _meta so the user can see the efficiency gain."""

TOOLS = [
    {
        "name": "discover",
        "description": "List indexed code repositories.",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "search",
        "description": "Find relevant code symbols. Returns IDs and summaries.",
        "input_schema": {
            "type": "object",
            "required": ["query", "repo"],
            "properties": {
                "query": {"type": "string"},
                "repo": {"type": "string"},
                "max_results": {"type": "integer", "default": 5}
            }
        }
    },
    {
        "name": "retrieve",
        "description": "Get full source for a symbol by ID.",
        "input_schema": {
            "type": "object",
            "required": ["id", "repo"],
            "properties": {
                "id": {"type": "string"},
                "repo": {"type": "string"}
            }
        }
    }
]


def run_tool(client: MRIClient, tool_name: str, tool_input: dict) -> str:
    try:
        if tool_name == "discover":
            sources = client.discover()
            return f"Available repos: {[s['repo'] for s in sources]}"

        elif tool_name == "search":
            results = client.search(
                tool_input["query"],
                tool_input["repo"],
                max_results=tool_input.get("max_results", 5)
            )
            if not results:
                return "No results found."
            lines = []
            for r in results:
                lines.append(f"  {r['id']}")
                if r.get("summary"):
                    lines.append(f"    {r['summary']}")
            return "\n".join(lines)

        elif tool_name == "retrieve":
            result = client.retrieve(tool_input["id"], tool_input["repo"])
            source = result.get("source", "No source found")
            meta = result.get("_meta", {})
            saved = meta.get("tokens_saved", 0)
            return f"{source}\n\n[tokens saved: {saved:,}]"

    except MRIError as e:
        return f"Error: {e}"

    return "Unknown tool"


def chat(question: str):
    mri = MRIClient()
    claude = anthropic.Anthropic()

    messages = [{"role": "user", "content": question}]

    while True:
        response = claude.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages
        )

        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    print(block.text)
            break

        # Process tool calls
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                print(f"[calling {block.name}({block.input})]")
                result = run_tool(mri, block.name, block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result
                })

        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python agent.py 'your question about the code'")
        sys.exit(1)

    question = " ".join(sys.argv[1:])
    print(f"Question: {question}\n")
    chat(question)
