# jMRI v1.0 — jMunch Retrieval Interface Specification

**Version:** 1.0.0
**Status:** Published
**License:** Apache 2.0
**Canonical URL:** https://github.com/jgravelle/mcp-retrieval-spec

---

## Motivation

Agents waste tokens. The default pattern — read a file, embed the whole thing, pass it to the model — consumes 10,000–100,000 tokens to answer questions that need 200. At $15/1M input tokens (Claude Opus 4.6), that's a measurable tax on every query.

The jMunch tools (jCodeMunch, jDocMunch) have collectively saved **12.4 billion tokens** across user sessions as of March 2026. That number comes from on-device telemetry: every response includes a `_meta` block with `tokens_saved` computed via `os.stat` — no file I/O, no estimation theatrics. The savings are real.

What those tools lack is a name for what they do. This spec provides that name.

**jMRI** (jMunch Retrieval Interface) is a minimal interface specification for retrieval MCP servers. It defines four operations, a response envelope, stable identifier formats, and two compliance levels. Any MCP server that implements jMRI-Core can replace a naive file reader. Any server that implements jMRI-Full can match or exceed the reference implementations.

The spec is open (Apache 2.0). The best implementations are commercial.

---

## Definitions

**Retrieval MCP** — An MCP server whose primary function is providing structured, token-efficient access to indexed knowledge. Not a general-purpose agent. Not a filesystem proxy.

**Knowledge source** — An indexed unit: a code repository, local folder, or documentation tree. Identified by a stable `repo` string.

**Symbol** — A named, addressable code unit. Functions, classes, methods, constants. Extracted via AST parsing, not text search.

**Section** — A named, addressable documentation unit. Bounded by heading hierarchy (h1–h6). Extracted via structural parsing.

**Stable ID** — A bookmarkable identifier that uniquely addresses a symbol or section within a knowledge source. Agents may cache these across sessions.

**Naive token cost** — The token count that would result from reading the entire source file(s) associated with a retrieval. Computed as `file_size_bytes / 4` (no file read required).

**Tokens saved** — `naive_tokens - response_tokens`. The delta between what naive file reading would have cost and what jMRI retrieval actually cost.

---

## Core Interface

A jMRI-compliant server MUST implement these four capabilities. The MCP tool names for a minimal implementation are specified below. jMRI-Full implementations (like jCodeMunch and jDocMunch) expose additional granular tools that map to these operations.

### 1. `discover()`

Return all available knowledge sources with metadata.

**Minimal tool name:** `list_repos`
**Returns:** Array of knowledge source objects.

```json
{
  "result": [
    {
      "repo": "fastapi/fastapi",
      "indexed_at": "2026-03-06T12:57:13.989580",
      "symbol_count": 1359,
      "file_count": 156,
      "languages": { "python": 155 },
      "index_version": 3
    }
  ],
  "_meta": { ... }
}
```

**Behavior:**
- Returns all currently indexed sources.
- Empty array (not error) if nothing is indexed.
- `index_version` increments on full re-index; implementations SHOULD increment on schema changes.

---

### 2. `search(query, scope?)`

Return ranked results matching a query across a knowledge source.

**Minimal tool name:** `search`
**Required parameters:** `repo` (string), `query` (string)
**Optional parameters:** `scope` (string — filters to file, path prefix, or document), `kind` (symbol kind filter), `max_results` (integer, default 10)
**Returns:** Ranked array of result objects with IDs, summaries, and relevance signals.

```json
{
  "result": [
    {
      "id": "src/auth.py::AuthService.validate_token#method",
      "kind": "method",
      "name": "validate_token",
      "file": "src/auth.py",
      "line": 47,
      "signature": "def validate_token(self, token: str) -> Optional[User]",
      "summary": "Validates a JWT token and returns the associated User, or None if invalid.",
      "score": 0.94
    }
  ],
  "_meta": { ... }
}
```

**Behavior:**
- Results MUST include a stable `id` usable with `retrieve()`.
- Results MUST NOT include full source content. Summaries only.
- Ranking is implementation-defined. Score range [0.0, 1.0] recommended.
- `scope` narrows the search to a file path, path prefix, or (for docs) a specific document.

