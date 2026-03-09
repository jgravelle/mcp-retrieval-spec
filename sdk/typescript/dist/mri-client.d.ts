/**
 * mri-client.ts — TypeScript client for jMRI-compliant MCP servers.
 *
 * Calls jcodemunch-mcp / jdocmunch-mcp via child_process stdin/stdout.
 * Works with any jMRI-compliant server.
 *
 * License: Apache 2.0
 */
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
export declare class MRIError extends Error {
    code: string;
    detail?: Record<string, unknown> | undefined;
    constructor(code: string, message: string, detail?: Record<string, unknown> | undefined);
}
export declare class MRIClient {
    private codeCmd;
    private docCmd;
    private callId;
    constructor(options?: {
        codeCmd?: string[];
        docCmd?: string[];
    });
    /** discover() → list available knowledge sources */
    discover(domain?: "code" | "docs"): Promise<MRISource[]>;
    /** search(query, scope?) → ranked results with IDs */
    search(query: string, repo: string, options?: {
        scope?: string;
        kind?: string;
        maxResults?: number;
        domain?: "code" | "docs";
    }): Promise<MRISearchResult[]>;
    /** retrieve(id) → full source or section content */
    retrieve(id: string, repo: string, options?: {
        verify?: boolean;
        contextLines?: number;
        domain?: "code" | "docs";
    }): Promise<MRIPayload>;
    /** retrieve batch — multiple IDs in one call */
    retrieveBatch(ids: string[], repo: string, domain?: "code" | "docs"): Promise<MRIPayload[]>;
    /** metadata(id?) → index stats and token cost estimates */
    metadata(repo: string, domain?: "code" | "docs"): Promise<MRIPayload>;
    private call;
}
//# sourceMappingURL=mri-client.d.ts.map