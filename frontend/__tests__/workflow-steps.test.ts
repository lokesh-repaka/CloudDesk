import { describe, it, expect } from "vitest";
import {
  deriveSteps,
  CANONICAL_STEPS,
  DerivedStep,
} from "../components/tickets/WorkflowSteps";
import { WorkflowEvent } from "../lib/types";

describe("WorkflowSteps.deriveSteps (CLAUDE.md §13 & §16)", () => {
  const CANONICAL_12_NODES = [
    "understand_ticket",
    "classify_severity",
    "customer_context",
    "knowledge_retrieval",
    "troubleshooting",
    "resolution_planning",
    "risk_check",
    "human_approval",
    "execute_resolution",
    "escalation",
    "ticket_summary",
    "memory_update",
  ];

  it("contains all 12 canonical LangGraph nodes in exact pipeline order", () => {
    expect(CANONICAL_STEPS.length).toBe(12);
    CANONICAL_12_NODES.forEach((nodeId, idx) => {
      expect(CANONICAL_STEPS[idx].id).toBe(nodeId);
      expect(CANONICAL_STEPS[idx].name).toBeDefined();
      expect(CANONICAL_STEPS[idx].description).toBeDefined();
    });
  });

  it("marks all steps pending when graph has not started", () => {
    const steps = deriveSteps([], null, "new");
    expect(steps.length).toBe(12);
    steps.forEach((step) => {
      expect(step.state).toBe("pending");
    });
  });

  it("marks completed nodes and active node during execution", () => {
    const completedNodes = [
      "understand_ticket",
      "classify_severity",
      "customer_context",
    ];
    const currentNode = "knowledge_retrieval";

    const steps = deriveSteps(completedNodes, currentNode, "running");

    expect(steps[0].state).toBe("completed"); // understand_ticket
    expect(steps[1].state).toBe("completed"); // classify_severity
    expect(steps[2].state).toBe("completed"); // customer_context
    expect(steps[3].state).toBe("active"); // knowledge_retrieval
    expect(steps[4].state).toBe("pending"); // troubleshooting
  });

  it("marks human_approval as paused when waiting_on_approval", () => {
    const completedNodes = [
      "understand_ticket",
      "classify_severity",
      "customer_context",
      "knowledge_retrieval",
      "troubleshooting",
      "resolution_planning",
      "risk_check",
    ];

    const steps = deriveSteps(
      completedNodes,
      "human_approval",
      "waiting_on_approval"
    );

    const approvalStep = steps.find((s) => s.id === "human_approval");
    expect(approvalStep).toBeDefined();
    expect(approvalStep?.state).toBe("paused");
  });

  it("marks escalation as skipped when resolution is executed directly", () => {
    const completedNodes = [
      "understand_ticket",
      "classify_severity",
      "customer_context",
      "knowledge_retrieval",
      "troubleshooting",
      "resolution_planning",
      "risk_check",
      "execute_resolution",
      "ticket_summary",
      "memory_update",
    ];

    const steps = deriveSteps(completedNodes, null, "completed");

    const escalationStep = steps.find((s) => s.id === "escalation");
    expect(escalationStep).toBeDefined();
    expect(escalationStep?.state).toBe("skipped");

    const execStep = steps.find((s) => s.id === "execute_resolution");
    expect(execStep?.state).toBe("completed");
  });

  it("marks execute_resolution as skipped when policy escalation occurs", () => {
    const completedNodes = [
      "understand_ticket",
      "classify_severity",
      "customer_context",
      "knowledge_retrieval",
      "troubleshooting",
      "resolution_planning",
      "risk_check",
      "escalation",
      "ticket_summary",
      "memory_update",
    ];

    const steps = deriveSteps(completedNodes, null, "completed");

    const execStep = steps.find((s) => s.id === "execute_resolution");
    expect(execStep).toBeDefined();
    expect(execStep?.state).toBe("skipped");

    const escalationStep = steps.find((s) => s.id === "escalation");
    expect(escalationStep?.state).toBe("completed");
  });

  it("correctly integrates telemetry events (duration, tokens, cost)", () => {
    const completedNodes = ["understand_ticket", "knowledge_retrieval"];
    const mockEvents: WorkflowEvent[] = [
      {
        id: "evt-1",
        workflow_id: "wf-test",
        ticket_id: "CD-1002",
        event_type: "node_completed",
        node_name: "understand_ticket",
        data: { intent: "refund_inquiry" },
        duration_ms: 145,
        tokens_used: 320,
        cost_estimate: 0.00064,
        created_at: "2026-11-08T00:00:00Z",
      },
      {
        id: "evt-2",
        workflow_id: "wf-test",
        ticket_id: "CD-1002",
        event_type: "node_completed",
        node_name: "knowledge_retrieval",
        data: { articles_count: 3 },
        duration_ms: 410,
        tokens_used: 1200,
        cost_estimate: 0.0024,
        created_at: "2026-11-08T00:00:01Z",
      },
    ];

    const steps = deriveSteps(completedNodes, null, "in_progress", mockEvents);

    const step1 = steps.find((s) => s.id === "understand_ticket");
    expect(step1?.durationMs).toBe(145);
    expect(step1?.tokensUsed).toBe(320);
    expect(step1?.costEstimate).toBe(0.00064);
    expect(step1?.eventData).toEqual({ intent: "refund_inquiry" });

    const step2 = steps.find((s) => s.id === "knowledge_retrieval");
    expect(step2?.durationMs).toBe(410);
    expect(step2?.tokensUsed).toBe(1200);
    expect(step2?.costEstimate).toBe(0.0024);
  });
});
