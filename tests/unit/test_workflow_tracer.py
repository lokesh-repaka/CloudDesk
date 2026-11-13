"""Unit and Security Tests for WorkflowTracer and Telemetry Events (P10-6).

Tests:
- Event creation and in-memory buffer tracking
- Node context manager timing (node_started, node_completed, duration_ms)
- Tool call and LLM call telemetry recording
- Approval request and resolution event recording
- Workflow completion and error recording
- Non-raising resilience (telemetry must NEVER crash workflow execution)
- Security audit: CWE-200 secret scrubbing in event payloads
- Security audit: CWE-400 payload bounding
"""

from __future__ import annotations

import pytest
from sqlalchemy.exc import OperationalError

from agents.tracer import (
    EVENT_APPROVAL_REQUESTED,
    EVENT_APPROVAL_RESOLVED,
    EVENT_ERROR,
    EVENT_LLM_CALLED,
    EVENT_NODE_COMPLETED,
    EVENT_NODE_STARTED,
    EVENT_TOOL_CALLED,
    EVENT_WORKFLOW_COMPLETED,
    WORKFLOW_EVENT_TYPES,
    WorkflowTracer,
    calculate_token_cost,
    record_llm,
    record_tool_calls,
    tracer_for,
)

# ============================================================================
# 1. Tracer Initialization & Helper Tests
# ============================================================================


def test_workflow_event_types_constants():
    """Verify all 8 canonical event types are defined and non-empty."""
    assert len(WORKFLOW_EVENT_TYPES) == 8
    assert EVENT_NODE_STARTED in WORKFLOW_EVENT_TYPES
    assert EVENT_NODE_COMPLETED in WORKFLOW_EVENT_TYPES
    assert EVENT_TOOL_CALLED in WORKFLOW_EVENT_TYPES
    assert EVENT_LLM_CALLED in WORKFLOW_EVENT_TYPES
    assert EVENT_APPROVAL_REQUESTED in WORKFLOW_EVENT_TYPES
    assert EVENT_APPROVAL_RESOLVED in WORKFLOW_EVENT_TYPES
    assert EVENT_ERROR in WORKFLOW_EVENT_TYPES
    assert EVENT_WORKFLOW_COMPLETED in WORKFLOW_EVENT_TYPES


def test_tracer_for_extracts_ticket_and_workflow_id():
    """Verify tracer_for factory correctly extracts state attributes."""
    state = {
        "ticket_id": "CD-1004",
        "workflow_id": "wf-custom-12345",
    }
    tracer = tracer_for(state)
    assert tracer.ticket_id == "CD-1004"
    assert tracer.workflow_id == "wf-custom-12345"


def test_calculate_token_cost():
    """Verify calculate_token_cost returns 0.0 for fake model and positive estimate for real model."""
    cost_fake = calculate_token_cost(
        prompt_tokens=1000, completion_tokens=500, model="fake"
    )
    assert cost_fake == 0.0

    cost_real = calculate_token_cost(
        prompt_tokens=1000, completion_tokens=500, model="claude-3-5-sonnet"
    )
    assert cost_real > 0.0


# ============================================================================
# 2. Node Context Manager & Timing Tests
# ============================================================================


@pytest.mark.asyncio
async def test_tracer_node_context_manager_lifecycle():
    """Verify async with tracer.node emits node_started and node_completed with positive duration."""
    tracer = WorkflowTracer(ticket_id="CD-1001", workflow_id="wf-test-01")

    async with tracer.node("understand_ticket", payload={"step": 1}):
        pass

    assert len(tracer.events_buffer) == 2
    started = tracer.events_buffer[0]
    completed = tracer.events_buffer[1]

    assert started["event_type"] == EVENT_NODE_STARTED
    assert started["node_name"] == "understand_ticket"
    assert started["ticket_id"] == "CD-1001"
    assert started["workflow_id"] == "wf-test-01"
    assert started["payload"]["step"] == 1

    assert completed["event_type"] == EVENT_NODE_COMPLETED
    assert completed["node_name"] == "understand_ticket"
    assert completed["duration_ms"] >= 0


