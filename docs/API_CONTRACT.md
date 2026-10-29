# CloudDesk Support Platform — API Contract Specification

> **Document Version:** 1.0.0  
> **Status:** Canonical Source of Truth  
> **Specification Governance:** As defined in [CLAUDE.md](CLAUDE.md) §12, `docs/API_CONTRACT.md` is the authoritative source of truth for every HTTP endpoint, request/response schema, and error behavior across the CloudDesk platform.  
> **Rule:** If an endpoint or data structure changes, `docs/API_CONTRACT.md`, `backend/app/schemas/`, and `frontend/lib/types.ts` must be updated in the same change.

---

## 1. Global Architectural Conventions

### 1.1 Base URL & Mounting
- All service endpoints are mounted under `/api/v1`, with the exception of root health probes (`/health`, `/health/live`, `/health/ready`).
- Base URL (Local Development): `http://localhost:8000`

### 1.2 Mandatory Request & Response Headers

| Header | Type | Direction | Description |
|---|---|:---:|---|
| `Authorization` | `string` | Client → Server | `Bearer <JWT_TOKEN>` for all non-public routes. HS256 Supabase-compatible JWT. |
| `Content-Type` | `string` | Bidirectional | Must be `application/json` for requests with bodies and JSON responses. |
| `X-Request-ID` | `string` | Bidirectional | Safe UUID/token (`^[a-zA-Z0-9_-]{1,128}$`) echoed from client or assigned by `RequestIdMiddleware`. Present on all responses including 4xx and 5xx. |

### 1.3 Role-Based Access Control (RBAC) Hierarchy
Enforced by `require_role(min_role)` in `backend/app/core/security.py`:
- `viewer` (Level 1): Read-only access to tickets, customer context, knowledge base, and audit logs.
- `agent` (Level 2): Full viewer permissions plus workflow execution (`/run`), customer replies, clarification requests, manual escalations, and approval decisions (`approve`/`reject`).
- `admin` (Level 3): Full agent permissions plus knowledge base re-indexing, administrative resets, and tenant settings modification.

### 1.4 Standard RFC 7807 Error Envelope
All error responses return a uniform JSON envelope:
```json
{
  "detail": "Descriptive error message explaining the failure condition."
}
```

Validation errors (`HTTP 422 Unprocessable Entity`) include field-level descriptors:
```json
{
  "detail": [
    {
      "loc": ["body", "subject"],
      "msg": "Subject must contain at least 3 non-whitespace characters",
      "type": "value_error"
    }
  ]
}
```

### 1.5 Standard HTTP Status Codes

| Code | Status | Usage |
|:---:|---|---|
| `200` | OK | Successful retrieval or synchronous state update. |
| `201` | Created | Resource successfully created (e.g., ticket ingestion, memory note). |
| `202` | Accepted | Asynchronous workflow initiated (`/tickets/{id}/run`). |
| `400` | Bad Request | Semantic business logic failure or invalid payload format. |
| `401` | Unauthorized | Missing, expired, or cryptographically invalid JWT token. |
| `403` | Forbidden | Insufficient RBAC role privilege or production demo-token access denial. |
| `404` | Not Found | Requested entity (ticket, customer, approval) does not exist. |
| `409` | Conflict | Illegal state transition (e.g., re-running a ticket waiting on approval). |
| `422` | Unprocessable Entity | Pydantic validation failure (invalid enum, out-of-bounds length). |
| `429` | Too Many Requests | Rate limit ceiling exceeded (fixed window in Redis, 120 req/min demo). |
| `503` | Service Unavailable | Health readiness probe failure (`/health/ready`). |

---

## 2. API Endpoint Groups Overview

