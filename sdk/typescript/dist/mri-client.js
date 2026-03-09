"use strict";
/**
 * mri-client.ts — TypeScript client for jMRI-compliant MCP servers.
 *
 * Calls jcodemunch-mcp / jdocmunch-mcp via child_process stdin/stdout.
 * Works with any jMRI-compliant server.
 *
 * License: Apache 2.0
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.MRIClient = exports.MRIError = void 0;
const child_process_1 = require("child_process");
const MRI_VERSION = "1.0.0";
class MRIError extends Error {
    constructor(code, message, detail) {
        super(`[${code}] ${message}`);
        this.code = code;
        this.detail = detail;
        this.name = "MRIError";
    }
}
exports.MRIError = MRIError;
class MRIClient {
    constructor(options) {
        this.callId = 0;
        this.codeCmd = options?.codeCmd ?? ["uvx", "jcodemunch-mcp"];
        this.docCmd = options?.docCmd ?? ["uvx", "jdocmunch-mcp"];
    }
    // ------------------------------------------------------------------
    // jMRI Core Interface
    // ------------------------------------------------------------------
    /** discover() → list available knowledge sources */
    async discover(domain = "code") {
        const result = await this.call(domain, "list_repos", {});
        return result.repos ?? [];
    }
    /** search(query, scope?) → ranked results with IDs */
    async search(query, repo, options) {
        const domain = options?.domain ?? "code";
        if (domain === "code") {
            const args = {
                repo,
                query,
                max_results: options?.maxResults ?? 10,
            };
            if (options?.kind)
                args.kind = options.kind;
            if (options?.scope)
                args.file_pattern = options.scope;
            const result = await this.call("code", "search_symbols", args);
            return result.symbols ?? [];
        }
        else {
            const args = {
                repo,
                query,
                max_results: options?.maxResults ?? 10,
            };
            if (options?.scope)
                args.doc_path = options.scope;
            const result = await this.call("docs", "search_sections", args);
            return result.sections ?? [];
        }
    }
    /** retrieve(id) → full source or section content */
    async retrieve(id, repo, options) {
        const domain = options?.domain ?? "code";
        if (domain === "code") {
            return this.call("code", "get_symbol", {
                repo,
                symbol_id: id,
                verify: options?.verify ?? false,
                context_lines: options?.contextLines ?? 0,
            });
        }
        else {
            return this.call("docs", "get_section", {
                repo,
                section_id: id,
                verify: options?.verify ?? false,
            });
        }
    }
    /** retrieve batch — multiple IDs in one call */
    async retrieveBatch(ids, repo, domain = "code") {
        if (domain === "code") {
            const result = await this.call("code", "get_symbols", { repo, symbol_ids: ids });
            return result.symbols ?? [];
        }
        else {
            const result = await this.call("docs", "get_sections", { repo, section_ids: ids });
            return result.sections ?? [];
        }
    }
    /** metadata(id?) → index stats and token cost estimates */
    async metadata(repo, domain = "code") {
        const tool = domain === "code" ? "get_repo_outline" : "get_toc";
        return this.call(domain, tool, { repo });
    }
    // ------------------------------------------------------------------
    // Transport
    // ------------------------------------------------------------------
    call(domain, toolName, args) {
        const cmd = domain === "code" ? this.codeCmd : this.docCmd;
        const [bin, ...binArgs] = cmd;
        return new Promise((resolve, reject) => {
            const proc = (0, child_process_1.spawn)(bin, binArgs, { stdio: ["pipe", "pipe", "pipe"] });
            let stdout = "";
            let stderr = "";
            proc.stdout.on("data", (chunk) => { stdout += chunk.toString(); });
            proc.stderr.on("data", (chunk) => { stderr += chunk.toString(); });
            proc.on("error", (err) => {
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
                    }
                    catch {
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
exports.MRIClient = MRIClient;
//# sourceMappingURL=mri-client.js.map