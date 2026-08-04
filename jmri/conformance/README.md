# jMRI Conformance Suite

A portable test fixture any MCP retrieval server can run against itself
to validate jMRI v1.0 compliance.

## What it does

The suite runs a set of named **cases** against your server and produces
a markdown or JSON report. Cases split into two tiers:

| Tier | Severity | Effect |
|------|----------|--------|
| **Core** | MUST | All Core cases must pass for the server to claim jMRI-Core compliance. |
| **Full** | SHOULD | Full cases gate jMRI-Full compliance (which subsumes Core). |

Each case is named after the spec invariant it enforces — `core.search.returns_stubs_only`, `full.meta.tokens_saved_present`, etc. — so a failing report points the maintainer straight at the relevant `SPEC.md` section.

## Usage

```bash
pip install jmri-sdk
python -m jmri.conformance --repo owner/repo --server-cmd "jcodemunch-mcp"
```

By default, output is markdown to stdout. `--json` for a machine-readable payload, `--out FILE` to write to disk.

### Common invocations

Run against a locally-installed `jcodemunch-mcp` against a repo it has indexed:

```bash
python -m jmri.conformance --repo expressjs/express --server-label "jcodemunch-mcp 1.90.0"
```

Run against `uvx`-launched server, Core-only:

```bash
python -m jmri.conformance \
  --server-cmd "uvx jcodemunch-mcp" \
  --repo expressjs/express \
  --core-only
```

Run against `jdocmunch-mcp` (docs domain):

```bash
python -m jmri.conformance \
  --server-cmd "jdocmunch-mcp" \
  --domain docs \
  --repo my-docs-repo
```

Emit JSON for a CI dashboard:

```bash
python -m jmri.conformance --repo owner/repo --json --out conformance.json
```

### Programmatic use

```python
from jmri.client import MRIClient
from jmri.conformance import Adapter, run_conformance

client = MRIClient()
adapter = Adapter.from_mri_client(
    client,
    repo="owner/repo",
    server_label="jcodemunch-mcp 1.90.0",
)
report = run_conformance(adapter)
print(report.to_markdown())
assert report.core_compliant
```

## Verdict semantics

The runner returns a `ConformanceReport` whose `verdict` is one of:

- `jMRI-Full compliant` — all Core MUSTs and all Full SHOULDs pass.
- `jMRI-Core compliant; Full has N SHOULD shortfall(s)` — Core passes, Full has gaps.
- `jMRI-Core compliant (Full not assessed)` — Core passes, suite was run with `--core-only`.
- `NOT compliant — N Core MUST failure(s)` — at least one Core case failed.

CLI exit code is `0` for Core-compliant runs (with or without Full gaps) and `1` for non-compliant runs.

## What gets tested

### Core (jMRI-Core MUST)

- `core.discover.returns_list` — `discover()` returns a non-empty list of dicts.
- `core.discover.required_fields` — entries have `id` and `name` fields.
- `core.search.returns_stubs_only` — `search()` results don't inline full source content.
- `core.search.required_fields` — each result carries a stable id.
- `core.search.respects_max_results` — `max_results` cap honored.
- `core.retrieve.returns_content` — `retrieve(id)` returns recognizable body content.
- `core.retrieve.has_meta` — response includes the required `_meta` envelope.
- `core.retrieve.bad_id_returns_error` — bogus ids return a structured error, not a raw exception.
- `core.metadata.returns_dict` — `metadata()` returns a dict.

### Full (jMRI-Full SHOULD)

- `full.meta.tokens_saved_present` — `_meta.tokens_saved` is included.
- `full.meta.tokens_saved_nonneg` — value is a non-negative number.
- `full.meta.elapsed_ms_present` — `_meta.elapsed_ms` (or `timing_ms`) included.
- `full.meta.retrieval_version_present` — server advertises supported spec version.
- `full.search.deterministic_ids` — same query returns the same id sequence (cacheable).

## Self-reporting policy

Maintainers run conformance against their own servers and publish the resulting report. We don't run conformance against competitors and publish — running someone else's tests for them is adversarial and the wrong shape for a standards-bearer position.

If you're a third-party MCP retrieval tool and want to claim jMRI compliance:

1. Run the suite against your server.
2. Save the report (markdown + JSON).
3. Publish it next to your README.
4. Optionally open a PR against this repo adding a link in
   `reference/conformance-reports/<your-server>.md` so other users can find it.

## Adapter protocol

The runner doesn't talk MCP directly — it calls into an `Adapter`, a thin protocol covering the four jMRI operations. The bundled `Adapter.from_mri_client(...)` wraps an `MRIClient`; you can also pass arbitrary callables for testing or for non-MCP transports.

```python
from jmri.conformance import Adapter

adapter = Adapter(
    discover=my_discover_callable,    # () -> list[dict]
    search=my_search_callable,        # (query, **opts) -> list[dict]
    retrieve=my_retrieve_callable,    # (id, **opts) -> dict
    metadata=my_metadata_callable,    # (id?) -> dict
    repo="owner/repo",
)
```

This is also how the suite tests itself — every case has unit-test coverage against mock adapters in `tests/test_conformance.py`.
