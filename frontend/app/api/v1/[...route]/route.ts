import { NextRequest, NextResponse } from "next/server";
import ticketsData from "@/data/sample_data/tickets.json";
import customersData from "@/data/sample_data/customers.json";
import subscriptionsData from "@/data/sample_data/subscriptions.json";
import workspacesData from "@/data/sample_data/workspaces.json";
import productsData from "@/data/sample_data/products.json";

interface ApprovalItem {
  id: string;
  ticket_id: string;
  workflow_id: string;
  action_type: string;
  parameters: Record<string, unknown>;
  status: string;
  created_at: string;
  decided_at: string | null;
  decided_by: string | null;
}

// In-memory demo state for live mutations (e.g. approving CD-1002 refund)
let approvalsState: ApprovalItem[] = [
  {
    id: "appr-1002",
    ticket_id: "CD-1002",
    workflow_id: "wf-1002-stateful",
    action_type: "refund",
    parameters: {
      amount: 90.0,
      currency: "USD",
      seats_refunded: 3,
      reason: "Downgraded from 8 to 5 seats. Invoiced for 8 seats ($240 vs $150).",
    },
    status: "pending",
    created_at: new Date(Date.now() - 3600000).toISOString(),
    decided_at: null,
    decided_by: null,
  },
];

let escalationsState = [
  {
    id: "esc-1005",
    ticket_id: "CD-1005",
    target_team: "Security Operations (SOC)",
    policy_reason: "Multiple anomalous login attempts from foreign IP addresses attempting brute-force attack",
    severity: "critical",
    status: "open",
    created_at: new Date(Date.now() - 7200000).toISOString(),
  },
  {
    id: "esc-1013",
    ticket_id: "CD-1013",
    target_team: "Platform Security",
    policy_reason: "Prompt injection attack detected: customer attempted to dump customer credentials and JWT keys",
    severity: "high",
    status: "open",
    created_at: new Date(Date.now() - 1800000).toISOString(),
  },
];