```text
/health               Health and readiness probes (Public)
/api/v1/auth          Authentication & demo token generation (Public / Guarded)
/api/v1/dashboard     Dashboard overview and executive queue summaries (Viewer)
/api/v1/tickets       Omnichannel intake, queue listing, workflow execution, replies, escalations
/api/v1/approvals     Human-in-the-loop approval gate and decision resume (Agent)
/api/v1/customers     360-degree customer dossier, subscriptions, workspaces, memory notes
/api/v1/knowledge     Hybrid RAG article search and re-indexing (Viewer / Admin)
/api/v1/escalations   Dedicated escalation queue and status tracking (Viewer / Agent)
/api/v1/agents        LangGraph agent architecture and topology discovery (Viewer)
/api/v1/audit         Immutable audit trail queries (Viewer)
/api/v1/settings      Platform configuration inspection and updates (Admin)
/api/v1/mcp/tools     Model Context Protocol read-only tool discovery (Agent)
```

---

## 3. Detailed Specification: Support Tickets API (`/api/v1/tickets`)

### 3.1 Create Ticket (Omnichannel Ingestion)
- **Route:** `POST /api/v1/tickets`
- **Minimum Role:** `Public` (Intake from webhooks, email parsers, customer forms)
- **Traceability:** `F1`, `US-001`, `AC-001`, `AC-002`, `AC-003`, `AC-004`, `AC-005`
- **Description:** Ingests a new customer support ticket across email, chat, web, or API. Atomically persists the ticket parent record and the initial customer conversation message.

#### Request Body (`TicketCreate`):
```json
{
  "customer_id": "cust-101-acme",
  "subject": "SSO login fails for whole team",
  "body": "None of our 50 enterprise users can authenticate via Okta SSO this morning.",
  "channel": "email"
}
```

| Field | Type | Required | Description / Constraints |
|---|---|:---:|---|
| `customer_id` | `string` | Yes | Customer UUID or identifier (1–100 chars). Must exist in DB. |
| `subject` | `string` | Yes | Subject line (3–255 chars). Cannot be whitespace-only. |
| `body` | `string` | Yes | Initial message content (1–50,000 chars). |
| `channel` | `string` | No | Ingestion channel: `"email"`, `"chat"`, `"web"`, `"api"`. Default: `"email"`. |

#### Response (`201 Created` - `TicketDetailResponse`):
```json
{
  "id": "c7a8b890-3b8e-4a69-a1b4-2b7e1c8d9e01",
  "customer_id": "cust-101-acme",
  "assigned_to": null,
  "subject": "SSO login fails for whole team",
  "status": "new",
  "severity": "medium",
  "category": "other",
  "channel": "email",
  "resolution_summary": null,
  "created_at": "2026-10-29T10:00:00Z",
  "updated_at": "2026-10-29T10:00:00Z",
  "customer_name": "Acme Corporation",
  "customer_plan": "enterprise",
  "customer_email": "support@acme.test",
  "messages": [
    {
      "id": "m1a2b3c4-0000-4000-8000-000000000001",
      "ticket_id": "c7a8b890-3b8e-4a69-a1b4-2b7e1c8d9e01",
      "author_role": "customer",
      "author_id": "cust-101-acme",
      "body": "None of our 50 enterprise users can authenticate via Okta SSO this morning.",
      "created_at": "2026-10-29T10:00:00Z"
    }
  ],
  "active_workflow_id": null
}
```

#### Error Responses:
- `404 Not Found`: Customer does not exist (`{"detail": "Customer cust-999 not found"}`).
- `422 Unprocessable Entity`: Invalid channel, empty subject, or body length > 50,000.

---

### 3.2 List Tickets (Queue & Filtering)
- **Route:** `GET /api/v1/tickets`
- **Minimum Role:** `viewer`
- **Traceability:** `F1`, `F12`, `US-002`, `AC-007`, `AC-008`, `AC-009`, `AC-010`, `AC-011`
- **Description:** Returns paginated list of support tickets filtered by status, severity, category, or customer plan.

