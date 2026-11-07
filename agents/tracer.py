"""Workflow Telemetry Tracer and Event Emitter (P10-6).

Provides:
- WorkflowTracer: Non-raising workflow telemetry recorder (CLAUDE.md §16, architecture.md §12).
- Writes discrete, strongly-typed events to `workflow_events` and maintains in-memory timeline:
  `node_started`, `node_completed`, `tool_called`, `llm_called`, `approval_requested`,
  `approval_resolved`, `error`, `workflow_completed`.
- Enforces secret scrubbing on all event payloads (CWE-200).
- Bounded payload sizes to prevent memory exhaustion (CWE-400).
- Telemetry never breaks execution: all recording operations catch and log errors safely.
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.guardrails import scrub
from backend.app.models.entities import WorkflowEvent, generate_uuid, get_utc_now

logger = logging.getLogger(__name__)

# Canonical Event Type Constants (CLAUDE.md §16)
EVENT_NODE_STARTED = "node_started"
EVENT_NODE_COMPLETED = "node_completed"
EVENT_TOOL_CALLED = "tool_called"
EVENT_LLM_CALLED = "llm_called"
EVENT_APPROVAL_REQUESTED = "approval_requested"
EVENT_APPROVAL_RESOLVED = "approval_resolved"
EVENT_ERROR = "error"
EVENT_WORKFLOW_COMPLETED = "workflow_completed"

WORKFLOW_EVENT_TYPES: tuple[str, ...] = (
    EVENT_NODE_STARTED,
    EVENT_NODE_COMPLETED,
    EVENT_TOOL_CALLED,
    EVENT_LLM_CALLED,
    EVENT_APPROVAL_REQUESTED,
    EVENT_APPROVAL_RESOLVED,
    EVENT_ERROR,
    EVENT_WORKFLOW_COMPLETED,
)


def calculate_token_cost(
    prompt_tokens: int,
    completion_tokens: int,
    model: str | None = None,
) -> float:
    """Estimate financial cost in USD of LLM token usage (estimates only; fake provider = 0.0)."""
    if not model or "fake" in model.lower():
        return 0.0
    # Standard pricing baseline: $3.00 / 1M prompt, $15.00 / 1M completion
    prompt_cost = (prompt_tokens / 1_000_000.0) * 3.00
    completion_cost = (completion_tokens / 1_000_000.0) * 15.00
    return round(prompt_cost + completion_cost, 6)


def _sanitize_and_bound_payload(data: Any, max_str_len: int = 50_000) -> Any:
    """Recursively scrub secrets and clamp string lengths to prevent data leaks and DoS."""
    if isinstance(data, str):
        clamped = data[:max_str_len]
        return scrub(clamped)
    elif isinstance(data, dict):
        return {
            str(k): _sanitize_and_bound_payload(v, max_str_len) for k, v in data.items()
        }
    elif isinstance(data, (list, tuple)):
        return [_sanitize_and_bound_payload(item, max_str_len) for item in data]
    return data


class WorkflowTracer:
    """Non-raising workflow execution tracer recording fine-grained telemetry."""

    def __init__(
        self,
        ticket_id: str,
        workflow_id: str | None = None,
        session: AsyncSession | None = None,
        session_factory: Any = None,
    ) -> None:
        self.ticket_id = ticket_id or "unknown"
        self.workflow_id = workflow_id or f"wf-{generate_uuid()[:12]}"
        self.session = session
        self.session_factory = session_factory
        self.events_buffer: list[dict[str, Any]] = []

    async def emit(
        self,
        event_type: str,
        node_name: str,
        payload: dict[str, Any] | None = None,
        duration_ms: int = 0,
        tokens_used: int = 0,
        cost_estimate: float = 0.0,
    ) -> dict[str, Any] | None:
        """Emit telemetry event to in-memory buffer and database without raising exceptions."""
        try:
            clean_payload = _sanitize_and_bound_payload(payload or {})
            event_id = generate_uuid()
            now_utc = get_utc_now()
            event_record = {
                "id": event_id,
                "workflow_id": self.workflow_id,
                "ticket_id": self.ticket_id,
                "event_type": event_type,
                "node_name": node_name,
                "payload": clean_payload,
                "duration_ms": max(0, int(duration_ms)),
                "tokens_used": max(0, int(tokens_used)),
                "cost_estimate": max(0.0, float(cost_estimate)),
                "created_at": now_utc,
            }
            self.events_buffer.append(event_record)

            if self.session is not None:
                wf_event = WorkflowEvent(
                    id=event_id,
                    workflow_id=self.workflow_id,
                    ticket_id=self.ticket_id,
                    event_type=event_type,
                    node_name=node_name,
                    payload=clean_payload,
                    duration_ms=event_record["duration_ms"],
                    tokens_used=event_record["tokens_used"],
                    cost_estimate=event_record["cost_estimate"],
                    created_at=now_utc,
                )
                self.session.add(wf_event)
                if hasattr(self.session, "flush"):
                    try:
                        await self.session.flush()
                    except Exception as flush_err:  # noqa: BLE001
                        logger.debug(
                            "WorkflowTracer session flush deferred: %s", flush_err
                        )
            elif self.session_factory is not None:
                try:
                    async with self.session_factory() as sess:
                        wf_event = WorkflowEvent(
                            id=event_id,
                            workflow_id=self.workflow_id,
                            ticket_id=self.ticket_id,
                            event_type=event_type,
                            node_name=node_name,
                            payload=clean_payload,
                            duration_ms=event_record["duration_ms"],
                            tokens_used=event_record["tokens_used"],
                            cost_estimate=event_record["cost_estimate"],
                            created_at=now_utc,
                        )
                        sess.add(wf_event)
                        await sess.commit()
                except Exception as sess_err:  # noqa: BLE001
                    logger.debug(
                        "WorkflowTracer factory session write skipped: %s", sess_err
                    )

            return event_record
        except Exception as exc:  # noqa: BLE001
            logger.warning("WorkflowTracer failed to emit event: %s", exc)
            return None

    @asynccontextmanager
    async def node(self, node_name: str, payload: dict[str, Any] | None = None):
        """Context manager tracing node entry, completion, execution duration, and errors."""
        await self.emit(
            event_type=EVENT_NODE_STARTED,
            node_name=node_name,
            payload=payload,
        )
        t0 = time.perf_counter()
        try:
            yield
            duration_ms = int((time.perf_counter() - t0) * 1000)
            await self.emit(
                event_type=EVENT_NODE_COMPLETED,
                node_name=node_name,
                duration_ms=duration_ms,
            )
        except Exception as exc:
            duration_ms = int((time.perf_counter() - t0) * 1000)
            await self.emit(
                event_type=EVENT_ERROR,
                node_name=node_name,
                payload={"error": str(exc), "error_type": type(exc).__name__},
                duration_ms=duration_ms,
            )
            raise

    async def record_tool_call(
        self,
        node_name: str,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        result: Any = None,
        duration_ms: int = 0,
    ) -> None:
        """Record tool invocation telemetry."""
        payload = {
            "tool_name": tool_name,
            "arguments": arguments or {},
            "result": result,
        }
        await self.emit(
            event_type=EVENT_TOOL_CALLED,
            node_name=node_name,
            payload=payload,
            duration_ms=duration_ms,
        )

    async def record_llm_call(
        self,
        node_name: str,
        model: str | None = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        duration_ms: int = 0,
        purpose: str | None = None,
    ) -> None:
        """Record model inference call telemetry and token expenditure."""
        tokens_used = prompt_tokens + completion_tokens
        cost = calculate_token_cost(prompt_tokens, completion_tokens, model)
        payload = {
            "model": model or "fake",
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "purpose": purpose or "inference",
        }
        await self.emit(
            event_type=EVENT_LLM_CALLED,
            node_name=node_name,
            payload=payload,
            duration_ms=duration_ms,
            tokens_used=tokens_used,
            cost_estimate=cost,
        )

    async def record_approval_requested(
        self,
        node_name: str,
        request_data: dict[str, Any] | None = None,
    ) -> None:
        """Record human approval requirement event."""
        await self.emit(
            event_type=EVENT_APPROVAL_REQUESTED,
            node_name=node_name,
            payload=request_data or {},
        )

    async def record_approval_resolved(
        self,
        node_name: str,
        decision_data: dict[str, Any] | None = None,
    ) -> None:
        """Record human approval resolution decision."""
        await self.emit(
            event_type=EVENT_APPROVAL_RESOLVED,
            node_name=node_name,
            payload=decision_data or {},
        )

    async def record_error(
        self,
        node_name: str,
        error_message: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Record runtime error telemetry."""
        payload = {"error": error_message, **(data or {})}
        await self.emit(
            event_type=EVENT_ERROR,
            node_name=node_name,
            payload=payload,
        )

    async def record_workflow_completed(
        self,
        node_name: str = "tail",
        data: dict[str, Any] | None = None,
    ) -> None:
        """Record full workflow termination."""
        await self.emit(
            event_type=EVENT_WORKFLOW_COMPLETED,
            node_name=node_name,
            payload=data or {},
        )