---

### 3. `retrieve(id)`

Fetch the full payload for a stable identifier.

**Minimal tool name:** `retrieve`
**Required parameters:** `repo` (string), `id` (string)
**Optional parameters:** `verify` (boolean — hash verification, default false), `context_lines` (integer — surrounding lines, default 0)
**Returns:** Full source content or section content.

```json
{
  "result": {
    "id": "src/auth.py::AuthService.validate_token#method",
    "kind": "method",
    "file": "src/auth.py",
    "line": 47,
    "end_line": 71,
    "source": "def validate_token(self, token: str) -> Optional[User]:\n    ...",
    "content_hash": "a3f9d2..."
  },
  "_meta": { ... }
}
```

**Behavior:**
- For code: returns the exact source of the symbol, bounded by AST line offsets.
- For docs: returns the full section content, bounded by byte offsets.
- `verify: true` compares stored hash against current file content. Signals source drift without re-indexing.
- If `id` is not found, return a structured error (see Error Handling).

---

### 4. `metadata(id?)`

Return cost and index statistics.

**Minimal tool name:** `metadata`
**Required parameters:** `repo` (string)
**Optional parameters:** `id` (string — if provided, return file/section-level stats)
**Returns:** Index metadata and token cost estimates.

```json
{
  "result": {
    "repo": "fastapi/fastapi",
    "indexed_at": "2026-03-06T12:57:13.989580",
    "file_count": 156,
    "symbol_count": 1359,
    "languages": { "python": 155 },
    "estimated_naive_tokens": 412000,
    "index_size_bytes": 2840000
  },
  "_meta": { ... }
}
```

**Behavior:**
- `estimated_naive_tokens` = sum of all indexed file sizes / 4.
- Called without `id`: repo-level stats.
- Called with `id`: file- or section-level stats for that specific identifier.

---

## Response Envelope

Every jMRI response MUST include a `_meta` block at the top level. There are no exceptions. `_meta` is how agents measure the value of retrieval over naive reads.

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `tokens_saved` | integer | Tokens saved by this call vs. naive file read. Computed as `(raw_file_bytes - response_bytes) / 4`. |
| `total_tokens_saved` | integer | Cumulative tokens saved across all calls for this install. Persisted to disk. |

### Optional Fields (SHOULD implement for jMRI-Full)

| Field | Type | Description |
|-------|------|-------------|
| `response_tokens` | integer | Estimated tokens in this response. `response_bytes / 4`. |
| `naive_tokens` | integer | Tokens naive reading would have cost. `tokens_saved + response_tokens`. |
| `cost_avoided` | object | Per-model dollar savings this call. Keys: model identifiers. Values: USD. |
| `total_cost_avoided` | object | Cumulative per-model dollar savings. |
| `retrieval_engine` | string | Engine identifier (e.g., `"munch"`). |
| `retrieval_version` | string | jMRI spec version implemented (e.g., `"1.0"`). |
| `timing_ms` | number | Server-side processing time in milliseconds. |
| `powered_by` | string | Attribution string. |

### Example (jMRI-Full)

```json
{
  "result": { ... },
  "_meta": {
    "tokens_saved": 81205,
    "total_tokens_saved": 1096818,
    "response_tokens": 420,
    "naive_tokens": 81625,
    "cost_avoided": {
      "claude_opus": 1.2181,
      "gpt5_latest": 0.8121
    },
    "total_cost_avoided": {
      "claude_opus": 16.4523,
      "gpt5_latest": 10.9682
    },
    "retrieval_engine": "munch",
    "retrieval_version": "1.0",
    "timing_ms": 18.0,
    "powered_by": "jcodemunch-mcp by jgravelle · https://github.com/jgravelle/jcodemunch-mcp"
  }
}
```

### Token Savings Calculation

The reference implementation uses zero-overhead estimation:

