import { describe, it, expect } from "vitest";
import { MAIN_NAV_ITEMS, NAV_SECTIONS, getAuthorizedNavItems } from "../components/layout/nav";
import { Role } from "../lib/types";

describe("Navigation Specification (CLAUDE.md §11)", () => {
  it("declares all required console shell routes", () => {
    const routeHrefs = MAIN_NAV_ITEMS.map((item) => item.href);
    const expected = [
      "/dashboard",
      "/tickets",
      "/customers",
      "/knowledge",
      "/escalations",
      "/agents",
      "/audit",
      "/settings",
    ];

    for (const route of expected) {
      expect(routeHrefs).toContain(route);
    }
  });

  it("every nav item has valid id, label, icon, and description", () => {
    for (const item of MAIN_NAV_ITEMS) {
      expect(item.id).toBeTruthy();
      expect(item.label).toBeTruthy();
      expect(item.icon).toBeTruthy();
      expect(item.description).toBeTruthy();
      expect(["viewer", "agent", "admin"]).toContain(item.minRole);
    }
  });

  describe("getAuthorizedNavItems role gating", () => {
    it("viewer role receives only viewer-accessible items", () => {
      const items = getAuthorizedNavItems("viewer");
      const ids = items.map((i) => i.id);

      expect(ids).toContain("dashboard");
      expect(ids).toContain("tickets");
      expect(ids).toContain("customers");
      expect(ids).toContain("knowledge");
      expect(ids).toContain("agents");
      expect(ids).toContain("audit");

      // Agent-only or Admin-only routes must be excluded
      expect(ids).not.toContain("escalations");
      expect(ids).not.toContain("settings");
      expect(items.length).toBe(6);
    });

    it("agent role receives viewer and agent items but not admin items", () => {
      const items = getAuthorizedNavItems("agent");
      const ids = items.map((i) => i.id);

      expect(ids).toContain("dashboard");
      expect(ids).toContain("tickets");
      expect(ids).toContain("escalations"); // agent-level
      expect(ids).not.toContain("settings"); // admin-only
      expect(items.length).toBe(7);
    });

    it("admin role receives all navigation items", () => {
      const items = getAuthorizedNavItems("admin");
      expect(items.length).toBe(MAIN_NAV_ITEMS.length);
      const ids = items.map((i) => i.id);
      expect(ids).toContain("settings");
      expect(ids).toContain("escalations");
      expect(ids).toContain("dashboard");
    });
  });

  describe("NAV_SECTIONS structure", () => {
    it("groups items into Operations and Governance & Intelligence", () => {
      expect(NAV_SECTIONS.length).toBe(2);
      expect(NAV_SECTIONS[0].title).toBe("Operations");
      expect(NAV_SECTIONS[1].title).toBe("Governance & Intelligence");

      const operationsIds = NAV_SECTIONS[0].items.map((i) => i.id);
      expect(operationsIds).toEqual(["dashboard", "tickets", "customers", "knowledge"]);

      const governanceIds = NAV_SECTIONS[1].items.map((i) => i.id);
      expect(governanceIds).toEqual(["escalations", "agents", "audit", "settings"]);
    });
  });
});

