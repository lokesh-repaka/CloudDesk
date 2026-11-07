/**
 * CloudDesk Support Platform — Typed API Client (CLAUDE.md §11)
 *
 * Single, canonical gateway for all frontend interactions with the backend API.
 * Features:
 * - Full TypeScript typing mirrored from API_CONTRACT.md and types.ts
 * - Automatic JWT Bearer token injection from localStorage
 * - Automatic 401 handling with redirection to /login?reason=expired
 * - Typed NetworkError envelope with automatic and manual retry capability
 * - Structured domain namespaces (auth, tickets, customers, knowledge, approvals, escalations, agents, mcp, health)
 */

import {
  AgentTopologyResponse,
  ApprovalRequestResponse,
  ApprovalStatus,
  ApproveDecisionRequest,
  CustomerDetail,
  CustomerListResponse,
  CustomerMemory,
  CustomerMemoryCreate,
  DemoTokensResponse,
  EscalateRequest,
  EscalateResponse,
  EscalationResponse,
  KnowledgeArticleDetail,
  KnowledgeArticleSummary,
  KnowledgeEvidence,
  KnowledgeReindexResponse,
  KnowledgeSearchRequest,
  LoginRequest,
  McpToolDefinition,
  RejectDecisionRequest,
  ReplyCreate,
  ReplyResponse,
  RequestInfoCreate,
  TicketCreate,
  TicketDetail,
  TicketFilterParams,
  TicketListResponse,
  TokenResponse,
  UserProfileResponse,
  WorkflowEvent,
  WorkflowRunResponse,
  WorkflowStateResponse,
} from "./types";

export const TOKEN_STORAGE_KEY = "clouddesk_jwt_token";

/**
 * Custom error thrown when the server returns an HTTP error status.
 */
export class ApiClientError extends Error {
  status: number;
  detail: string | Array<{ loc: string[]; msg: string; type: string }>;
  url: string;
  method: string;

  constructor(
    message: string,
    status: number,
    detail: string | Array<{ loc: string[]; msg: string; type: string }>,
    url: string,
    method: string = "GET"
  ) {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
    this.detail = detail;
    this.url = url;
    this.method = method;
  }
}

/**
 * Custom error thrown on fetch network failures (connection refused, DNS failure, offline).
 * Provides a retry function to trigger re-execution.
 */
export class NetworkError extends Error {
  url: string;
  method: string;
  isRetryable: boolean = true;
  originalError: unknown;
  retry: () => Promise<unknown>;

  constructor(
    message: string,
    url: string,
    method: string,
    retryFn: () => Promise<unknown>,
    originalError?: unknown
  ) {
    super(message);
    this.name = "NetworkError";
    this.url = url;
    this.method = method;
    this.retry = retryFn;
    this.originalError = originalError;
  }
}

/**
 * Custom error thrown on HTTP 401 Unauthorized responses.
 */
export class AuthExpiredError extends ApiClientError {
  constructor(url: string, method: string) {
    super("Authentication session has expired", 401, "Session expired", url, method);
    this.name = "AuthExpiredError";
  }
}

// ----------------------------------------------------------------------------
// Token Storage Helpers (Client-side safe)
// ----------------------------------------------------------------------------