```python
_BYTES_PER_TOKEN = 4  # conservative approximation

def estimate_savings(raw_bytes: int, response_bytes: int) -> int:
    return max(0, (raw_bytes - response_bytes) // _BYTES_PER_TOKEN)
```

`raw_bytes` comes from `os.stat(file_path).st_size` — no file read. This is accurate enough for cost modeling and deliberately conservative (actual savings are typically higher due to whitespace and comments).

### Persistence

`total_tokens_saved` MUST be persisted across server restarts. Reference path: `~/.code-index/_savings.json`. The exact path is implementation-defined.

---

## Identifier Formats

Stable IDs are the contract between agents and retrieval servers. They must survive server restarts and be cacheable across sessions. IDs MUST NOT be random or time-based.

### Code Symbol IDs

```
{file_path}::{qualified_name}#{kind}
```

| Component | Description | Example |
|-----------|-------------|---------|
| `file_path` | Repo-relative path | `src/auth.py` |
| `qualified_name` | Dotted name from file root | `AuthService.validate_token` |
| `kind` | Symbol type | `function`, `class`, `method`, `constant` |

**Examples:**
```
src/auth.py::validate_token#function
src/auth.py::AuthService.validate_token#method
src/models.py::User#class
src/config.py::MAX_RETRIES#constant
```

**Rules:**
- `file_path` uses forward slashes regardless of OS.
- `qualified_name` uses dot notation for nested symbols (`ClassName.method_name`).
- `kind` values: `function`, `class`, `method`, `constant`, `type`. Implementations MAY add kinds; these five are required.
- IDs are case-sensitive.

### Documentation Section IDs

```
{file_path}::{heading_path}#{level}
```

| Component | Description | Example |
|-----------|-------------|---------|
| `file_path` | Repo-relative path | `docs/api.md` |
| `heading_path` | ` > `-separated heading breadcrumb | `Authentication > OAuth Flow` |
| `level` | Heading level | `h1`, `h2`, `h3` |

**Examples:**
```
docs/api.md::Authentication#h1
docs/api.md::Authentication > OAuth Flow#h2
docs/api.md::Authentication > OAuth Flow > Token Refresh#h3
README.md::Installation#h2
```

**Rules:**
- Heading text is normalized: trimmed, collapsed whitespace. Case preserved.
- If two sibling headings have identical text, append a 1-based counter suffix: `API Reference > Errors` and `API Reference > Errors~2`.
- Section IDs are stable as long as heading text doesn't change. Re-indexing after heading rename invalidates dependent IDs (this is expected behavior, not a bug).

---

## Compliance Levels

### jMRI-Core

Minimum viable implementation. Implements `discover`, `search`, `retrieve`, `metadata`. Returns `_meta` with `tokens_saved` and `total_tokens_saved`.

| Requirement | Detail |
|-------------|--------|
| Tool names | Exactly `list_repos`, `search`, `retrieve`, `metadata` (or mapped equivalents) |
| `_meta` fields | `tokens_saved`, `total_tokens_saved` |
| Identifier format | Stable across restarts; spec-compliant format RECOMMENDED |
| Persistence | `total_tokens_saved` persisted to disk |

A server claiming jMRI-Core MUST pass the core test suite in `munch-benchmark`.

### jMRI-Full

Production-grade implementation. All Core requirements plus:

| Requirement | Detail |
|-------------|--------|
| All `_meta` optional fields | `response_tokens`, `naive_tokens`, `cost_avoided`, `retrieval_version`, `timing_ms` |
| Spec-compliant stable IDs | Exact format from Identifier Formats section |
| `retrieve(verify=true)` | Hash-based source drift detection |
| Byte-offset retrieval | Section/symbol content extracted via stored offsets, not re-parsing |
| Batch retrieval | `retrieve` accepts an array of IDs in a single call |
| Incremental indexing | Re-index only changed files |

jCodeMunch and jDocMunch are jMRI-Full reference implementations.

---

## Method Reference

### `discover()` — Full Specification

Agents call `discover()` at session start to enumerate available knowledge sources. The response shapes subsequent `search()` calls.