#### Query Parameters (`TicketFilterParams`):
| Parameter | Type | Default | Description / Constraints |
|---|---|:---:|---|
| `status` | `string` | `null` | Filter: `new`, `in_progress`, `waiting_on_customer`, `waiting_on_approval`, `escalated`, `resolved`, `closed`. |
| `severity` | `string` | `null` | Filter: `low`, `medium`, `high`, `critical`. |
| `category` | `string` | `null` | Filter: one of the 10 canonical categories. |
| `plan` | `string` | `null` | Filter: `free`, `pro`, `business`, `enterprise`. |
| `customer_id` | `string` | `null` | Filter by specific customer UUID. |
| `assigned_to` | `string` | `null` | Filter by assigned agent profile UUID. |
| `offset` | `integer`| `0` | Pagination offset (ge=0). |
| `limit` | `integer`| `50` | Pagination limit (1–100). |

#### Response (`200 OK` - `TicketListResponse`):
```json
{
  "items": [
    {
      "id": "CD-1001",
      "customer_id": "cust-101-acme",
      "assigned_to": null,
      "subject": "SSO login fails for whole team",
      "status": "new",
      "severity": "critical",
      "category": "login_issue",
      "channel": "web",
      "resolution_summary": null,
      "created_at": "2026-10-29T08:00:00Z",
      "updated_at": "2026-10-29T08:00:00Z",
      "customer_name": "Acme Corporation",
      "customer_plan": "enterprise",
      "customer_email": "support@acme.test"
    }
  ],
  "total": 1,
  "offset": 0,
  "limit": 50
}
```

---

### 3.3 Get Ticket Details
- **Route:** `GET /api/v1/tickets/{id}`
- **Minimum Role:** `viewer`
- **Traceability:** `F12`, `US-015`, `AC-060`
- **Description:** Retrieves complete ticket dossier including customer metadata, full conversation message history, and latest workflow status.

#### Response (`200 OK` - `TicketDetailResponse`):
Returns the complete `TicketDetailResponse` structure with message history and active workflow execution pointer.

#### Error Responses:
- `404 Not Found`: Ticket with specified ID does not exist.

---

### 3.4 Run AI Workflow
- **Route:** `POST /api/v1/tickets/{id}/run`
- **Minimum Role:** `agent`
- **Traceability:** `F2`–`F11`, `US-003`–`US-012`, `AC-012`–`AC-050`
- **Description:** Triggers autonomous LangGraph investigation in the background. Transitions ticket to `in_progress`.

#### Response (`202 Accepted` - `WorkflowRunResponse`):
```json
{
  "ticket_id": "CD-1001",
  "workflow_id": "wf-b4391447-7372-419a-be66-ac7b3bac0451",
  "status": "running",
  "started_at": "2026-10-29T10:05:00Z"
}
```

#### Error Responses:
- `403 Forbidden`: User has `viewer` role (`{"detail": "Operation requires agent role"}`).
- `404 Not Found`: Ticket does not exist.
- `409 Conflict`: Ticket is currently in `waiting_on_approval` status or active run already processing.

---

### 3.5 Poll Workflow State
- **Route:** `GET /api/v1/tickets/{id}/workflow`
- **Minimum Role:** `viewer`
- **Traceability:** `F12`, `US-015`, `AC-060`, `AC-061`
- **Description:** Polled by frontend every 2 seconds to render live graph execution progress, completed node chips, diagnostic reasoning, and proposed resolution plan.