@pytest.mark.asyncio
async def test_tracer_node_context_manager_records_error_on_exception():
    """Verify tracer emits error event and reraises when an exception occurs inside node."""
    tracer = WorkflowTracer(ticket_id="CD-1001", workflow_id="wf-test-02")

    with pytest.raises(ValueError, match="Simulated node failure"):
        async with tracer.node("troubleshooting"):
            raise ValueError("Simulated node failure")

    assert len(tracer.events_buffer) == 2
    assert tracer.events_buffer[0]["event_type"] == EVENT_NODE_STARTED
    error_event = tracer.events_buffer[1]
    assert error_event["event_type"] == EVENT_ERROR
    assert error_event["node_name"] == "troubleshooting"
    assert "Simulated node failure" in error_event["payload"]["error"]


# ============================================================================
# 3. Tool & LLM Telemetry Recording Tests
# ============================================================================


@pytest.mark.asyncio
async def test_record_tool_call_and_batch_helper():
    """Verify recording single and batch tool calls."""
    tracer = WorkflowTracer(ticket_id="CD-1002", workflow_id="wf-test-03")

    await tracer.record_tool_call(
        node_name="knowledge_retrieval",
        tool_name="search_docs",
        arguments={"query": "refund policy"},
        result={"hits": 3},
        duration_ms=45,
    )

    assert len(tracer.events_buffer) == 1
    event = tracer.events_buffer[0]
    assert event["event_type"] == EVENT_TOOL_CALLED
    assert event["node_name"] == "knowledge_retrieval"
    assert event["payload"]["tool_name"] == "search_docs"
    assert event["payload"]["arguments"]["query"] == "refund policy"
    assert event["payload"]["result"]["hits"] == 3
    assert event["duration_ms"] == 45

    # Test batch helper
    calls = [
        {
            "tool_name": "check_service_status",
            "arguments": {"service_name": "billing"},
            "result": "operational",
        }
    ]
    await record_tool_calls(tracer, "troubleshooting", calls)
    assert len(tracer.events_buffer) == 2
    assert tracer.events_buffer[1]["payload"]["tool_name"] == "check_service_status"


@pytest.mark.asyncio
async def test_record_llm_call_and_helper():
    """Verify recording LLM usage telemetry."""
    tracer = WorkflowTracer(ticket_id="CD-1003", workflow_id="wf-test-04")

    await tracer.record_llm_call(
        node_name="classify_severity",
        model="claude-3-5-sonnet",
        prompt_tokens=250,
        completion_tokens=40,
        duration_ms=180,
        purpose="severity_assessment",
    )

    assert len(tracer.events_buffer) == 1
    event = tracer.events_buffer[0]
    assert event["event_type"] == EVENT_LLM_CALLED
    assert event["node_name"] == "classify_severity"
    assert event["tokens_used"] == 290
    assert event["duration_ms"] == 180
    assert event["payload"]["purpose"] == "severity_assessment"

    # Test record_llm helper
    usage = {"prompt_tokens": 120, "completion_tokens": 30, "total_tokens": 150}
    await record_llm(
        tracer, "understand_ticket", usage, ms=95, purpose="ticket_understanding"
    )
    assert len(tracer.events_buffer) == 2
    assert tracer.events_buffer[1]["tokens_used"] == 150


# ============================================================================
# 4. Approval and Workflow Completion Telemetry Tests
# ============================================================================


