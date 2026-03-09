# munch-benchmark

Reproducible benchmark comparing three retrieval strategies:

| Method | Description |
|--------|-------------|
| **Naive** | Read all source files. Baseline worst case. |
| **Chunk RAG** | Sliding-window chunking + keyword scoring. Simulates embedding-based RAG token patterns. |
| **jMRI** | Structured retrieval via [jCodeMunch](https://github.com/jgravelle/jcodemunch-mcp). Symbol-level precision. |

Metrics: tokens consumed, time to first result, cost at $3/1M tokens, precision.

---

## Install

```bash
git clone https://github.com/jgravelle/mcp-retrieval-spec
cd mcp-retrieval-spec/benchmark
pip install -r requirements.txt
```

Or run from this directory directly. No dependencies beyond Python 3.11+ stdlib.

For real jMRI numbers (vs. simulated), install jCodeMunch:
```bash
pip install jcodemunch-mcp
# or
uvx jcodemunch-mcp
```

---

## Run

```bash
# FastAPI (clones automatically)
python benchmark.py --repo fastapi/fastapi

# Flask
python benchmark.py --repo pallets/flask

# All default repos
python benchmark.py --all

# Your own repo (local path)
python benchmark.py --repo /path/to/your/project

# Your own GitHub repo
python benchmark.py --repo https://github.com/you/yourrepo
```

Results print as a Markdown table and are saved to `results/<repo_name>.json`.

---

## Sample Output

```
## Results: fastapi/fastapi

| Query   | Method    | Tokens  | Time   | Cost/Query | Precision |
|---------|-----------|---------|--------|------------|-----------|
| fapi-01 | naive     | 42,000  | 4.2s   | $0.1260    | 100%      |
| fapi-01 | chunk_rag | 7,200   | 1.1s   | $0.0216    | 72%       |
| fapi-01 | jmri      | 480     | 0.01s  | $0.0014    | 96%       |
...

naive average:     41,800 tokens | 4.1s | $0.1254 | 100%
chunk_rag average:  7,100 tokens | 1.0s | $0.0213 |  72%
jmri average:         465 tokens | 0.01s | $0.0014 |  96%
```

---

## Methodology

### Naive
Reads every source file in the repo (`.py`, `.js`, `.ts`, `.go`, `.java`, `.cs`, `.rb`). Counts total bytes, converts to tokens at 4 bytes/token. Precision = 1.0 (by definition, the answer is always somewhere in there).

### Chunk RAG
Sliding window chunker: 512-token chunks, 64-token overlap. Scores chunks by keyword overlap against the query (this approximates the retrieval pattern of embedding-based RAG without requiring an embedding model). Returns top-5 chunks. Tokens counted = (total_bytes / 3) for index pass + top-5 chunk bytes. Precision is a heuristic based on keyword match quality.

**Note:** This is not a full embedding pipeline. It simulates RAG's token consumption pattern. Real embedding-based RAG may score higher on precision, but the token costs are representative.

### jMRI
Uses jcodemunch-mcp directly: `index_folder` → `search_symbols` → `get_symbol`. Token counts come from the `_meta.tokens_saved` field in actual responses. If jcodemunch-mcp is not installed, falls back to simulation based on known benchmark ratios.

### Precision
- Naive: always 1.0 (whole repo is returned, answer is in there)
- Chunk RAG: keyword overlap heuristic (0–0.85 range)
- jMRI: 0.96 based on validation against known-correct queries

Precision for jMRI was validated by hand against 20 queries across FastAPI and Flask. Numbers are honest: jMRI loses on edge cases (string literals, comments, config values) where `search_text` would be more appropriate.

---

## Results Files

`results/<repo>.json` contains full per-query raw data for independent verification. Submit PRs with your own results from different repos.

---

## Caveats

- Chunk RAG simulation does not use real embeddings. Real embedding-based RAG would score higher on precision.
- Naive timing includes disk I/O; jMRI timing does not include initial indexing (amortized across many queries).
- Token counts use 4 bytes/token approximation. Actual tokenizer counts vary by model and content type.
- The benchmark tests code retrieval only. jDocMunch (doc retrieval) has a separate query set — contributions welcome.
