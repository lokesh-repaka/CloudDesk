# MEMORY.md — CloudDesk Project 1

Durable facts for this repository. `CLAUDE.md` wins if this file drifts. Update this file when a decision, demo fact, or delivery status changes. Do not store secrets, customer payloads, or raw ticket bodies here.

## Product

- Fictional SaaS: **CloudDesk** (team collaboration, cloud file storage, billing, workspaces, API access).
- Users of this product are **support agents**. Customers do not use the console in v1.
- Pipeline for every ticket: Understand → Classify → Investigate → Retrieve → Troubleshoot → Decide → Resolve → Act → Escalate → Remember.
- v1 integrations are mocks. The product does not send real email and does not issue real refunds.
- v1 is English-only and has no customer-facing chat widget.
- Business metrics are tracked, never hard-coded: percent of tickets resolved without a human edit, median time to first response, escalation precision, refund approvals per week. Refunds are never zero-touch.

## Locked decisions

- Three tiers: Next.js 15 on `:3000`, FastAPI on `:8000`, then PostgreSQL/SQLite, Redis/fakeredis, Qdrant/in-memory, and `get_llm`.
- The workflow is a LangGraph graph in `agents/graph.py` with six specialists.
- Demo runtime is offline: `LLM_PROVIDER=fake`, `VECTOR_STORE=memory`, `USE_FAKE_REDIS=true`, SQLite, `InMemorySaver` when `CHECKPOINT_DB_PATH=:memory:`.
- SQLAlchemy models stay portable: JSON columns, `String(36)` UUIDs, same code on SQLite and Postgres.
- Postgres DDL in `database/schema.sql` is the cloud schema. SQLite tables are created at startup.
- The backend uses the service-role key on the server. The browser receives only the anon key.
- JWT is HS256. Demo tokens expire in 8 hours.
- Background workflows run in-process for v1.
- Image tags equal the git SHA once delivery exists. Nothing has been built or tagged yet.
- Stage 17 (Agentic DevOps) is optional and depends on stages 13–16. It is outside core Project 1 completion.
- 2026-10-25 — F14 / observability: process settings are `get_settings()` in `backend/app/core/config.py` (cached). JSON logs come from `setup_logging()` and `log_context()` in `backend/app/core/logging.py`. Every line includes `request_id` and `workflow_id` (`null` when unset). `model_dump()` redacts secrets and URL passwords; connection code reads the attributes.
- 2026-10-25 — N3: `RequestIdMiddleware` echoes a safe `X-Request-ID` or assigns a UUID, binds `log_context`, and sets the header on application responses, including 404 and 500. CORS sits outside it and exposes the header. `/health` and `/health/live` do not probe dependencies. `/health/ready` returns 200 `ready` or 503 `degraded` from configuration checks until the database, Redis, vector store, and LLM clients exist. Those details never include a URL, password, or API key.

## Roles

Enforced by `require_role` in `backend/app/core/security.py` (`viewer 1 < agent 2 < admin 3`).

| Role | Access |
|---|---|
| `viewer` | Read tickets, customers, knowledge, and audit |
| `agent` | Viewer access, plus run workflows, reply, approve/reject, and escalate |
| `admin` | Agent access, plus reindex knowledge and settings |

Demo users: `admin@clouddesk.demo`, `sam.agent@clouddesk.demo`, `vic.viewer@clouddesk.demo`.

## Domain constants

Categories, exactly these ten, defined first in `backend/app/schemas/common.py`:

`login_issue`, `billing`, `api_failure`, `workspace_permissions`, `storage_quota`, `integration`, `feature_request`, `account`, `security`, `other`.

- Statuses: `new`, `in_progress`, `waiting_on_customer`, `waiting_on_approval`, `escalated`, `resolved`, `closed`.
- Severity: `low`, `medium`, `high`, `critical`.
- Channels: `email`, `chat`, `web`, `api`.
- Plans in the demo set: free, pro, business, enterprise. Eight customers. Thirteen tickets.

