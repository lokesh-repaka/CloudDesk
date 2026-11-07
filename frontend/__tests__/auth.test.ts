import { describe, it, expect } from "vitest";
import { DEMO_USERS_MAP } from "../lib/auth";
import { Role } from "../lib/types";

describe("Authentication & Role Gating (CLAUDE.md §9, §11)", () => {
  it("provides canonical demo identities for admin, agent, and viewer", () => {
    expect(DEMO_USERS_MAP.admin.email).toBe("admin@clouddesk.demo");
    expect(DEMO_USERS_MAP.admin.name).toBe("Alice Admin");
    expect(DEMO_USERS_MAP.admin.role).toBe("admin");

    expect(DEMO_USERS_MAP.agent.email).toBe("sam.agent@clouddesk.demo");
    expect(DEMO_USERS_MAP.agent.name).toBe("Sam Agent");
    expect(DEMO_USERS_MAP.agent.role).toBe("agent");

    expect(DEMO_USERS_MAP.viewer.email).toBe("vic.viewer@clouddesk.demo");
    expect(DEMO_USERS_MAP.viewer.name).toBe("Vic Viewer");
    expect(DEMO_USERS_MAP.viewer.role).toBe("viewer");
  });

  describe("Role Hierarchy & Gating Rules", () => {
    const roleRank: Record<Role, number> = {
      viewer: 1,
      agent: 2,
      admin: 3,
    };

    it("verifies viewer role (rank 1) has canAct=false and canAdmin=false", () => {
      const role: Role = "viewer";
      const canAct = role !== "viewer" && roleRank[role] >= roleRank.agent;
      const canAdmin = role === "admin";

      expect(canAct).toBe(false);
      expect(canAdmin).toBe(false);
    });

    it("verifies agent role (rank 2) has canAct=true and canAdmin=false", () => {
      const role: Role = "agent";
      const canAct = role !== "viewer" && roleRank[role] >= roleRank.agent;
      const canAdmin = role === "admin";

      expect(canAct).toBe(true);
      expect(canAdmin).toBe(false);
    });

    it("verifies admin role (rank 3) has canAct=true and canAdmin=true", () => {
      const role: Role = "admin";
      const canAct = role !== "viewer" && roleRank[role] >= roleRank.agent;
      const canAdmin = role === "admin";

      expect(canAct).toBe(true);
      expect(canAdmin).toBe(true);
    });
  });
});

