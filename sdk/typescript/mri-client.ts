/**
 * mri-client.ts — TypeScript client for jMRI-compliant MCP servers.
 *
 * Calls jcodemunch-mcp / jdocmunch-mcp via child_process stdin/stdout.
 * Works with any jMRI-compliant server.
 *
 * License: Apache 2.0
 */

import { spawn } from "child_process";

const MRI_VERSION = "1.0.0";

export interface MRISource {
  repo: string;
  indexed_at: string;
  symbol_count?: number;
  file_count?: number;
  languages?: Record<string, number>;
  index_version?: number;
}

export interface MRISearchResult {
  id: string;
  kind?: string;
  name?: string;
  file?: string;
  line?: number;
  signature?: string;
  summary?: string;
  score?: number;
}

export interface MRIMeta {
  tokens_saved: number;
  total_tokens_saved: number;
  response_tokens?: number;
  naive_tokens?: number;
  cost_avoided?: Record<string, number>;
  timing_ms?: number;
}

export interface MRIPayload {
  [key: string]: unknown;
  _meta?: MRIMeta;
}

export class MRIError extends Error {
  constructor(
    public code: string,
    message: string,
    public detail?: Record<string, unknown>
  ) {
    super(`[${code}] ${message}`);
    this.name = "MRIError";
  }
}

export class MRIClient {
  private codeCmd: string[];
  private docCmd: string[];
  private callId = 0;

  constructor(options?: { codeCmd?: string[]; docCmd?: string[] }) {
    this.codeCmd = options?.codeCmd ?? ["uvx", "jcodemunch-mcp"];
    this.docCmd = options?.docCmd ?? ["uvx", "jdocmunch-mcp"];
  }

  // ------------------------------------------------------------------
  // jMRI Core Interface
  // ------------------------------------------------------------------

  /** discover() → list available knowledge sources */
  async discover(domain: "code" | "docs" = "code"): Promise<MRISource[]> {
    const result = await this.call(domain, "list_repos", {});
    return (result as { repos?: MRISource[] }).repos ?? [];
  }

  /** search(query, scope?) → ranked results with IDs */
  async search(
    query: string,
    repo: string,
    options?: {
      scope?: string;
      kind?: string;
      maxResults?: number;
      domain?: "code" | "docs";
    }
  ): Promise<MRISearchResult[]> {
    const domain = options?.domain ?? "code";
    if (domain === "code") {
      const args: Record<string, unknown> = {
        repo,
        query,
        max_results: options?.maxResults ?? 10,
      };
      if (options?.kind) args.kind = options.kind;
      if (options?.scope) args.file_pattern = options.scope;
      const result = await this.call("code", "search_symbols", args);
      return (result as { symbols?: MRISearchResult[] }).symbols ?? [];
    } else {
      const args: Record<string, unknown> = {
        repo,
        query,
        max_results: options?.maxResults ?? 10,
      };
      if (options?.scope) args.doc_path = options.scope;
      const result = await this.call("docs", "search_sections", args);
      return (result as { sections?: MRISearchResult[] }).sections ?? [];
    }
  }

  /** retrieve(id) → full source or section content */
  async retrieve(
    id: string,
    repo: string,
    options?: {
      verify?: boolean;
      contextLines?: number;
      domain?: "code" | "docs";
    }
  ): Promise<MRIPayload> {
    const domain = options?.domain ?? "code";
    if (domain === "code") {
      return this.call("code", "get_symbol", {
        repo,
        symbol_id: id,
        verify: options?.verify ?? false,
        context_lines: options?.contextLines ?? 0,
      });
    } else {
      return this.call("docs", "get_section", {
        repo,
        section_id: id,
        verify: options?.verify ?? false,
      });
    }
  }

  /** retrieve batch — multiple IDs in one call */
  async retrieveBatch(
    ids: string[],
    repo: string,
    domain: "code" | "docs" = "code"
  ): Promise<MRIPayload[]> {
    if (domain === "code") {
      const result = await this.call("code", "get_symbols", { repo, symbol_ids: ids });
      return (result as { symbols?: MRIPayload[] }).symbols ?? [];
    } else {
      const result = await this.call("docs", "get_sections", { repo, section_ids: ids });
      return (result as { sections?: MRIPayload[] }).sections ?? [];
    }
  }

  /** metadata(id?) → index stats and token cost estimates */
  async metadata(repo: string, domain: "code" | "docs" = "code"): Promise<MRIPayload> {
    const tool = domain === "code" ? "get_repo_outline" : "get_toc";
    return this.call(domain, tool, { repo });
  }

  // ------------------------------------------------------------------
  // Transport
  // ------------------------------------------------------------------

  private call(
    domain: "code" | "docs",
    toolName: string,
    args: Record<string, unknown>
  ): Promise<MRIPayload> {
    const cmd = domain === "code" ? this.codeCmd : this.docCmd;
    const [bin, ...binArgs] = cmd;

    return new Promise((resolve, reject) => {
      const proc = spawn(bin, binArgs, { stdio: ["pipe", "pipe", "pipe"] });

      let stdout = "";
      let stderr = "";

      proc.stdout.on("data", (chunk: Buffer) => { stdout += chunk.toString(); });
      proc.stderr.on("data", (chunk: Buffer) => { stderr += chunk.toString(); });

      proc.on("error", (err: Error) => {
        reject(new MRIError("NOT_INSTALLED", `Server command failed: ${err.message}`));
      });

      proc.on("close", () => {
        const lines = stdout.trim().split("\n").map((l) => l.trim()).filter(Boolean);
        for (let i = lines.length - 1; i >= 0; i--) {
          try {
            const parsed = JSON.parse(lines[i]);
            if (parsed.result?.content?.[0]?.text) {
              const payload = JSON.parse(parsed.result.content[0].text);
              if (payload.error) {
                const e = payload.error;
                reject(new MRIError(e.code ?? "ERROR", e.message ?? "Unknown", e.detail));
                return;
              }
              resolve(payload);
              return;
            }
          } catch {
            // continue
          }
        }
        reject(new MRIError("PARSE_ERROR", `No parseable response. stderr: ${stderr.slice(0, 200)}`));
      });

      const initMsg = JSON.stringify({
        jsonrpc: "2.0",
        id: 0,
        method: "initialize",
        params: {
          protocolVersion: "2024-11-05",
          capabilities: {},
          clientInfo: { name: "mri-client-ts", version: MRI_VERSION },
        },
      });

      const callMsg = JSON.stringify({
        jsonrpc: "2.0",
        id: ++this.callId,
        method: "tools/call",
        params: { name: toolName, arguments: args },
      });

      proc.stdin.write(initMsg + "\n");
      proc.stdin.write(callMsg + "\n");
      proc.stdin.end();
    });
  }
}