#### Response (`200 OK` - `WorkflowStateResponse`):
```json
{
  "ticket_id": "CD-1002",
  "workflow_id": "wf-b4391447-7372-419a-be66-ac7b3bac0451",
  "status": "waiting_on_approval",
  "current_node": "human_approval",
  "completed_nodes": [
    "understand_ticket",
    "classify_severity",
    "customer_context",
    "knowledge_retrieval",
    "troubleshooting",
    "resolution_planning",
    "risk_check"
  ],
  "classification": {
    "category": "billing",
    "confidence": 0.98,
    "summary": "Customer charged for 8 seats after downgrading to 5 seats."
  },
  "severity": {
    "severity": "medium",
    "reason": "Billing adjustment under standard financial risk limit."
  },
  "diagnosis": {
    "probable_causes": ["Subscription seat count cached during previous invoice cycle."],
    "troubleshooting_steps": ["1. Verify workspace seats.", "2. Calculate pro-rata difference."]
  },
  "resolution_plan": {
    "summary": "Issue $90 refund for 3 unused seats.",
    "customer_reply": "We have credited $90 to your account for the unused seats.",
    "action": "create_refund_request",
    "action_payload": { "amount": 90.0, "currency": "USD" },
    "requires_approval": true
  },
  "escalation": null,
  "token_usage": {
    "prompt_tokens": 2150,
    "completion_tokens": 420,
    "total_tokens": 2570
  },
  "error": null
}
```

---

### 3.6 Inspect Workflow Telemetry Events
- **Route:** `GET /api/v1/tickets/{id}/events`
- **Minimum Role:** `viewer`
- **Traceability:** `F13`, `US-016`, `AC-064`, `AC-065`, `AC-066`, `AC-067`
- **Description:** Chronological audit trail of all graph node executions, tool invocations, and LLM calls, including elapsed time in milliseconds, token counts, and cost estimates.

#### Response (`200 OK` - `list[WorkflowEventResponse]`):
```json
[
  {
    "id": "evt-001",
    "workflow_id": "wf-b4391447-7372-419a-be66-ac7b3bac0451",
    "ticket_id": "CD-1002",
    "event_type": "node_completed",
    "node_name": "knowledge_retrieval",
    "data": {
      "articles_retrieved": 3,
      "top_article": "kb://billing-refunds#seats"
    },
    "duration_ms": 320,
    "tokens_used": 650,
    "cost_estimate": 0.0013,
    "created_at": "2026-10-29T10:05:03Z"
  }
]
```

---

### 3.7 Send Customer Reply
- **Route:** `POST /api/v1/tickets/{id}/reply`
- **Minimum Role:** `agent`
- **Traceability:** `F8`, `F12`, `US-013`, `AC-052`, `AC-053`
- **Description:** Dispatches human-verified reply to the customer. Appends message to ticket conversation and updates status to `waiting_on_customer`.

#### Request Body (`ReplyCreate`):
```json
{
  "message": "We have investigated your Okta configuration and updated the SAML certificate. Please try logging in now.",
  "internal_note": "Verified IdP thumbprint with security operations."
}
```

#### Response (`200 OK` - `ReplyResponse`):
```json
{
  "ticket_id": "CD-1001",
  "message_id": "msg-999-new",
  "status": "waiting_on_customer"
}
```

---

### 3.8 Request Additional Information
- **Route:** `POST /api/v1/tickets/{id}/request-info`
- **Minimum Role:** `agent`
- **Traceability:** `US-013`, `AC-054`
- **Description:** Sends a targeted clarification request to the customer.

#### Request Body (`RequestInfoCreate`):
```json
{
  "question": "Could you provide the exact correlation ID shown in your Okta error screen?"
}
```

#### Response (`200 OK` - `ReplyResponse`):
Returns `ReplyResponse` with ticket status set to `waiting_on_customer`.

---

### 3.9 Escalate Ticket
- **Route:** `POST /api/v1/tickets/{id}/escalate`
- **Minimum Role:** `agent`
- **Traceability:** `F10`, `US-011`, `AC-045`, `AC-046`, `AC-047`
- **Description:** Routes ticket to a specialized team (e.g., Security, Billing, Legal, Senior Tier 3 Engineering). Updates status to `escalated`.

#### Request Body (`EscalateRequest`):
```json
{
  "target_team": "Security Operations",
  "policy_reason": "Multiple credential stuffing attempts detected on administrator account (CD-1005).",
  "severity": "critical"
}
```

