# SKILLS.md — CloudDesk Engineering Playbook & Agent Skills

This document defines the core developer workflows, testing standards, architectural patterns, and execution skills required when contributing to **CloudDesk**. Refer to this alongside `CLAUDE.md`, `PLAN.md`, `MEMORY.md`, and `TASKS.md`.

---

## 1. Development & Dependency Management (`uv`)

CloudDesk uses **`uv`** as its official Python package and virtual environment manager.

- **Add a dependency:** `uv add <package>`
- **Add a dev dependency:** `uv add --dev <package>`
- **Run tests:** `uv run pytest`
- **Run tests on a specific file:** `uv run pytest tests/unit/test_config_logging.py -v`
- **Run the FastAPI server:** `uv run uvicorn backend.app.main:app --reload --port 8000`
- **Sync environment:** `uv sync`

*Never modify `uv.lock` manually. Always allow `uv` to resolve and update locks.*

---

## 2. Test-Driven Development (TDD) Workflow

Every task in `TASKS.md` follows a disciplined TDD cycle:

1. **Write Tests First**:
   - Unit tests go under `tests/unit/`.
   - API route tests go under `tests/api/`.
   - RAG pipeline tests go under `tests/rag/`.
   - Agent specialist tests go under `tests/agents/`.
   - End-to-end workflow tests go under `tests/workflow/`.
2. **Execute & Confirm Failure**:
   - Run the new test before writing implementation: verify it fails cleanly for the expected reason (e.g., `ModuleNotFoundError`, missing attribute, or assertion error).
3. **Implement Minimum Viable Code**:
   - Write the cleanest, minimal code necessary to satisfy the test specifications and adhere to project architecture.
4. **Verify & Refactor**:
   - Run tests with `uv run pytest`. Confirm all tests pass.
   - Never weaken or bypass tests to force a pass.
5. **Pytest Configuration Rules**:
   - Pytest uses `asyncio_mode = "auto"` with session or function scoping as specified.
   - Do not use arbitrary event loops that interfere with pytest-asyncio.

---

## 3. Backend Architectural Conventions

### 3.1 Settings & Configuration (`backend/app/core/config.py`)
- Define settings with Pydantic v2 `BaseSettings` (`pydantic-settings`).
- Read from `.env` with fallback defaults suitable for local offline development.
- Expose `get_settings()` wrapped with `@functools.lru_cache()` to prevent disk I/O on every request.
- Keep secrets strictly typed with `SecretStr` where applicable.

### 3.2 Structured JSON Logging (`backend/app/core/logging.py`)
- All logs must be output as valid JSON lines in production/demo mode.
- Mandatory fields on each log entry:
  - `timestamp` (ISO 8601 UTC)
  - `level` (INFO, WARNING, ERROR, DEBUG)
  - `logger` (module name)
  - `message`
- Context fields:
  - `request_id` (propagated via `contextvars`)
  - `workflow_id` (propagated via `contextvars` or log extras)
- **Zero Secrets in Logs**: Never log passwords, API keys, tokens, or raw payment details.

### 3.3 Error Handling & Status Codes
- All API errors return standard JSON: `{"detail": "Descriptive error message"}`.
- Specific domain status codes:
  - `400`: Invalid inputs or schema failures.
  - `401`: Missing or invalid JWT token.
  - `403`: Insufficient role (`require_role`).
  - `404`: Entity not found.
  - `409`: Conflict (e.g., ticket already waiting on approval, or resuming an unpaused run).
  - `422`: Unprocessable request or guardrail failure.
  - `503`: Dependency degraded (`/health/ready`).

### 3.4 Fault-Tolerant Tool Execution
- All tools are decorated with `@tool` and registered in `ToolRegistry`.
- Execution must always go through `ToolRegistry.execute(name, args, approved=...)`.
- Tool failures return `ToolResult(ok=False, error=...)` instead of raising unhandled exceptions into the LangGraph state machine.

---

## 4. Git & Task Execution Protocol

When tackling a task from `docs/TASKS.md`:

1. **Branching**:
   - Identify the assigned branch name from `docs/TASKS.md` (e.g., `feature/backend-config-logging`).
   - Create and checkout the feature branch off `development`.
   - Never commit directly to `main` (only `README.md` is on `main`).
2. **Implementation & Testing**:
   - Complete only the specified scope of the task.
   - Verify all unit and integration tests pass locally.
3. **Safety & Cleanliness Review**:
   - Check `git status` to ensure no temporary, secret, or `.env` files are untracked or staged.
   - Update `.gitignore` if new tools or caches generate artifacts.
4. **Documentation Updates**:
   - In `docs/TASKS.md`, update task status from `Pending ❌` to `Completed ✅`.
   - In `docs/MEMORY.md`, record the state in Honest Status with test counts and verified outcomes.
5. **PR Readiness**:
   - Generate a concise, factual pull request description ready to paste into GitHub.
