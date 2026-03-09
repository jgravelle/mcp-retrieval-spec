# Cursor Integration

Add jCodeMunch and jDocMunch to Cursor.

## Setup

In Cursor settings → MCP (or edit `.cursor/mcp.json` in your project):

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

## Usage

Once connected, you can ask Cursor's AI to:

- "Index this project for efficient retrieval"
- "Find the authentication middleware in this codebase"
- "What does the rate limiting code do?"

The agent will use `search_symbols` → `get_symbol` instead of reading whole files.

## Cursor-Specific Notes

- Cursor uses the MCP tools transparently. You don't call them directly.
- The AI decides when to use jMRI tools vs. reading files. Adding index instructions to your project's `.cursorrules` helps guide it.

Example `.cursorrules` addition:
```
Use jcodemunch-mcp search_symbols and get_symbol for code navigation.
Use jdocmunch-mcp search_sections and get_section for documentation.
Only read full files when editing.
```