export function getToken(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    return window.localStorage.getItem(TOKEN_STORAGE_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string): void {
  if (typeof window === "undefined") {
    return;
  }
  try {
    window.localStorage.setItem(TOKEN_STORAGE_KEY, token);
  } catch {
    // Ignore storage quota or private browsing exceptions
  }
}

export function clearToken(): void {
  if (typeof window === "undefined") {
    return;
  }
  try {
    window.localStorage.removeItem(TOKEN_STORAGE_KEY);
  } catch {
    // Ignore storage exceptions
  }
}

// ----------------------------------------------------------------------------
// API Base Configuration
// ----------------------------------------------------------------------------

export function getApiBaseUrl(): string {
  const envUrl = process.env.NEXT_PUBLIC_API_URL;
  if (envUrl && envUrl.trim().length > 0) {
    return envUrl.replace(/\/+$/, "");
  }
  return "http://localhost:8000";
}

export interface RequestOptions extends RequestInit {
  params?: Record<string, string | number | boolean | undefined | null>;
  skipAuth?: boolean;
  retries?: number;
  retryDelayMs?: number;
}

/**
 * Core HTTP dispatch function with error classification, token injection, and retry logic.
 */
export async function request<T>(
  endpoint: string,
  options: RequestOptions = {}
): Promise<T> {
  const baseUrl = getApiBaseUrl();
  const cleanEndpoint = endpoint.startsWith("/") ? endpoint : `/${endpoint}`;

  // Build query string if params are provided
  let url = `${baseUrl}${cleanEndpoint}`;
  if (options.params) {
    const searchParams = new URLSearchParams();
    for (const [key, value] of Object.entries(options.params)) {
      if (value !== undefined && value !== null && value !== "") {
        searchParams.append(key, String(value));
      }
    }
    const queryString = searchParams.toString();
    if (queryString) {
      url += `?${queryString}`;
    }
  }

  const method = options.method || "GET";
  const headers = new Headers(options.headers || {});

  if (!headers.has("Accept")) {
    headers.set("Accept", "application/json");
  }

  // Set Content-Type only if request has a body and header is not already set
  if (options.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  // Inject Bearer token if available and not skipped
  if (!options.skipAuth) {
    const token = getToken();
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }
  }

  const executeFetch = async (currentAttempt: number): Promise<T> => {
    let response: Response;
    try {
      response = await fetch(url, {
        ...options,
        method,
        headers,
      });
    } catch (err: unknown) {
      const maxRetries = options.retries ?? (method === "GET" ? 2 : 0);
      if (currentAttempt < maxRetries) {
        const delay = (options.retryDelayMs ?? 400) * Math.pow(2, currentAttempt);
        await new Promise((resolve) => setTimeout(resolve, delay));
        return executeFetch(currentAttempt + 1);
      }

      const networkErr = new NetworkError(
        `Network connection to ${url} failed. Backend may be offline.`,
        url,
        method,
        () => request<T>(endpoint, options),
        err
      );
      throw networkErr;
    }

    // Handle HTTP 401 Unauthorized -> redirect to /login?reason=expired
    if (response.status === 401) {
      clearToken();
      if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
        window.location.href = "/login?reason=expired";
      }
      throw new AuthExpiredError(url, method);
    }

    // Handle other non-2xx HTTP responses
    if (!response.ok) {
      let detail: string | Array<{ loc: string[]; msg: string; type: string }> =
        response.statusText;
      try {
        const errorBody = await response.json();
        if (errorBody && errorBody.detail) {
          detail = errorBody.detail;
        }
      } catch {
        // Body was not JSON
      }

      const errorMessage =
        typeof detail === "string"
          ? detail
          : Array.isArray(detail)
          ? detail.map((d) => d.msg).join("; ")
          : `HTTP Error ${response.status}`;

      throw new ApiClientError(errorMessage, response.status, detail, url, method);
    }

    // Success response parsing
    if (response.status === 204) {
      return undefined as unknown as T;
    }

    try {
      return (await response.json()) as T;
    } catch (err) {
      throw new ApiClientError(
        "Failed to parse server JSON response",
        response.status,
        String(err),
        url,
        method
      );
    }
  };

  return executeFetch(0);
}

// ----------------------------------------------------------------------------
// Domain Namespaces
// ----------------------------------------------------------------------------

