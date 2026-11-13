import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import {
  api,
  getToken,
  setToken,
  clearToken,
  TOKEN_STORAGE_KEY,
  getApiBaseUrl,
  ApiClientError,
  NetworkError,
  AuthExpiredError,
  request,
} from "../lib/api";

describe("Typed API Client (CLAUDE.md §11)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  describe("Token Storage Management", () => {
    it("reads and writes tokens to localStorage correctly", () => {
      const mockStorage: Record<string, string> = {};
      const storageMock = {
        getItem: vi.fn((key: string) => mockStorage[key] ?? null),
        setItem: vi.fn((key: string, val: string) => {
          mockStorage[key] = val;
        }),
        removeItem: vi.fn((key: string) => {
          delete mockStorage[key];
        }),
      };

      vi.stubGlobal("localStorage", storageMock);
      vi.stubGlobal("window", { localStorage: storageMock });

      expect(getToken()).toBeNull();

      setToken("test-jwt-token-value");
      expect(storageMock.setItem).toHaveBeenCalledWith(
        TOKEN_STORAGE_KEY,
        "test-jwt-token-value"
      );
      expect(getToken()).toBe("test-jwt-token-value");

      clearToken();
      expect(storageMock.removeItem).toHaveBeenCalledWith(TOKEN_STORAGE_KEY);
      expect(getToken()).toBeNull();
    });
  });

  describe("Error Classes & Classification", () => {
    it("constructs ApiClientError with status and detail", () => {
      const err = new ApiClientError(
        "Resource not found",
        404,
        "Ticket CD-9999 does not exist",
        "/api/v1/tickets/CD-9999",
        "GET"
      );

      expect(err.name).toBe("ApiClientError");
      expect(err.status).toBe(404);
      expect(err.detail).toBe("Ticket CD-9999 does not exist");
      expect(err.url).toBe("/api/v1/tickets/CD-9999");
      expect(err.method).toBe("GET");
    });

    it("constructs NetworkError with retry callback", async () => {
      const retryFn = vi.fn().mockResolvedValue({ status: "recovered" });
      const netErr = new NetworkError(
        "Connection refused",
        "http://localhost:8000/api/v1/tickets",
        "GET",
        retryFn
      );

      expect(netErr.name).toBe("NetworkError");
      expect(netErr.isRetryable).toBe(true);
      const res = await netErr.retry();
      expect(res).toEqual({ status: "recovered" });
      expect(retryFn).toHaveBeenCalledTimes(1);
    });

    it("constructs AuthExpiredError with 401 status", () => {
      const authErr = new AuthExpiredError("/api/v1/tickets", "GET");
      expect(authErr.name).toBe("AuthExpiredError");
      expect(authErr.status).toBe(401);
      expect(authErr.message).toContain("expired");
    });
  });

  describe("Domain Namespaces Coverage", () => {
    it("exposes all required API domain methods", () => {
      // Auth
      expect(typeof api.auth.login).toBe("function");
      expect(typeof api.auth.getDemoTokens).toBe("function");
      expect(typeof api.auth.getMe).toBe("function");
      expect(typeof api.auth.refresh).toBe("function");

      // Tickets
      expect(typeof api.tickets.list).toBe("function");
      expect(typeof api.tickets.get).toBe("function");
      expect(typeof api.tickets.create).toBe("function");
      expect(typeof api.tickets.runWorkflow).toBe("function");
      expect(typeof api.tickets.getWorkflowState).toBe("function");
      expect(typeof api.tickets.getEvents).toBe("function");
      expect(typeof api.tickets.reply).toBe("function");
      expect(typeof api.tickets.requestInfo).toBe("function");
      expect(typeof api.tickets.escalate).toBe("function");

      // Customers
      expect(typeof api.customers.list).toBe("function");
      expect(typeof api.customers.get).toBe("function");
      expect(typeof api.customers.addMemory).toBe("function");

      // Knowledge
      expect(typeof api.knowledge.search).toBe("function");
      expect(typeof api.knowledge.reindex).toBe("function");
      expect(typeof api.knowledge.listArticles).toBe("function");
      expect(typeof api.knowledge.getArticle).toBe("function");

      // Approvals
      expect(typeof api.approvals.list).toBe("function");
      expect(typeof api.approvals.approve).toBe("function");
      expect(typeof api.approvals.reject).toBe("function");

      // Escalations
      expect(typeof api.escalations.list).toBe("function");
      expect(typeof api.escalations.get).toBe("function");
      expect(typeof api.escalations.updateStatus).toBe("function");

      // Agents
      expect(typeof api.agents.getTopology).toBe("function");

      // MCP
      expect(typeof api.mcp.getTools).toBe("function");

      // Health
      expect(typeof api.health.checkLive).toBe("function");
      expect(typeof api.health.checkReady).toBe("function");
      expect(typeof api.health.check).toBe("function");
    });
  });

  describe("getApiBaseUrl", () => {
    it("returns default localhost URL when env var is unset", () => {
      delete process.env.NEXT_PUBLIC_API_URL;
      expect(getApiBaseUrl()).toBe("http://localhost:8000");
    });

    it("strips trailing slashes from custom URL", () => {
      process.env.NEXT_PUBLIC_API_URL = "https://api.clouddesk.dev///";
      expect(getApiBaseUrl()).toBe("https://api.clouddesk.dev");
      delete process.env.NEXT_PUBLIC_API_URL;
    });
  });
});

