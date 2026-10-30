/**
 * CloudDesk Support Platform — TypeScript API Types
 *
 * Single source of truth mirrored from docs/API_CONTRACT.md and backend/app/schemas/.
 * Maintained in lockstep per CLAUDE.md §12.
 */

// ----------------------------------------------------------------------------
// Canonical Domain Enums
// ----------------------------------------------------------------------------

export type Category =
  | "login_issue"
  | "billing"
  | "api_failure"
  | "workspace_permissions"
  | "storage_quota"
  | "integration"
  | "feature_request"
  | "account"
  | "security"
  | "other";

export type TicketStatus =
  | "new"
  | "in_progress"
  | "waiting_on_customer"
  | "waiting_on_approval"
  | "escalated"
  | "resolved"
  | "closed";

export type Severity = "low" | "medium" | "high" | "critical";

export type Channel = "email" | "chat" | "web" | "api";

export type Role = "viewer" | "agent" | "admin";

export type CustomerPlan = "free" | "pro" | "business" | "enterprise";

export type ApprovalStatus = "pending" | "approved" | "rejected";

export type MemoryType = "preference" | "past_issue" | "troubleshooting" | "note";

export type WorkflowStatus =
  | "queued"
  | "running"
  | "waiting_on_approval"
  | "completed"
  | "escalated"
  | "failed";

// ----------------------------------------------------------------------------
// Standard Error Envelope
// ----------------------------------------------------------------------------

export interface ApiError {
  detail: string | Array<{ loc: string[]; msg: string; type: string }>;
}

// ----------------------------------------------------------------------------
// Ticket Data Types
// ----------------------------------------------------------------------------

export interface TicketCreate {
  customer_id: string;
  subject: string;
  body: string;
  channel?: Channel;
}

export interface TicketMessage {
  id: string;
  ticket_id: string;
  author_role: "customer" | "agent" | "system";
  author_id?: string | null;
  body: string;
  created_at: string;
}

export interface TicketSummary {
  id: string;
  customer_id: string;
  assigned_to?: string | null;
  subject: string;
  status: TicketStatus;
  severity: Severity;
  category: Category;
  channel: Channel;
  resolution_summary?: string | null;
  created_at: string;
  updated_at: string;
  customer_name?: string | null;
  customer_plan?: CustomerPlan | null;
  customer_email?: string | null;
}

export interface TicketDetail extends TicketSummary {
  messages: TicketMessage[];
  active_workflow_id?: string | null;
}

export interface TicketFilterParams {
  status?: TicketStatus;
  severity?: Severity;
  category?: Category;
  plan?: CustomerPlan;
  customer_id?: string;
  assigned_to?: string;
  offset?: number;
  limit?: number;
}

export interface TicketListResponse {
  items: TicketSummary[];
  total: number;
  offset: number;
  limit: number;
}

export interface ReplyCreate {
  message: string;
  internal_note?: string | null;
}

export interface ReplyResponse {
  ticket_id: string;
  message_id: string;
  status: TicketStatus;
}

export interface RequestInfoCreate {
  question: string;
}

export interface EscalateRequest {
  target_team: string;
  policy_reason: string;
  severity?: Severity;
}

export interface EscalateResponse {
  escalation_id: string;
  ticket_id: string;
  target_team: string;
  policy_reason: string;
  severity: Severity;
  status: string;
  created_at: string;
}

// ----------------------------------------------------------------------------
// Workflow & Telemetry Types
// ----------------------------------------------------------------------------

export interface WorkflowRunResponse {
  ticket_id: string;
  workflow_id: string;
  status: WorkflowStatus;
  started_at: string;
}

export interface WorkflowStateResponse {
  ticket_id: string;
  workflow_id: string;
  status: WorkflowStatus;
  current_node?: string | null;
  completed_nodes: string[];
  classification?: Record<string, unknown> | null;
  severity?: Record<string, unknown> | null;
  diagnosis?: Record<string, unknown> | null;
  resolution_plan?: Record<string, unknown> | null;
  escalation?: Record<string, unknown> | null;
  token_usage: {
    prompt_tokens?: number;
    completion_tokens?: number;
    total_tokens?: number;
  };
  error?: string | null;
}

export interface WorkflowEvent {
  id: string;
  workflow_id: string;
  ticket_id: string;
  event_type: string;
  node_name: string;
  data: Record<string, unknown>;
  duration_ms: number;
  tokens_used: number;
  cost_estimate: number;
  created_at: string;
}

// ----------------------------------------------------------------------------
// Customer Context Types
// ----------------------------------------------------------------------------

export interface Subscription {
  id: string;
  customer_id: string;
  plan: string;
  status: string;
  seats: number;
  current_period_end?: string | null;
  created_at: string;
  updated_at: string;
}

export interface Workspace {
  id: string;
  customer_id: string;
  name: string;
  slug: string;
  storage_used_bytes: number;
  storage_limit_bytes: number;
  created_at: string;
  updated_at: string;
}

export interface CustomerMemory {
  id: string;
  customer_id: string;
  memory_type: MemoryType;
  content: string;
  created_at: string;
  updated_at: string;
}

export interface CustomerMemoryCreate {
  memory_type?: MemoryType;
  content: string;
}

export interface CustomerSummary {
  id: string;
  name: string;
  email: string;
  plan: CustomerPlan;
  created_at: string;
  updated_at: string;
}

export interface CustomerListResponse {
  items: CustomerSummary[];
  total: number;
  offset: number;
  limit: number;
}

export interface CustomerDetail extends CustomerSummary {
  active_subscription?: Subscription | null;
  subscriptions: Subscription[];
  workspaces: Workspace[];
  recent_tickets: TicketSummary[];
  memory_notes: CustomerMemory[];
}

// ----------------------------------------------------------------------------
// Knowledge Base Types (P5-4 / API_CONTRACT.md §5.2)
// ----------------------------------------------------------------------------

export interface KnowledgeSearchRequest {
  query: string;
  category?: Category | null;
  top_k?: number;
  mode?: "hybrid" | "semantic" | "keyword";
}

export interface KnowledgeEvidence {
  id: string;
  title: string;
  source: string;
  snippet: string;
  score: number;
  url: string;
  article_id: string;
}

export interface KnowledgeReindexResponse {
  indexed_articles: number;
  total_chunks: number;
}

export interface KnowledgeArticleSummary {
  id: string;
  slug: string;
  title: string;
  category: string;
  tags: string[];
  summary: string;
  url: string;
}

export interface KnowledgeArticleDetail extends KnowledgeArticleSummary {
  content: string;
  file_path?: string | null;
}

