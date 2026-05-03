/**
 * NodeWeaver TypeScript HTTP Client
 *
 * Drop this file into `server/lib/nodeweaver-client.ts` in the AxTask repo.
 * No framework dependencies — uses the native `fetch` API (Node 18+).
 *
 * Required env vars (AxTask side):
 *   NODEWEAVER_BASE_URL   - e.g. https://nodeweaver.example.com
 *   NODEWEAVER_API_KEY    - shared secret, must match NodeWeaver's NODEWEAVER_API_KEY
 */

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface NodeWeaverConfig {
  baseUrl: string;
  apiKey?: string;
  timeoutMs?: number;
  maxRetries?: number;
}

export interface HealthResponse {
  status: "healthy" | "degraded";
  service: string;
  version: string;
  api_version: string;
  components: {
    database: "healthy" | "unhealthy";
    embedding_model: "ready" | "unavailable";
  };
  timestamp: string;
}

export interface ClassifyRequest {
  text: string;
  metadata?: Record<string, unknown>;
}

export interface ClassifyResponse {
  predicted_category: string;
  confidence_score: number;
  similar_topics: SimilarTopic[];
  similar_nodes: SimilarNode[];
  processing_time: number;
  log_id?: number;
}

export interface SimilarTopic {
  topic_id?: number;
  label?: string;
  similarity?: number;
  [key: string]: unknown;
}

export interface SimilarNode {
  node_id?: number;
  content?: string;
  similarity?: number;
  [key: string]: unknown;
}

export interface BatchClassifyRequest {
  texts: string[];
}

export interface BatchClassifyResponse {
  results: (ClassifyResponse | { error: string })[];
  batch_size: number;
  processing_time: number;
}

export interface TopicsResponse {
  topics: TopicItem[];
  pagination: Pagination;
}

export interface TopicItem {
  topic_id: number;
  label: string;
  category: string;
  total_weight: number;
  coherence_score: number;
  origin_node_ids: number[];
  metadata?: Record<string, unknown>;
  created_at?: string;
}

export interface Pagination {
  page: number;
  per_page: number;
  total: number;
  pages: number;
  has_next: boolean;
  has_prev: boolean;
}

// ---------------------------------------------------------------------------
// Error types
// ---------------------------------------------------------------------------

export class NodeWeaverError extends Error {
  constructor(
    message: string,
    public readonly statusCode?: number,
    public readonly responseBody?: unknown,
  ) {
    super(message);
    this.name = "NodeWeaverError";
  }
}

export class NodeWeaverAuthError extends NodeWeaverError {
  constructor() {
    super("Invalid or missing X-API-Key", 401);
    this.name = "NodeWeaverAuthError";
  }
}

export class NodeWeaverTimeoutError extends NodeWeaverError {
  constructor(timeoutMs: number) {
    super(`Request timed out after ${timeoutMs}ms`);
    this.name = "NodeWeaverTimeoutError";
  }
}

// ---------------------------------------------------------------------------
// Client
// ---------------------------------------------------------------------------

export class NodeWeaverClient {
  private readonly baseUrl: string;
  private readonly apiKey: string | undefined;
  private readonly timeoutMs: number;
  private readonly maxRetries: number;

  constructor(config?: Partial<NodeWeaverConfig>) {
    this.baseUrl = (
      config?.baseUrl ??
      process.env.NODEWEAVER_BASE_URL ??
      "http://localhost:5000"
    ).replace(/\/$/, "");

    this.apiKey =
      config?.apiKey ?? process.env.NODEWEAVER_API_KEY ?? undefined;
    this.timeoutMs = config?.timeoutMs ?? 10_000;
    this.maxRetries = config?.maxRetries ?? 3;
  }

  // -------------------------------------------------------------------------
  // Public API
  // -------------------------------------------------------------------------

  /** Poll connectivity — no auth required. */
  async health(): Promise<HealthResponse> {
    return this._request<HealthResponse>("GET", "/api/v1/health", undefined, {
      skipAuth: true,
    });
  }

  /** Classify a single piece of text. */
  async classify(req: ClassifyRequest): Promise<ClassifyResponse> {
    return this._request<ClassifyResponse>("POST", "/api/v1/classify", req);
  }