@pytest.mark.asyncio
async def test_approval_requested_and_resolved_events():
    """Verify recording approval requests and decisions."""
    tracer = WorkflowTracer(ticket_id="CD-1002", workflow_id="wf-test-05")

    await tracer.record_approval_requested(
        node_name="risk_check",
        request_data={"tool_name": "create_refund_request", "amount": 90.0},
    )
    await tracer.record_approval_resolved(
        node_name="human_approval",
        decision_data={"decision": "approved", "approver": "agent@clouddesk.demo"},
    )
    await tracer.record_workflow_completed(
        node_name="tail",
        data={"final_status": "completed"},
    )

    assert len(tracer.events_buffer) == 3
    assert tracer.events_buffer[0]["event_type"] == EVENT_APPROVAL_REQUESTED
    assert tracer.events_buffer[0]["payload"]["tool_name"] == "create_refund_request"

    assert tracer.events_buffer[1]["event_type"] == EVENT_APPROVAL_RESOLVED
    assert tracer.events_buffer[1]["payload"]["decision"] == "approved"

    assert tracer.events_buffer[2]["event_type"] == EVENT_WORKFLOW_COMPLETED


# ============================================================================
# 5. Resilience Test: Never Raises on Error
# ============================================================================


@pytest.mark.asyncio
async def test_tracer_never_raises_on_db_exception():
    """Verify tracer catches and swallows internal exceptions so telemetry never breaks workflow execution."""

    class BrokenSession:
        def add(self, entity):
            raise OperationalError("INSERT INTO workflow_events failed", None, None)

        async def flush(self):
            raise OperationalError("DB connection dropped", None, None)

    tracer = WorkflowTracer(ticket_id="CD-1001", session=BrokenSession())

    # Emitting events must NOT raise
    try:
        await tracer.emit(
            event_type=EVENT_NODE_STARTED,
            node_name="understand_ticket",
            payload={"test": "data"},
        )
    except Exception as exc:  # noqa: BLE001
        pytest.fail(f"WorkflowTracer.emit raised an exception: {exc}")

    # Buffer still records the event in memory
    assert len(tracer.events_buffer) == 1
    assert tracer.events_buffer[0]["event_type"] == EVENT_NODE_STARTED


# ============================================================================
# 6. Security Audit & Penetration Tests (CWE-200, CWE-400)
# ============================================================================


@pytest.mark.asyncio
async def test_security_cwe_200_no_secrets_stored_in_telemetry_payloads():
    """Security Audit (CWE-200): Secrets, API keys, and credentials in event payloads are scrubbed."""
    tracer = WorkflowTracer(ticket_id="CD-1005", workflow_id="wf-sec-01")

    dirty_payload = {
        "api_key": "sk-ant-api03-abcdef1234567890abcdef1234567890abcdef12",
        "connection_string": "postgresql://admin:supersecretpwd@postgres.internal:5432/clouddesk",
        "credit_card": "4111111111111111",
        "normal_field": "safe diagnostics",
    }

    await tracer.emit(
        event_type=EVENT_TOOL_CALLED,
        node_name="troubleshooting",
        payload=dirty_payload,
    )

    recorded = tracer.events_buffer[0]["payload"]
    assert recorded["normal_field"] == "safe diagnostics"

    # Ensure none of the secret patterns match the stored payload
    payload_str = str(recorded)
    assert "sk-ant-api03-abcdef" not in payload_str
    assert "supersecretpwd" not in payload_str
    assert "4111111111111111" not in payload_str
    assert "***REDACTED***" in payload_str


@pytest.mark.asyncio
async def test_security_cwe_400_oversized_payload_bounded():
    """Security Audit (CWE-400): Massive event payloads (>100KB) are bounded to prevent memory exhaustion."""
    tracer = WorkflowTracer(ticket_id="CD-1001", workflow_id="wf-dos-01")

    massive_text = "A" * 150_000
    await tracer.emit(
        event_type=EVENT_NODE_COMPLETED,
        node_name="customer_context",
        payload={"raw_notes": massive_text},
    )

    recorded = tracer.events_buffer[0]["payload"]
    stored_text = recorded["raw_notes"]
    assert len(stored_text) <= 50_000