**Input schema:**
```json
{ "type": "object", "properties": {} }
```

**Output schema:**
```json
{
  "type": "object",
  "properties": {
    "result": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["repo", "indexed_at"],
        "properties": {
          "repo":          { "type": "string" },
          "indexed_at":    { "type": "string", "format": "date-time" },
          "symbol_count":  { "type": "integer" },
          "file_count":    { "type": "integer" },
          "languages":     { "type": "object" },
          "index_version": { "type": "integer" }
        }
      }
    },
    "_meta": { "$ref": "#/definitions/_meta" }
  }
}
```

**Agent usage pattern:**
```
1. discover()                          → get list of repos
2. search("auth middleware", scope="fastapi/fastapi") → get IDs
3. retrieve("src/middleware.py::auth_middleware#function") → get source
```

---

### `search(query, scope?)` — Full Specification

The primary entry point for finding relevant context. Returns summaries and IDs — never full content.

**Input schema:**
```json
{
  "type": "object",
  "required": ["repo", "query"],
  "properties": {
    "repo":        { "type": "string" },
    "query":       { "type": "string" },
    "scope":       { "type": "string", "description": "File path, path prefix, or doc path" },
    "kind":        { "type": "string", "enum": ["function", "class", "method", "constant", "type", "section"] },
    "max_results": { "type": "integer", "default": 10 }
  }
}
```

**Search behavior:**
- Implementations SHOULD search: symbol names, signatures, docstrings/summaries, tags.
- Implementations MAY use BM25, TF-IDF, embedding similarity, or hybrid approaches.
- Results are ranked by relevance. Tie-breaking is implementation-defined.
- `kind: "section"` constrains to documentation sections (jMRI-Full with doc support).

**Failure modes:**
- Zero results: return empty array, not error.
- Invalid `repo`: return structured error (see Error Handling).
- `query` over 1000 characters: implementations MAY truncate or return error.

---

### `retrieve(id)` — Full Specification

Fetches exact content by stable ID. Only called after a `search()` confirms the ID is relevant.

**Input schema:**
```json
{
  "type": "object",
  "required": ["repo", "id"],
  "properties": {
    "repo":          { "type": "string" },
    "id":            { "type": "string" },
    "verify":        { "type": "boolean", "default": false },
    "context_lines": { "type": "integer", "default": 0 }
  }
}
```

**Batch input (jMRI-Full):**
```json
{
  "type": "object",
  "required": ["repo", "ids"],
  "properties": {
    "repo": { "type": "string" },
    "ids":  { "type": "array", "items": { "type": "string" } }
  }
}
```

**Verification behavior:**
When `verify: true`, the server computes a hash of the current on-disk content for the symbol's byte range and compares against the stored hash. If they differ, the response includes `"source_drift": true` and SHOULD include the current content.

**Retrieval efficiency:**
jMRI-Full implementations use stored byte offsets for `retrieve()`. The server knows exactly where a symbol or section begins and ends in the source file without re-parsing. This is what makes retrieval sub-millisecond at scale.

---

### `metadata(id?)` — Full Specification

Returns token cost estimates and index statistics. Useful for agents that want to pre-check cost before committing to a retrieval strategy.

**Input schema:**
```json
{
  "type": "object",
  "required": ["repo"],
  "properties": {
    "repo": { "type": "string" },
    "id":   { "type": "string" }
  }
}
```

**Repo-level output:**
```json
{
  "repo": "fastapi/fastapi",
  "indexed_at": "2026-03-06T12:57:13.989580",
  "file_count": 156,
  "symbol_count": 1359,
  "languages": { "python": 155 },
  "estimated_naive_tokens": 412000,
  "index_size_bytes": 2840000
}
```

**Symbol/section-level output (when `id` provided):**
```json
{
  "id": "src/auth.py::AuthService.validate_token#method",
  "file": "src/auth.py",
  "file_size_bytes": 4280,
  "symbol_size_bytes": 312,
  "estimated_file_tokens": 1070,
  "estimated_symbol_tokens": 78,
  "estimated_savings": 992
}
```