#### Response (`200 OK` - `EscalateResponse`):
```json
{
  "escalation_id": "esc-888-uuid",
  "ticket_id": "CD-1005",
  "target_team": "Security Operations",
  "policy_reason": "Multiple credential stuffing attempts detected on administrator account (CD-1005).",
  "severity": "critical",
  "status": "open",
  "created_at": "2026-10-29T10:10:00Z"
}
```

---

## 4. Detailed Specification: Customer API (`/api/v1/customers`)

### 4.1 List Customers
- **Route:** `GET /api/v1/customers`
- **Minimum Role:** `viewer`
- **Description:** Returns a paginated list of registered customers.

#### Query Parameters:
| Parameter | Type | Default | Description |
|---|---|:---:|---|
| `plan` | `string` | `null` | Filter by subscription plan: `free`, `pro`, `business`, `enterprise`. |
| `offset` | `integer`| `0` | Pagination offset. |
| `limit` | `integer`| `50` | Maximum records per page. |

#### Response (`200 OK` - `CustomerListResponse`):
```json
{
  "items": [
    {
      "id": "cust-101-acme",
      "name": "Acme Corporation",
      "email": "support@acme.test",
      "plan": "enterprise",
      "created_at": "2026-10-20T00:00:00Z",
      "updated_at": "2026-10-20T00:00:00Z"
    }
  ],
  "total": 1,
  "offset": 0,
  "limit": 50
}
```

---

### 4.2 Get Customer 360-Degree Dossier
- **Route:** `GET /api/v1/customers/{id}`
- **Minimum Role:** `viewer`
- **Traceability:** `F4`, `US-005`, `AC-020`, `AC-021`, `AC-022`, `AC-023`
- **Description:** Retrieves 360-degree customer profile for the middle column of the agent console. Gathers customer data, active subscriptions, workspaces, storage quotas, recent tickets, and the **10 most recent persistent memory notes**.

#### Response (`200 OK` - `CustomerDetailResponse`):
```json
{
  "id": "cust-101-acme",
  "name": "Acme Corporation",
  "email": "support@acme.test",
  "plan": "enterprise",
  "created_at": "2026-10-20T00:00:00Z",
  "updated_at": "2026-10-20T00:00:00Z",
  "active_subscription": {
    "id": "sub-101",
    "customer_id": "cust-101-acme",
    "plan": "enterprise",
    "status": "active",
    "seats": 50,
    "current_period_end": "2027-10-20T00:00:00Z",
    "created_at": "2026-10-20T00:00:00Z",
    "updated_at": "2026-10-20T00:00:00Z"
  },
  "subscriptions": [
    {
      "id": "sub-101",
      "customer_id": "cust-101-acme",
      "plan": "enterprise",
      "status": "active",
      "seats": 50,
      "current_period_end": "2027-10-20T00:00:00Z",
      "created_at": "2026-10-20T00:00:00Z",
      "updated_at": "2026-10-20T00:00:00Z"
    }
  ],
  "workspaces": [
    {
      "id": "ws-101",
      "customer_id": "cust-101-acme",
      "name": "Acme Corp Production",
      "slug": "acme-corp-production",
      "storage_used_bytes": 4831838208,
      "storage_limit_bytes": 107374182400,
      "created_at": "2026-10-20T00:00:00Z",
      "updated_at": "2026-10-20T00:00:00Z"
    }
  ],
  "recent_tickets": [
    {
      "id": "CD-1001",
      "customer_id": "cust-101-acme",
      "assigned_to": null,
      "subject": "SSO login fails for whole team",
      "status": "new",
      "severity": "critical",
      "category": "login_issue",
      "channel": "web",
      "resolution_summary": null,
      "created_at": "2026-10-29T08:00:00Z",
      "updated_at": "2026-10-29T08:00:00Z",
      "customer_name": "Acme Corporation",
      "customer_plan": "enterprise",
      "customer_email": "support@acme.test"
    }
  ],
  "memory_notes": [
    {
      "id": "mem-001",
      "customer_id": "cust-101-acme",
      "memory_type": "preference",
      "content": "Customer requires SAML 2.0 via Okta; password logins are disabled organization-wide.",
      "created_at": "2026-10-22T14:30:00Z",
      "updated_at": "2026-10-22T14:30:00Z"
    }
  ]
}
```