  /** Classify up to 100 texts in one call. */
  async classifyBatch(
    req: BatchClassifyRequest,
  ): Promise<BatchClassifyResponse> {
    return this._request<BatchClassifyResponse>(
      "POST",
      "/api/v1/classify/batch",
      req,
    );
  }

  /**
   * List topics with optional filtering.
   * @param params - query params forwarded to NodeWeaver
   */
  async getTopics(params?: {
    category?: string;
    min_weight?: number;
    min_coherence?: number;
    page?: number;
    per_page?: number;
  }): Promise<TopicsResponse> {
    const qs = params
      ? "?" + new URLSearchParams(params as Record<string, string>).toString()
      : "";
    return this._request<TopicsResponse>("GET", `/api/v1/topics${qs}`);
  }

  /**
   * Trigger topic detection on the server.
   *
   * Note: with the default SimpleRAGEngine, this returns existing topics as a
   * placeholder. Genuine new-topic emergence events are fired to AxTask via the
   * AXTASK_WEBHOOK_URL webhook rather than polled here.
   */
  async detectTopics(): Promise<{
    message: string;
    emerging_topics: number;
    topics: TopicItem[];
  }> {
    return this._request("POST", "/api/v1/topics/detect");
  }

  /**
   * Find topics semantically similar to the given text.
   * @param text - query text
   * @param limit - max results (server cap: 50)
   * @param threshold - similarity threshold 0–1 (default 0.5)
   */
  async findSimilarTopics(
    text: string,
    limit = 10,
    threshold = 0.5,
  ): Promise<{ input_text: string; similar_topics: unknown[]; count: number }> {
    return this._request("POST", "/api/v1/topics/similar", {
      text,
      limit,
      threshold,
    });
  }

  // -------------------------------------------------------------------------
  // Internal helpers
  // -------------------------------------------------------------------------

  private _buildHeaders(skipAuth = false): HeadersInit {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      "User-Agent": "AxTask-NodeWeaverClient/1.0",
    };
    if (!skipAuth && this.apiKey) {
      headers["X-API-Key"] = this.apiKey;
    }
    return headers;
  }

  private async _request<T>(
    method: "GET" | "POST",
    path: string,
    body?: unknown,
    opts?: { skipAuth?: boolean },
  ): Promise<T> {
    const url = `${this.baseUrl}${path}`;
    let lastError: Error | undefined;

    for (let attempt = 0; attempt <= this.maxRetries; attempt++) {
      if (attempt > 0) {
        const backoffMs = Math.min(200 * 2 ** (attempt - 1), 4_000);
        await _sleep(backoffMs);
      }

      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), this.timeoutMs);

      try {
        const res = await fetch(url, {
          method,
          headers: this._buildHeaders(opts?.skipAuth),
          body: body !== undefined ? JSON.stringify(body) : undefined,
          signal: controller.signal,
        });

        clearTimeout(timer);

        if (res.status === 401) throw new NodeWeaverAuthError();

        if (!res.ok) {
          let detail: unknown;
          try {
            detail = await res.json();
          } catch {
            detail = await res.text();
          }
          throw new NodeWeaverError(
            `NodeWeaver responded with HTTP ${res.status}`,
            res.status,
            detail,
          );
        }

        return (await res.json()) as T;
      } catch (err) {
        clearTimeout(timer);

        if (err instanceof NodeWeaverAuthError) throw err;

        if ((err as Error).name === "AbortError") {
          throw new NodeWeaverTimeoutError(this.timeoutMs);
        }

        lastError = err as Error;

        // Non-retriable: 4xx client errors (except 429)
        if (
          err instanceof NodeWeaverError &&
          err.statusCode !== undefined &&
          err.statusCode >= 400 &&
          err.statusCode < 500 &&
          err.statusCode !== 429
        ) {
          throw err;
        }
      }
    }

    throw lastError ?? new NodeWeaverError("Request failed after retries");
  }
}

function _sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// ---------------------------------------------------------------------------
// Singleton factory (mirrors dispatcher.ts import style)
// ---------------------------------------------------------------------------

let _default: NodeWeaverClient | undefined;

export function getNodeWeaverClient(
  config?: Partial<NodeWeaverConfig>,
): NodeWeaverClient {
  if (!_default || config) {
    _default = new NodeWeaverClient(config);
  }
  return _default;
}

export default NodeWeaverClient;