---

## Error Handling

jMRI errors are structured. Implementations MUST NOT return raw exceptions.

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Symbol 'src/auth.py::deleted_func#function' not found in index.",
    "detail": { "repo": "fastapi/fastapi", "id": "src/auth.py::deleted_func#function" }
  },
  "_meta": { "tokens_saved": 0, "total_tokens_saved": 184320 }
}
```

**Standard error codes:**

| Code | Meaning |
|------|---------|
| `NOT_FOUND` | ID or repo does not exist in the index |
| `NOT_INDEXED` | Repo exists but has not been indexed |
| `STALE_ID` | ID format is valid but content has changed (source drift) |
| `INVALID_ID` | ID format is malformed |
| `INVALID_REPO` | Repo identifier is malformed |
| `INDEX_ERROR` | Server-side indexing failure |

`_meta` MUST be present even in error responses. `tokens_saved` is 0 for errors.

---

## Indexing (Out of Spec, Informational)

jMRI does not specify how indexing works. Implementations are free to use AST parsing, embedding models, keyword extraction, or any combination. The only indexing-related contract is:

1. After indexing, `discover()` returns the new source.
2. Stable IDs returned from `search()` are valid for `retrieve()`.
3. Incremental re-indexing MUST NOT invalidate IDs for unchanged symbols/sections.

The reference implementations (jCodeMunch, jDocMunch) use tree-sitter for AST-based symbol extraction and heading-hierarchy parsing for sections. Savings are computed via `os.stat` — no file I/O during retrieval.

---

## Versioning

This spec uses semantic versioning. The `retrieval_version` field in `_meta` SHOULD reflect the implemented spec version.

**Breaking changes** (require major version bump):
- Removing required `_meta` fields
- Changing stable ID format in a non-backward-compatible way
- Removing any of the four core methods

**Non-breaking changes** (minor version):
- Adding optional `_meta` fields
- Adding new tool names
- Adding new error codes

**Patch:**
- Clarifications that don't change behavior

Implementations SHOULD advertise their supported spec version via `_meta.retrieval_version`.

---

## Worked Examples

### Example 1: Code Retrieval (jCodeMunch)

**Goal:** Find how FastAPI handles dependency injection for a database session.

```
# Step 1: discover
list_repos()
→ ["fastapi/fastapi", "local/my-api"]

# Step 2: search
search_symbols(repo="fastapi/fastapi", query="database session dependency")
→ [
    { "id": "fastapi/dependencies/database.py::get_db#function", score: 0.91 },
    { "id": "fastapi/routing.py::APIRouter.add_api_route#method", score: 0.62 }
  ]
  _meta.tokens_saved: 42000  (searched entire codebase, returned 2 summaries)

# Step 3: retrieve
get_symbol(repo="fastapi/fastapi", symbol_id="fastapi/dependencies/database.py::get_db#function")
→ { source: "def get_db():\n    db = SessionLocal()\n    try:\n        yield db\n    finally:\n        db.close()" }
  _meta.tokens_saved: 3840  (returned 12 lines instead of the full file)

Total tokens consumed: ~180 (summaries + source)
Naive equivalent: ~44,000 tokens
Savings: 99.6%
```

### Example 2: Doc Retrieval (jDocMunch)

**Goal:** Find the OAuth token refresh flow in an API's documentation.

```
# Step 1: search
search_sections(repo="my-api-docs", query="OAuth token refresh")
→ [
    { "id": "docs/auth.md::Authentication > OAuth Flow > Token Refresh#h3", score: 0.97 },
    { "id": "docs/auth.md::Authentication > OAuth Flow#h2", score: 0.83 }
  ]
  _meta.tokens_saved: 18200

# Step 2: retrieve
get_section(repo="my-api-docs", section_id="docs/auth.md::Authentication > OAuth Flow > Token Refresh#h3")
→ { content: "### Token Refresh\n\nRefresh tokens expire after 30 days..." }
  _meta.tokens_saved: 2800