| Ticket | What it must exercise |
|---|---|
| CD-1001 | Login issue, active incident, enterprise |
| CD-1002 | Billing refund; approval gate on `create_refund_request` |
| CD-1003 | API 429; rate-limit docs |
| CD-1004 | Storage quota and subscription limits |
| CD-1005 | Security; policy escalation |
| CD-1006 | Data loss; policy escalation |
| CD-1007 | Workspace permissions |
| CD-1008 | Integration failure |
| CD-1009 | Account deletion / GDPR; policy escalation |
| CD-1010 | Feature request; low severity by policy |
| CD-1011 | Payment dispute; policy escalation |
| CD-1012 | MFA recovery article |
| CD-1013 | Prompt injection; ticket text stays data |

Policy cases that rules decide, and the model must not override: dispute, deletion, security, data loss, legal, enterprise outage.

## Workflow facts

Graph order:

`understand_ticket` → `classify_severity` → `customer_context` → `knowledge_retrieval` → `troubleshooting` → `resolution_planning` → `risk_check`, then either `escalation`, `human_approval`, or `execute_resolution`, then `ticket_summary` → `memory_update` → END.

- `human_approval` calls `interrupt()`. Resume uses `Command(resume=…)`.
- Rejection of an approval routes to escalation.
- Node ids are the `completed_nodes` values the UI renders.
- `GET /api/v1/agents` is fed by `GRAPH_NODES` / `GRAPH_EDGES`.
- A second run while status is `waiting_on_approval` returns 409. Resuming a run that is not paused returns 409.
- `WorkflowTracer` never raises. Event names: `node_started`, `node_completed`, `tool_called`, `llm_called`, `approval_requested`, `approval_resolved`, `error`, `workflow_completed`.
- Exposed to operators: decisions, tool calls and results, evidence with scores, node timings, token counts, errors.
- Hidden: raw prompts, hidden chain-of-thought, other customers’ data, secrets.

Tools:

| Tool | Writes | Approval |
|---|---|---|
| `get_customer`, `get_subscription`, `get_ticket_history` | no | no |
| `search_docs`, `check_service_status` | no | no |
| `update_ticket` | tickets | no |
| `reset_demo_setting` | workspace admin | yes |
| `create_refund_request` | billing | yes |
| `create_escalation` | escalations | no |

Unknown tools require approval. Timeout is `TOOL_TIMEOUT_SECONDS`.

## RAG and memory facts

- Knowledge source: `sample_data/knowledge_base/*.md` (15 articles) with YAML front-matter `title`, `category`, `tags`, `summary`.
- Chunk on headings, then 900-character windows with 150-character overlap. Prefix each chunk with `"{title} - {heading}"`.
- Retrieval: semantic ∪ BM25 → reciprocal rank fusion (`k=60`) → heuristic rerank → optional LLM rerank → one hit per article.
- Modes: `hybrid` (default), `semantic`, `keyword`.
- Fake embeddings: hashed bag-of-words, 384 dimensions. Changing the embedding model requires admin `POST /knowledge/reindex`, which recreates the collection.
- Evidence fields: `id`, `title`, `source` (`kb://slug#section`), `snippet`, `score`, `url` (`/knowledge/<id>`), `article_id`.
- Customer-facing policy claims cite knowledge articles.
- Short-term memory TTL is 24 hours. Retrieval cache TTL is 300 seconds. Cache key shape: `rag:{mode}:{category}:{top_k}:{query}`.
- Long-term note types: `preference`, `past_issue`, `troubleshooting`, `note`. Recall up to 10 notes. After a run, store the past issue, the first three troubleshooting steps, and a resolution note.
- `SECRET_PATTERNS` covers card numbers, API keys, and passwords.

## Evaluation bar

These fail the build: classification accuracy ≥ 0.80, retrieval hit-rate@3 ≥ 0.75, escalation correctness ≥ 0.90, citation rate ≥ 0.90, grounding rate ≥ 0.90.

Cases live in `datasets/eval_cases.json` and each case needs a valid `expected_category`.

## Environment defaults worth remembering

- `APPROVAL_REQUIRED_FOR_REFUNDS=true`, `MAX_REFUND_WITHOUT_APPROVAL=0`.
- Demo rate limit: `RATE_LIMIT_PER_MINUTE=120`.
- `QDRANT_COLLECTION=clouddesk_knowledge`.
- `get_settings()` is cached. A `.env` change requires a server restart.
- Middleware order, outermost last: CORS → RequestId → RateLimit → Audit.
- Health: `/health`, `/health/live` (no I/O), `/health/ready` (db, redis, vector store, llm).