#### Error Responses:
- `404 Not Found`: Customer ID not found.

---

### 4.3 Add Customer Memory Note
- **Route:** `POST /api/v1/customers/{id}/memory`
- **Minimum Role:** `agent`
- **Traceability:** `F11`, `N7`, `US-014`, `US-022`, `AC-056`, `AC-058`
- **Description:** Stores persistent customer context or troubleshooting learnings. Content is strictly scrubbed of API keys, credit cards, and passwords prior to storage.

#### Request Body (`CustomerMemoryCreate`):
```json
{
  "memory_type": "troubleshooting",
  "content": "Okta SSO integration requires certificate renewal every 12 months."
}
```

#### Response (`201 Created` - `CustomerMemoryResponse`):
```json
{
  "id": "mem-uuid-999",
  "customer_id": "cust-101-acme",
  "memory_type": "troubleshooting",
  "content": "Okta SSO integration requires certificate renewal every 12 months.",
  "created_at": "2026-10-29T10:15:00Z",
  "updated_at": "2026-10-29T10:15:00Z"
}
```

---

## 5. Connected Platform APIs Specification

### 5.1 Approvals API (`/api/v1/approvals`)
- `GET /api/v1/approvals`: List pending or historical approval requests.
  - Role: `viewer`
  - Query: `?status=pending|approved|rejected`
  - Returns: `list[ApprovalRequestResponse]`
- `POST /api/v1/approvals/{id}/approve`: Approve gated action (e.g. `create_refund_request`).
  - Role: `agent`
  - Triggers execution on the shared tool path and resumes LangGraph checkpointer.
  - Status codes: `200 OK`, `404 Not Found`, `409 Conflict` (already decided or run not paused).
- `POST /api/v1/approvals/{id}/reject`: Reject gated action.
  - Role: `agent`
  - Body: `{"rejection_reason": "Refund requested outside policy window"}`
  - Diverts LangGraph workflow directly into `escalation` node.

### 5.2 Knowledge Base API (`/api/v1/knowledge`)
- `POST /api/v1/knowledge/search`: Hybrid RAG retrieval over markdown support articles.
  - Role: `viewer`
  - Body: `{"query": "...", "category": "login_issue", "top_k": 3, "mode": "hybrid"}`
  - Returns: Reciprocal Rank Fusion (RRF, k=60) evidence hits with citations (`kb://<slug>#<section>`).
- `POST /api/v1/knowledge/reindex`: Re-chunks sample articles and populates vector index.
  - Role: `admin`
  - Returns: `200 OK` `{"indexed_articles": 15, "total_chunks": 48}`.

### 5.3 Audit API (`/api/v1/audit`)
- `GET /api/v1/audit`: Query immutable audit logs recorded by `AuditMiddleware`.
  - Role: `viewer`
  - Query: `?actor_id=...&route=...&offset=0&limit=50`
  - Returns: `list[AuditLogResponse]`

### 5.4 MCP Tools Discovery (`/api/v1/mcp/tools`)
- `GET /api/v1/mcp/tools`: Exposes registered read-only support tools for external MCP agents.
  - Role: `agent`
  - Returns list of tool schemas, argument requirements, and safety policies.

---

## 6. Frontend Type Synchronization Reference (`frontend/lib/types.ts`)

To ensure TypeScript strict compilation and end-to-end type safety, `frontend/lib/types.ts` mirrors the contracts defined above.
Any addition of query parameters, response attributes, or status enum values must update both backend schemas and frontend types.