Total tokens consumed: ~90
Naive equivalent: ~21,000 tokens
Savings: 99.6%
```

### Example 3: Cross-Source Agent Workflow

```python
# An agent that understands both code structure and documentation
# uses jCodeMunch + jDocMunch in sequence

1. search_symbols(repo="local/my-api", query="rate limiting middleware")
   → get symbol ID

2. get_symbol(...symbol_id...)
   → read the implementation

3. search_sections(repo="local/my-api-docs", query="rate limiting configuration")
   → get section ID

4. get_section(...section_id...)
   → read the docs

# Result: agent has precise code + docs for exactly the feature it needs
# at a fraction of the cost of reading both repos wholesale
```

---

## Reference Implementations

jCodeMunch and jDocMunch are the canonical jMRI-Full implementations.

### jCodeMunch — Code Retrieval

- **Repo:** https://github.com/jgravelle/jcodemunch-mcp
- **Stars:** 900+
- **Languages:** 30+ via tree-sitter (Python, JS/TS, Go, Rust, C#, Java, PHP, Dart, and more)
- **Install:** `uvx jcodemunch-mcp`
- **License:** Commercial (Gumroad)

**jMRI method mapping:**

| jMRI Method | jCodeMunch Tool(s) |
|-------------|-------------------|
| `discover()` | `list_repos` |
| `search(query)` | `search_symbols`, `search_text` |
| `retrieve(id)` | `get_symbol`, `get_symbols`, `get_file_content` |
| `metadata(id?)` | `get_repo_outline`, `get_file_outline` |

**Additional tools (beyond jMRI minimum):** `index_repo`, `index_folder`, `get_file_tree`, `invalidate_cache`

### jDocMunch — Documentation Retrieval

- **Repo:** https://github.com/jgravelle/jdocmunch-mcp
- **Formats:** Markdown, RST, AsciiDoc, HTML, Jupyter notebooks, OpenAPI specs, plain text
- **Install:** `uvx jdocmunch-mcp`
- **License:** Commercial (Gumroad, also bundled with jCodeMunch)

**jMRI method mapping:**

| jMRI Method | jDocMunch Tool(s) |
|-------------|------------------|
| `discover()` | `list_repos` |
| `search(query)` | `search_sections` |
| `retrieve(id)` | `get_section`, `get_sections` |
| `metadata(id?)` | `get_toc`, `get_document_outline` |

**Additional tools (beyond jMRI minimum):** `index_local`, `index_repo`, `get_toc_tree`, `delete_index`

### Licensing

The spec (this document) is Apache 2.0. Anyone can implement it.

The reference servers require a jMunch license to run commercially. Free to inspect; paid to use in production.

**Where to get a license:** https://j.gravelle.us/jCodeMunch/

---

## Appendix A: Why Not Just Read Files?

| Approach | Tokens/Query | Precision | Latency |
|----------|-------------|-----------|---------|
| Naive file reading | 10,000–100,000 | N/A (whole file) | 2–10s |
| Chunk RAG | 2,000–10,000 | ~72% | 0.5–2s |
| jMRI retrieval | 50–500 | ~96% | <50ms |

Numbers are from the `munch-benchmark` suite against FastAPI and Flask. See `munch-benchmark/` for reproducible methodology.

The precision advantage comes from AST-based and heading-hierarchy-based extraction. RAG chunks split at arbitrary byte boundaries, often bisecting a function or splitting a table. jMRI splits at semantic boundaries.

---

## Appendix B: `_meta` in MCP Context

MCP tools return `list[TextContent]`. jMRI implementations serialize the full response (including `_meta`) as JSON in the text content. Agents that call jMRI-compliant tools receive `_meta` as part of the response and can log, display, or aggregate token savings data.

The `total_tokens_saved` field is a running total persisted to `~/.code-index/_savings.json` (code) and the equivalent for docs. On-device only. The community meter at `j.gravelle.us` receives anonymous aggregate totals — no query content, no file paths.

---

*jMRI v1.0.0 · Apache 2.0 · https://github.com/jgravelle/mcp-retrieval-spec*