def tracer_for(
    state: dict[str, Any],
    session: AsyncSession | None = None,
    session_factory: Any = None,
) -> WorkflowTracer:
    """Instantiate a WorkflowTracer initialized from LangGraph state."""
    ticket_id = state.get("ticket_id") or "unknown"
    workflow_id = state.get("workflow_id")
    return WorkflowTracer(
        ticket_id=ticket_id,
        workflow_id=workflow_id,
        session=session,
        session_factory=session_factory,
    )


async def record_tool_calls(
    tracer: WorkflowTracer,
    node_name: str,
    calls: list[dict[str, Any]],
) -> None:
    """Helper to record a collection of tool calls (CLAUDE.md §7.3)."""
    for call in calls:
        tool_name = call.get("tool_name", "unknown")
        args = call.get("arguments") or call.get("args") or {}
        res = call.get("result")
        dur = call.get("duration_ms", 0)
        await tracer.record_tool_call(
            node_name=node_name,
            tool_name=tool_name,
            arguments=args,
            result=res,
            duration_ms=dur,
        )


async def record_llm(
    tracer: WorkflowTracer,
    node_name: str,
    usage: dict[str, int],
    ms: int,
    purpose: str,
) -> None:
    """Helper to record LLM token usage and duration (CLAUDE.md §7.3)."""
    p_tokens = usage.get("prompt_tokens") or usage.get("input_tokens") or 0
    c_tokens = usage.get("completion_tokens") or usage.get("output_tokens") or 0
    await tracer.record_llm_call(
        node_name=node_name,
        prompt_tokens=p_tokens,
        completion_tokens=c_tokens,
        duration_ms=ms,
        purpose=purpose,
    )