## Honest status

Update each row in place. Do not mark a row done from intention.

| Surface | State on 2026-11-07 |
|---|---|
| Repository contents | Core documentation ([CLAUDE.md](CLAUDE.md), [PLAN.md](PLAN.md), [SKILLS.md](SKILLS.md), [TASKS.md](TASKS.md), [API_CONTRACT.md](API_CONTRACT.md)) organized in `docs/`. Backend core settings, JSON logging, health routes, request-id middleware, CORS, offline test harness, Makefile, `.env.example`, domain schemas (`backend/app/schemas/`), SQLAlchemy 2.0 models, PostgreSQL DDL/RLS/migrations, async database core, repository layer, Support Ticket API (`backend/app/api/tickets.py`), Customer API (`backend/app/api/customers.py`), Knowledge Base API (`backend/app/api/knowledge.py`), RAG article loading and heading-based chunking pipeline (`backend/app/rag/chunking.py`), offline vector store and fake embeddings (`backend/app/rag/vector_store.py`), hybrid retriever (`backend/app/rag/retriever.py`), knowledge ingestion service and CLI (`backend/app/rag/ingest.py`, `make ingest`), sample dataset fixtures (`sample_data/`), `database/seed.sql`, demo bootstrap service, Tool Registry, Policy engine, Read-Only and Approval-Gated Write Support Tools (`backend/app/tools/`), external service protocols (`integrations/protocols.py`), mock service adapters (`integrations/mock/services.py`), integration factory (`integrations/factory.py`), Model Context Protocol (MCP) server (`integrations/mcp/`), MCP tool discovery API (`backend/app/api/mcp.py`), deterministic rules engine (`agents/rules.py`), guardrails and prompt injection defense (`backend/app/core/guardrails.py`), specialist agent prompt templates with security preamble (`agents/prompts.py`), specialist agents (`agents/specialists/supervisor.py`, `agents/specialists/customer.py`, `agents/specialists/knowledge.py`, `agents/specialists/troubleshooting.py`, `agents/specialists/resolution.py`, `agents/specialists/escalation.py`), and TypeScript type interfaces (`frontend/lib/types.ts`) in place. |
| Implemented | Phase 1 (Runtime skeleton), Phase 2 (Persistence and demo data), Phase 3 (Identity and request guards), Phase 4 (Support API), Phase 5 (Knowledge pipeline), Phase 6 (Tools and mocks), Phase 7 (Rules and guardrails: P7-1, P7-2, P7-3, P7-4), Phase 8 (Memory: P8-1, P8-2, P8-3), and Phase 9 (Specialist agents: P9-1 through P9-7) implemented and validated. Implemented `ESCALATION_RULES`, deterministic policy routing, `wrap_untrusted`, delimiter escaping against tag breakouts (CWE-116), immutable `SECURITY_PREAMBLE`, `scan_for_injection` catching CD-1013 and jailbreaks, `validate_customer_output` blocking internal URLs, credentials/secrets/PANs, and foreign customer identifiers/emails (AC-066, AC-067), secret scrubbing `scrub()` for credit cards (Luhn-checked), API keys, passwords, and connection credentials (AC-070, N7), raw conversation filtering `is_raw_ticket_body` (AC-071), `assess_risk` elevation on injection detection and output validation failure, telemetry sanitization (AC-057), `ShortTermMemory` facade (`memory/short_term.py`), `LongTermMemory` facade (`memory/long_term.py`), unified `MemoryService` (`memory/service.py`, `memory/memory_service.py`), workflow schemas (`backend/app/schemas/workflow.py`), `FakeLLM` provider, `call_structured()` (`backend/app/core/llm.py`), `SupervisorAgent` (`agents/specialists/supervisor.py`), `CustomerAgent` (`agents/specialists/customer.py`), `KnowledgeAgent` (`agents/specialists/knowledge.py`) with hybrid `search_docs` evidence retrieval and Jaccard token overlap for matching historical resolved cases, `TroubleshootingAgent` (`agents/specialists/troubleshooting.py`) with platform health check tool inspection (`check_service_status`), category-specific playbooks for all 10 canonical categories, incident cause/step enrichment, and strictly numbered remediation steps formatting (F7, AC-030, CLAUDE.md §7.1, §7.3), `ResolutionAgent` (`agents/specialists/resolution.py`) with deterministic action planning for allowed tools (`update_ticket`, `create_refund_request`, `reset_demo_setting`), rejection of arbitrary model-invented tools (AC-033), grounded customer reply drafting (`_ground_response`, AC-034), output guardrail enforcement with unsafe draft quarantine (AC-066, AC-067), and human-in-the-loop approval gating (F8, AC-032, AC-035, AC-038), and `EscalationAgent` (`agents/specialists/escalation.py`) with deterministic policy rule routing for security, data loss, GDPR deletion, payment disputes, legal threats, and outages (AC-043, policy rules always win), database persistence via `create_escalation` (AC-044), rejection of vague low-confidence model escalations on high severity (AC-045), and prompt injection isolation routing to Security (F10, CLAUDE.md §7.1, §7.2). |
| Validated locally | `tests/unit/test_config_logging.py`, `tests/api/test_health.py`, `tests/unit/test_offline_harness.py`, `tests/deployment/test_env_example.py`, `tests/unit/test_entities.py`, `tests/unit/test_postgres_schema.py`, `tests/unit/test_repositories.py`, `tests/unit/test_seed_service.py`, `tests/unit/test_security.py`, `tests/api/test_auth.py`, `tests/unit/test_redis.py`, `tests/unit/test_rate_limit.py`, `tests/unit/test_audit_middleware.py`, `tests/unit/test_schemas_contract.py`, `tests/api/test_tickets.py`, `tests/api/test_customers.py`, `tests/rag/test_chunking.py`, `tests/rag/test_vector_store.py`, `tests/rag/test_retriever.py`, `tests/rag/test_ingest.py`, `tests/api/test_knowledge.py`, `tests/unit/test_tools_policy_registry.py`, `tests/unit/test_tools_read_only.py`, `tests/unit/test_tools_approval_gated.py`, `tests/unit/test_integrations_mock.py`, `tests/api/test_mcp_api.py`, `tests/unit/test_rules.py`, `tests/unit/test_guardrail_injection.py`, `tests/unit/test_guardrail_output_validation.py`, `tests/unit/test_guardrail_secret_scrub.py`, `tests/unit/test_memory_short_term.py`, `tests/unit/test_memory_long_term.py`, `tests/unit/test_memory_service.py`, `tests/unit/test_workflow_schemas_fake_llm.py`, `tests/unit/test_agent_supervisor.py`, `tests/unit/test_agent_customer.py`, `tests/unit/test_agent_knowledge.py`, `tests/unit/test_agent_troubleshooting.py`, `tests/unit/test_agent_resolution.py`, and `tests/unit/test_agent_escalation.py`: 616 passed on this machine. `make lint` / `ruff` clean. |
| Cloud credentials | None used. |
| Applied to a real account | Nothing. |
| GitHub Actions | Workflow `.github/workflows/test.yml` active with ruff linter and pytest suite. |
| Phase plan | Phase 1, Phase 2, Phase 3, Phase 4, Phase 5, Phase 6, Phase 7, and Phase 8 complete; Phase 9 in progress (P9-1 through P9-7 complete; P9-8 unblocked). |

## Open questions from `CLAUDE.md` §20

- A Project 1 `README.md` was referenced by the course and was not supplied. Command names in `CLAUDE.md` §14 still need to be checked against it when it appears.
- Course paths `../docs/`, `../deployment-agent/`, and `../shared-infrastructure/` sit outside this repo. They are not copied in yet.
- Table counts disagree across the course notes (16 in the database doc, 15 data tables in the RLS note). `database/schema.sql` becomes the authority once it is written.
- Stage documents 00–17 are not in this repo. `PLAN_PHASE.md` is derived from `CLAUDE.md`, not from those missing files.

## Update protocol

- Record a new locked decision with the date and the requirement id it serves.
- When a phase exits, set its status in `PLAN_PHASE.md` and add one line here under Honest status.
- When a demo ticket’s expected behaviour changes, change the ticket table above and the matching test together.
- Leave secrets, tokens, connection strings, and ticket bodies out of this file.
