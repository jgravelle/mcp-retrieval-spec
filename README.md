# mcp-retrieval-spec

The jMRI (jMunch Retrieval Interface) specification — an open interface standard for token-efficient context retrieval in MCP servers.

---

## What Is jMRI?

Agents that read whole files to answer specific questions waste 99% of their token budget. jMRI is a minimal interface for MCP servers that do retrieval right: index once, search by intent, retrieve exactly what you need.

Four operations. One response envelope. Two compliance levels.

**The problem in numbers:** A typical FastAPI codebase costs ~42,000 tokens to read naively. jMRI retrieval of the same answer costs ~480 tokens. At $3/1M tokens, that's $0.126 vs. $0.0014 per query. Across millions of queries, the savings are material.

The jMunch tools have saved **12.4 billion tokens** across user sessions as of March 3, 2026. This spec is the formal definition of what they do.

---

## How It Works

```
Agent
  │
  ├─ discover()    → What knowledge sources are available?
  ├─ search(query) → Which symbols/sections are relevant? (IDs + summaries only)
  ├─ retrieve(id)  → Give me the exact source for this ID.
  └─ metadata(id?) → What would naive reading have cost?
```

Every response includes a `_meta` block with `tokens_saved` and `total_tokens_saved`. Agents can see exactly what they're saving on every call.

---

## Spec

→ [SPEC.md](./SPEC.md)

The full jMRI v1.0 specification. Apache 2.0. Implement it however you want.

---

## Reference Implementations

The spec is open. The best implementations are commercial.

| Implementation | Domain | Stars | Install |
|----------------|--------|-------|---------|
| [jCodeMunch](https://github.com/jgravelle/jcodemunch-mcp) | Code (30+ languages) | 900+ | `uvx jcodemunch-mcp` |
| [jDocMunch](https://github.com/jgravelle/jdocmunch-mcp) | Docs (MD, RST, HTML, notebooks) | 45+ | `uvx jdocmunch-mcp` |

Both implement jMRI-Full. Licenses available at https://j.gravelle.us/jCodeMunch/

---

## Quick Start

### Using the Python SDK

```python
from sdk.python.mri_client import MRIClient

client = MRIClient()  # connects to local jcodemunch-mcp

# List available repos
sources = client.discover()

# Search
results = client.search("database session dependency", repo="fastapi/fastapi")
for r in results:
    print(r["id"], r["summary"])

# Retrieve
symbol = client.retrieve(results[0]["id"], repo="fastapi/fastapi")
print(symbol["source"])
print(f"Tokens saved: {symbol['_meta']['tokens_saved']:,}")
```

### Claude Code Integration

Add to your `~/.claude.json`:

```json
{
  "mcpServers": {
    "jcodemunch-mcp": {
      "command": "uvx",
      "args": ["jcodemunch-mcp"]
    },
    "jdocmunch-mcp": {
      "command": "uvx",
      "args": ["jdocmunch-mcp"]
    }
  }
}
```

See [examples/claude-code/](./examples/claude-code/) for full setup.

### Cursor Integration

See [examples/cursor/](./examples/cursor/).

---

## Repo Structure

```
mcp-retrieval-spec/
├── SPEC.md                    # The jMRI specification (Apache 2.0)
├── CHANGELOG.md               # Spec version history
├── LICENSE                    # Spec: Apache 2.0. Reference impls: commercial.
├── reference/
│   ├── server.py              # Minimal jMRI-compliant server
│   └── config.example.json   # Sample configuration
├── sdk/
│   ├── python/mri_client.py  # Python client helper (Apache 2.0)
│   └── typescript/mri-client.ts
├── examples/
│   ├── claude-code/           # Claude Code integration
│   ├── cursor/                # Cursor integration
│   └── generic-agent/         # Minimal jMRI agent
└── benchmark/                 # munch-benchmark suite
```

---

## Licensing

| Component | License |
|-----------|---------|
| SPEC.md | Apache 2.0 — implement freely |
| SDK clients | Apache 2.0 — use freely |
| Reference server | Requires jMunch license for commercial use |
| Benchmark suite | Apache 2.0 |

This is the [Stripe model](https://stripe.com/docs/api): the API spec is open and well-documented; the best implementation is commercial.

---

## Benchmark

→ [benchmark/](./benchmark/)

Clone and run in under 5 minutes. Compares Naive, Chunk RAG, and jMRI on FastAPI and Flask. Results are honest: if RAG beats jMRI on a metric, it's reported.

Real numbers on FastAPI (950K naive tokens):

| Method | Avg Tokens | Cost/Query | Precision |
|--------|-----------|------------|-----------|
| Naive (read all files) | 949,904 | $2.85 | 100% |
| Chunk RAG | 330,372 | $0.99 | 74% |
| **jMRI** | **480** | **$0.0014** | **96%** |

**1,979x fewer tokens than naive. Higher precision than RAG.**

---

## Contributing

The spec is intentionally minimal. PRs that extend the core interface require strong justification. PRs that improve examples, fix errors, or add language-specific SDK clients are welcome.

Open an issue before proposing spec changes.
