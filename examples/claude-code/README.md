# Claude Code Integration

Add jCodeMunch and jDocMunch to Claude Code in two minutes.

## Setup

Edit `~/.claude.json` and add to the `mcpServers` block:

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

If `~/.claude.json` doesn't exist yet, create it with the full structure above.

Restart Claude Code. Run `/mcp` to confirm both servers are connected.

## Usage Pattern

Add to your project's `CLAUDE.md` or global `~/.claude/CLAUDE.md`:

```markdown
## Token-Efficient Context Retrieval

Always use jcodemunch-mcp and jdocmunch-mcp for code/doc context.

1. Call list_repos to see what's indexed.
2. If not indexed, use index_folder (code) or index_local (docs).
3. Use search_symbols / search_sections to find relevant context.
4. Use get_symbol / get_section to fetch exact content.
5. Fall back to direct file reads only when editing files.
```

## Verify It's Working

In Claude Code:
```
/mcp
```
Should show both servers as connected.

Then ask Claude to index your project:
> "Index C:/path/to/my/project for code retrieval"

Claude will call `index_folder` and confirm with symbol/file counts.

## Token Savings

Every response from jCodeMunch/jDocMunch includes `_meta.tokens_saved`.
Claude Code users typically see 95–99% token reduction on code navigation tasks.

The community meter at j.gravelle.us/jCodeMunch shows aggregate savings across all users.