export const api = {
  // Authentication & Demo Tokens
  auth: {
    login: (credentials: LoginRequest) =>
      request<TokenResponse>("/api/v1/auth/login", {
        method: "POST",
        body: JSON.stringify(credentials),
        skipAuth: true,
      }),

    getDemoTokens: () =>
      request<DemoTokensResponse>("/api/v1/auth/demo-tokens", {
        method: "GET",
        skipAuth: true,
      }),

    getMe: () => request<UserProfileResponse>("/api/v1/auth/me", { method: "GET" }),

    refresh: () =>
      request<TokenResponse>("/api/v1/auth/refresh", {
        method: "POST",
      }),
  },

  // Support Tickets API
  tickets: {
    list: (params?: TicketFilterParams) =>
      request<TicketListResponse>("/api/v1/tickets", {
        method: "GET",
        params: params as Record<string, string | number | boolean | undefined | null>,
      }),

    get: (id: string) =>
      request<TicketDetail>(`/api/v1/tickets/${encodeURIComponent(id)}`, {
        method: "GET",
      }),

    create: (data: TicketCreate) =>
      request<TicketDetail>("/api/v1/tickets", {
        method: "POST",
        body: JSON.stringify(data),
      }),

    runWorkflow: (id: string) =>
      request<WorkflowRunResponse>(
        `/api/v1/tickets/${encodeURIComponent(id)}/run`,
        { method: "POST" }
      ),

    getWorkflowState: (id: string) =>
      request<WorkflowStateResponse>(
        `/api/v1/tickets/${encodeURIComponent(id)}/workflow`,
        { method: "GET" }
      ),

    getEvents: (id: string) =>
      request<WorkflowEvent[]>(
        `/api/v1/tickets/${encodeURIComponent(id)}/events`,
        { method: "GET" }
      ),

    reply: (id: string, data: ReplyCreate) =>
      request<ReplyResponse>(
        `/api/v1/tickets/${encodeURIComponent(id)}/reply`,
        {
          method: "POST",
          body: JSON.stringify(data),
        }
      ),

    requestInfo: (id: string, data: RequestInfoCreate) =>
      request<ReplyResponse>(
        `/api/v1/tickets/${encodeURIComponent(id)}/request-info`,
        {
          method: "POST",
          body: JSON.stringify(data),
        }
      ),

    escalate: (id: string, data: EscalateRequest) =>
      request<EscalateResponse>(
        `/api/v1/tickets/${encodeURIComponent(id)}/escalate`,
        {
          method: "POST",
          body: JSON.stringify(data),
        }
      ),
  },

  // Customers 360-Degree Dossier API
  customers: {
    list: (params?: { offset?: number; limit?: number; query?: string }) =>
      request<CustomerListResponse>("/api/v1/customers", {
        method: "GET",
        params,
      }),

    get: (id: string) =>
      request<CustomerDetail>(`/api/v1/customers/${encodeURIComponent(id)}`, {
        method: "GET",
      }),

    addMemory: (id: string, data: CustomerMemoryCreate) =>
      request<CustomerMemory>(
        `/api/v1/customers/${encodeURIComponent(id)}/memory`,
        {
          method: "POST",
          body: JSON.stringify(data),
        }
      ),
  },

  // Knowledge Base & RAG Index API
  knowledge: {
    search: (params: KnowledgeSearchRequest) =>
      request<{ query: string; evidence: KnowledgeEvidence[] }>(
        "/api/v1/knowledge/search",
        {
          method: "POST",
          body: JSON.stringify(params),
        }
      ),

    reindex: () =>
      request<KnowledgeReindexResponse>("/api/v1/knowledge/reindex", {
        method: "POST",
      }),

    listArticles: () =>
      request<KnowledgeArticleSummary[]>("/api/v1/knowledge/articles", {
        method: "GET",
      }),

    getArticle: (id: string) =>
      request<KnowledgeArticleDetail>(
        `/api/v1/knowledge/articles/${encodeURIComponent(id)}`,
        { method: "GET" }
      ),
  },

  // Human Approval Governance API
  approvals: {
    list: (params?: { status?: ApprovalStatus; ticket_id?: string }) =>
      request<ApprovalRequestResponse[]>("/api/v1/approvals", {
        method: "GET",
        params,
      }),

    approve: (id: string, data?: ApproveDecisionRequest) =>
      request<ApprovalRequestResponse>(
        `/api/v1/approvals/${encodeURIComponent(id)}/approve`,
        {
          method: "POST",
          body: data ? JSON.stringify(data) : undefined,
        }
      ),

    reject: (id: string, data: RejectDecisionRequest) =>
      request<ApprovalRequestResponse>(
        `/api/v1/approvals/${encodeURIComponent(id)}/reject`,
        {
          method: "POST",
          body: JSON.stringify(data),
        }
      ),
  },

  // Specialist Escalations Queue API
  escalations: {
    list: (params?: { status?: string; target_team?: string }) =>
      request<EscalationResponse[]>("/api/v1/escalations", {
        method: "GET",
        params,
      }),

    get: (id: string) =>
      request<EscalationResponse>(
        `/api/v1/escalations/${encodeURIComponent(id)}`,
        { method: "GET" }
      ),

    updateStatus: (
      id: string,
      status: "open" | "in_investigation" | "resolved" | "cancelled"
    ) =>
      request<EscalationResponse>(
        `/api/v1/escalations/${encodeURIComponent(id)}`,
        {
          method: "PATCH",
          body: JSON.stringify({ status }),
        }
      ),
  },

  // Specialist Agents & Topology API
  agents: {
    getTopology: () =>
      request<AgentTopologyResponse>("/api/v1/agents", {
        method: "GET",
      }),
  },

  // Model Context Protocol (MCP) Tool Discovery API
  mcp: {
    getTools: () =>
      request<{ tools: McpToolDefinition[] }>("/api/v1/mcp/tools", {
        method: "GET",
      }),
  },

  // Health Check Probes
  health: {
    checkLive: () =>
      request<{ status: string }>("/health/live", {
        method: "GET",
        skipAuth: true,
      }),

    checkReady: () =>
      request<{ status: string; checks?: Record<string, string> }>(
        "/health/ready",
        {
          method: "GET",
          skipAuth: true,
        }
      ),

    check: () =>
      request<{ status: string }>("/health", {
        method: "GET",
        skipAuth: true,
      }),
  },
};

export default api;