const DEMO_USERS_LOOKUP: Record<string, { id: string; email: string; full_name: string; role: string }> = {
  "admin@clouddesk.demo": {
    id: "usr-admin-001",
    email: "admin@clouddesk.demo",
    full_name: "Alice Admin",
    role: "admin",
  },
  "sam.agent@clouddesk.demo": {
    id: "usr-agent-002",
    email: "sam.agent@clouddesk.demo",
    full_name: "Sam Agent",
    role: "agent",
  },
  "vic.viewer@clouddesk.demo": {
    id: "usr-viewer-003",
    email: "vic.viewer@clouddesk.demo",
    full_name: "Vic Viewer",
    role: "viewer",
  },
};

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ route: string[] }> }
) {
  const { route } = await params;
  const path = route.join("/");

  // 1. Auth: demo-tokens
  if (path === "auth/demo-tokens") {
    return NextResponse.json({
      admin: { ...DEMO_USERS_LOOKUP["admin@clouddesk.demo"], token: "demo-jwt-admin-token" },
      agent: { ...DEMO_USERS_LOOKUP["sam.agent@clouddesk.demo"], token: "demo-jwt-agent-token" },
      viewer: { ...DEMO_USERS_LOOKUP["vic.viewer@clouddesk.demo"], token: "demo-jwt-viewer-token" },
    });
  }

  // 2. Auth: me
  if (path === "auth/me") {
    return NextResponse.json(DEMO_USERS_LOOKUP["admin@clouddesk.demo"]);
  }

  // 3. Tickets: list
  if (path === "tickets") {
    const enrichedTickets = (ticketsData as Array<Record<string, unknown>>).map((t) => {
      const cust = (customersData as Array<Record<string, unknown>>).find((c) => c.id === t.customer_id);
      return {
        ...t,
        customer_name: cust?.name || "Enterprise Customer",
        customer_plan: cust?.plan || "pro",
        customer_email: cust?.email || "customer@example.com",
        created_at: new Date(Date.now() - 3600000 * 4).toISOString(),
        updated_at: new Date().toISOString(),
      };
    });
    return NextResponse.json({
      items: enrichedTickets,
      total: enrichedTickets.length,
      offset: 0,
      limit: 50,
    });
  }

  // 4. Tickets: single ticket detail
  if (path.startsWith("tickets/") && route.length === 2) {
    const ticketId = route[1];
    const ticket = (ticketsData as Array<Record<string, unknown>>).find((t) => t.id === ticketId);
    if (!ticket) {
      return NextResponse.json({ detail: "Ticket not found" }, { status: 404 });
    }
    const cust = (customersData as Array<Record<string, unknown>>).find((c) => c.id === ticket.customer_id);
    return NextResponse.json({
      ...ticket,
      customer_name: cust?.name || "Enterprise Customer",
      customer_plan: cust?.plan || "pro",
      customer_email: cust?.email || "customer@example.com",
      created_at: new Date(Date.now() - 3600000 * 4).toISOString(),
      updated_at: new Date().toISOString(),
      messages: [
        {
          id: `msg-${ticketId}-1`,
          ticket_id: ticketId,
          author_role: "customer",
          author_id: ticket.customer_id,
          body: ticket.initial_message,
          created_at: new Date(Date.now() - 3600000 * 4).toISOString(),
        },
      ],
      active_workflow_id: `wf-${ticketId}`,
    });
  }

  // 5. Tickets: workflow status
  if (path.startsWith("tickets/") && route.length === 3 && route[2] === "workflow") {
    const ticketId = route[1];
    const isPendingRefund = ticketId === "CD-1002";
    return NextResponse.json({
      ticket_id: ticketId,
      workflow_id: `wf-${ticketId}`,
      status: isPendingRefund ? "waiting_on_approval" : "completed",
      current_node: isPendingRefund ? "human_approval" : "memory_update",
      completed_nodes: [
        "understand_ticket",
        "classify_severity",
        "customer_context",
        "knowledge_retrieval",
        "troubleshooting",
        "resolution_planning",
        ...(isPendingRefund ? [] : ["execute_resolution", "memory_update"]),
      ],
      classification: { category: "billing", confidence: 0.96 },
      severity: { severity: "medium", reason: "Billing discrepancy request" },
      diagnosis: { probable_cause: "Proration update lagged behind subscription downgrade" },
      resolution_plan: {
        summary: "Refund 3 seats ($90.00) and adjust next billing cycle.",
        action_type: "refund",
        amount: 90.0,
      },
      token_usage: { prompt_tokens: 1420, completion_tokens: 380, total_tokens: 1800 },
    });
  }

  // 6. Tickets: events
  if (path.startsWith("tickets/") && route.length === 3 && route[2] === "events") {
    const ticketId = route[1];
    return NextResponse.json([
      {
        id: `ev-1`,
        workflow_id: `wf-${ticketId}`,
        ticket_id: ticketId,
        event_type: "node_completed",
        node_name: "understand_ticket",
        data: { summary: "Customer reported billing seat mismatch" },
        duration_ms: 120,
        tokens_used: 240,
        cost_estimate: 0.001,
        created_at: new Date(Date.now() - 120000).toISOString(),
      },
      {
        id: `ev-2`,
        workflow_id: `wf-${ticketId}`,
        ticket_id: ticketId,
        event_type: "node_completed",
        node_name: "knowledge_retrieval",
        data: { articles_found: 2, top_relevance: 0.94 },
        duration_ms: 140,
        tokens_used: 510,
        cost_estimate: 0.002,
        created_at: new Date(Date.now() - 90000).toISOString(),
      },
      {
        id: `ev-3`,
        workflow_id: `wf-${ticketId}`,
        ticket_id: ticketId,
        event_type: "approval_requested",
        node_name: "human_approval",
        data: { action: "refund", amount: 90.0 },
        duration_ms: 50,
        tokens_used: 120,
        cost_estimate: 0.0005,
        created_at: new Date(Date.now() - 30000).toISOString(),
      },
    ]);
  }

  // 7. Approvals: list
  if (path === "approvals") {
    return NextResponse.json(approvalsState);
  }

  // 8. Escalations: list
  if (path === "escalations") {
    return NextResponse.json(escalationsState);
  }

  // 9. Customers: list
  if (path === "customers") {
    return NextResponse.json({
      items: customersData,
      total: (customersData as unknown[]).length,
      offset: 0,
      limit: 50,
    });
  }

  // 10. Customers: detail
  if (path.startsWith("customers/") && route.length === 2) {
    const custId = route[1];
    const customer = (customersData as Array<Record<string, unknown>>).find((c) => c.id === custId);
    const sub = (subscriptionsData as Array<Record<string, unknown>>).find((s) => s.customer_id === custId);
    const workspaces = (workspacesData as Array<Record<string, unknown>>).filter((w) => w.customer_id === custId);
    return NextResponse.json({
      ...(customer || { id: custId, name: "Customer", email: "cust@example.com", plan: "pro" }),
      subscriptions: sub ? [sub] : [],
      workspaces: workspaces,
      tickets: (ticketsData as Array<Record<string, unknown>>).filter((t) => t.customer_id === custId),
      memory_notes: [
        {
          id: `mem-${custId}`,
          customer_id: custId,
          content: "Enterprise customer prefers email confirmation for all quota and billing modifications.",
          created_at: new Date(Date.now() - 86400000 * 2).toISOString(),
        },
      ],
    });
  }

  // 11. Knowledge: articles
  if (path === "knowledge/articles") {
    return NextResponse.json([
      {
        id: "kb-billing-01",
        slug: "seats-refund",
        title: "Seat Management and Prorated Refund Policy",
        category: "billing",
        tags: ["billing", "refund", "seats", "proration", "invoices"],
        summary: "Policy guidelines for license seat count adjustments and prorated credit refund processing.",
        url: "/knowledge/seats-refund",
      },
      {
        id: "kb-login-01",
        slug: "sso-okta",
        title: "Troubleshooting SAML 2.0 Single Sign-On (SSO) Failures",
        category: "login_issue",
        tags: ["sso", "saml", "okta", "azure", "authentication"],
        summary: "Guide to diagnosing and resolving SAML assertion signature errors and IdP configuration issues.",
        url: "/knowledge/sso-okta",
      },
      {
        id: "kb-sec-01",
        slug: "compromised-accounts",
        title: "Incident Response Protocol for Compromised Accounts and Breaches",
        category: "security",
        tags: ["security", "breach", "compromise", "escalation", "incident-response"],
        summary: "High-priority response procedure for reported account takeover or anomalous access.",
        url: "/knowledge/compromised-accounts",
      },
      {
        id: "kb-api-01",
        slug: "api-rate-limits",
        title: "API Rate Limits, HTTP 429 Errors, and Backoff Guidelines",
        category: "api_failure",
        tags: ["api", "rate-limit", "429", "backoff", "throttling"],
        summary: "Understanding CloudDesk REST API rate limits and implementing exponential backoff.",
        url: "/knowledge/api-rate-limits",
      },
      {
        id: "kb-acc-01",
        slug: "deletion-gdpr",
        title: "Account Erasure, Workspace Deletion, and GDPR Compliance",
        category: "account",
        tags: ["account", "gdpr", "deletion", "compliance", "privacy"],
        summary: "Protocol for processing permanent data erasure and GDPR Article 17 right to be forgotten requests.",
        url: "/knowledge/deletion-gdpr",
      },
      {
        id: "kb-integ-01",
        slug: "slack-notifications",
        title: "Connecting Slack Notifications and Webhook Troubleshooting",
        category: "integration",
        tags: ["integration", "slack", "webhooks", "alerts", "bot"],
        summary: "Setup guide and troubleshooting steps for the CloudDesk Slack notification bot.",
        url: "/knowledge/slack-notifications",
      },
      {
        id: "kb-quota-01",
        slug: "storage-tiers",
        title: "Workspace Storage Quotas and Storage Tier Specifications",
        category: "storage_quota",
        tags: ["storage", "quota", "tiers", "limits", "upgrade"],
        summary: "Overview of workspace storage quota allowances and tier upgrade processes.",
        url: "/knowledge/storage-tiers",
      },
      {
        id: "kb-sec-02",
        slug: "audit-access",
        title: "Security Telemetry, Audit Trails, and Prompt Injection Defense",
        category: "security",
        tags: ["security", "audit", "injection", "guardrails", "compliance"],
        summary: "System design for immutable audit logging and prompt injection containment.",
        url: "/knowledge/audit-access",
      },
    ]);
  }

  // 12. Agents topology
  if (path === "agents") {
    return NextResponse.json({
      agents: [
        { id: "supervisor", name: "Supervisor Agent", role: "Triage & Injection Quarantine", status: "active" },
        { id: "customer", name: "Customer Agent", role: "360° Context Assembly", status: "active" },
        { id: "knowledge", name: "Knowledge Agent", role: "Hybrid Vector + BM25 RAG", status: "active" },
        { id: "troubleshooting", name: "Troubleshooting Agent", role: "System Outage Diagnostics", status: "active" },
        { id: "resolution", name: "Resolution Agent", role: "Drafting & Action Staging", status: "active" },
        { id: "escalation", name: "Escalation Agent", role: "Deterministic SLA Policy Routing", status: "active" },
      ],
    });
  }

  // 13. MCP Tools
  if (path === "mcp/tools") {
    return NextResponse.json({
      tools: [
        { name: "get_customer_dossier", description: "Retrieve customer subscriptions, limits, and tickets" },
        { name: "search_docs", description: "Hybrid vector and token search across verified knowledge base" },
        { name: "check_service_status", description: "Query live infrastructure health and outage metrics" },
      ],
    });
  }

  // 14. Fallback 404
  return NextResponse.json({ detail: `Route /api/v1/${path} not found` }, { status: 404 });
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ route: string[] }> }
) {
  const { route } = await params;
  const path = route.join("/");

  // 1. Auth: login
  if (path === "auth/login") {
    let email = "admin@clouddesk.demo";
    try {
      const body = await request.json();
      if (body?.email) email = body.email.toLowerCase().trim();
    } catch {
      // Use default admin
    }
    const user = DEMO_USERS_LOOKUP[email] || {
      id: "usr-custom-001",
      email,
      full_name: email.split("@")[0],
      role: "agent",
    };
    return NextResponse.json({
      access_token: `demo-jwt-${user.role}-token`,
      token_type: "bearer",
      user,
    });
  }

  // 2. Approvals: approve
  if (path.startsWith("approvals/") && route[2] === "approve") {
    const approvalId = route[1];
    approvalsState = approvalsState.map((a) =>
      a.id === approvalId ? { ...a, status: "approved", decided_at: new Date().toISOString() } : a
    );
    return NextResponse.json({ id: approvalId, status: "approved" });
  }

  // 3. Approvals: reject
  if (path.startsWith("approvals/") && route[2] === "reject") {
    const approvalId = route[1];
    approvalsState = approvalsState.map((a) =>
      a.id === approvalId ? { ...a, status: "rejected", decided_at: new Date().toISOString() } : a
    );
    return NextResponse.json({ id: approvalId, status: "rejected" });
  }

  // 4. Knowledge: search
  if (path === "knowledge/search") {
    let query = "";
    try {
      const body = await request.json();
      query = body?.query || "";
    } catch {
      // Empty query
    }
    return NextResponse.json({
      query,
      evidence: [
        {
          id: "ev-1",
          article_id: "kb-login-01",
          title: "Configuring Okta SAML Single Sign-On",
          source: "sso-okta",
          snippet: "To configure Okta SAML SSO, export the x509 signing certificate from your Okta application administrator dashboard and verify the SAML Response signature under Workspace Security settings.",
          score: 0.94,
          url: "/knowledge/sso-okta",
        },
        {
          id: "ev-2",
          article_id: "kb-billing-01",
          title: "Seat Adjustments and Refund Policy",
          source: "seats-refund",
          snippet: "Seats removed mid-billing cycle generate a prorated credit balance. Unused seat charges can be refunded within 30 days of the invoice date upon approval.",
          score: 0.88,
          url: "/knowledge/seats-refund",
        },
      ],
    });
  }

  // 5. Tickets: run workflow
  if (path.startsWith("tickets/") && route[2] === "run") {
    const ticketId = route[1];
    return NextResponse.json(
      {
        ticket_id: ticketId,
        workflow_id: `wf-${ticketId}`,
        status: ticketId === "CD-1002" ? "waiting_on_approval" : "running",
        started_at: new Date().toISOString(),
      },
      { status: 202 }
    );
  }

  // 6. Tickets: reply
  if (path.startsWith("tickets/") && route[2] === "reply") {
    const ticketId = route[1];
    return NextResponse.json({
      ticket_id: ticketId,
      message_id: `msg-${Date.now()}`,
      status: "resolved",
    });
  }

  // 7. Tickets: create
  if (path === "tickets") {
    const body = await request.json().catch(() => ({}));
    const newId = `CD-${1000 + Math.floor(Math.random() * 9000)}`;
    return NextResponse.json({
      id: newId,
      customer_id: body.customer_id || "cust-101-acme",
      subject: body.subject || "Customer Inquiry",
      status: "new",
      severity: "medium",
      category: "other",
      channel: body.channel || "web",
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });
  }

  return NextResponse.json({ detail: "Success" });
}
