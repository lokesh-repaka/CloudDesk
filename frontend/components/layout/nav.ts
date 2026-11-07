/**
 * CloudDesk Support Platform — Navigation Specification (CLAUDE.md §11)
 *
 * Single source of truth for console shell routes, hierarchy, icons,
 * role restrictions, and keyboard shortcut associations.
 */

import { Role } from "@/lib/types";

export interface NavItem {
  id: string;
  label: string;
  href: string;
  icon: string;
  description: string;
  minRole: Role;
  shortcut?: string;
  badgeKey?: "openTickets" | "pendingApprovals" | "escalations";
}

export interface NavSection {
  title: string;
  items: NavItem[];
}

export const MAIN_NAV_ITEMS: NavItem[] = [
  {
    id: "dashboard",
    label: "Dashboard",
    href: "/dashboard",
    icon: "layout-dashboard",
    description: "Support operational overview and system telemetry metrics",
    minRole: "viewer",
  },
  {
    id: "tickets",
    label: "Tickets",
    href: "/tickets",
    icon: "ticket",
    description: "Customer support cases, triaged queues, and active workflows",
    minRole: "viewer",
    shortcut: "t",
    badgeKey: "openTickets",
  },
  {
    id: "customers",
    label: "Customers",
    href: "/customers",
    icon: "users",
    description: "Customer profiles, subscriptions, tier limits, and memory notes",
    minRole: "viewer",
    shortcut: "c",
  },
  {
    id: "knowledge",
    label: "Knowledge Base",
    href: "/knowledge",
    icon: "book-open",
    description: "Documentation articles, chunked sections, and RAG search",
    minRole: "viewer",
    shortcut: "k",
  },
  {
    id: "escalations",
    label: "Escalations",
    href: "/escalations",
    icon: "alert-triangle",
    description: "Deterministic policy escalation queues routed to specialist teams",
    minRole: "agent",
    shortcut: "e",
    badgeKey: "escalations",
  },
  {
    id: "agents",
    label: "Agents & Topology",
    href: "/agents",
    icon: "bot",
    description: "Specialist agent profiles, tools, rules, and LangGraph topology",
    minRole: "viewer",
  },
  {
    id: "audit",
    label: "Audit Logs",
    href: "/audit",
    icon: "shield",
    description: "Access logs, policy gating triggers, and compliance audit trail",
    minRole: "viewer",
  },
  {
    id: "settings",
    label: "Settings",
    href: "/settings",
    icon: "settings",
    description: "System configuration, model settings, and knowledge reindex",
    minRole: "admin",
  },
];

export const NAV_SECTIONS: NavSection[] = [
  {
    title: "Operations",
    items: MAIN_NAV_ITEMS.filter((i) =>
      ["dashboard", "tickets", "customers", "knowledge"].includes(i.id)
    ),
  },
  {
    title: "Governance & Intelligence",
    items: MAIN_NAV_ITEMS.filter((i) =>
      ["escalations", "agents", "audit", "settings"].includes(i.id)
    ),
  },
];

/**
 * Filter navigation items accessible to the active user role.
 */
export function getAuthorizedNavItems(userRole: Role): NavItem[] {
  const roleRank: Record<Role, number> = {
    viewer: 1,
    agent: 2,
    admin: 3,
  };

  const currentRank = roleRank[userRole] ?? 1;
  return MAIN_NAV_ITEMS.filter((item) => roleRank[item.minRole] <= currentRank);
}

