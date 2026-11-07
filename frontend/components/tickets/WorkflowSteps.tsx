"use client";

import React, { useState } from "react";
import { WorkflowEvent } from "@/lib/types";
import { Badge } from "@/components/ui/Badge";

export type StepState =
  | "completed"
  | "active"
  | "paused"
  | "pending"
  | "skipped"
  | "failed";

export interface DerivedStep {
  id: string;
  name: string;
  description: string;
  state: StepState;
  durationMs?: number;
  tokensUsed?: number;
  costEstimate?: number;
  eventData?: Record<string, unknown>;
}

export const CANONICAL_STEPS: Array<{ id: string; name: string; description: string }> = [
  {
    id: "understand_ticket",
    name: "Understand Ticket",
    description: "Parse inbound ticket content, clean text, and extract structural intent.",
  },
  {
    id: "classify_severity",
    name: "Classify Severity",
    description: "Determine ticket category, urgency, and initial SLA response tier.",
  },
  {
    id: "customer_context",
    name: "Customer Context",
    description: "Fetch 360° customer profile, subscription tier, and historical memory.",
  },
  {
    id: "knowledge_retrieval",
    name: "Knowledge Retrieval",
    description: "Execute hybrid vector search across indexed knowledge base articles.",
  },
  {
    id: "troubleshooting",
    name: "Troubleshooting",
    description: "Formulate diagnostic hypotheses and cross-reference active incident state.",
  },
  {
    id: "resolution_planning",
    name: "Resolution Planning",
    description: "Synthesize root-cause diagnosis, recommended resolution, and proposed actions.",
  },
  {
    id: "risk_check",
    name: "Risk Assessment",
    description: "Evaluate policy guardrails, financial impact, and consequential action thresholds.",
  },
  {
    id: "human_approval",
    name: "Human Approval",
    description: "Pause pipeline with LangGraph interrupt when human approval is required.",
  },
  {
    id: "execute_resolution",
    name: "Execute Resolution",
    description: "Execute approved actions and integrations (refunds, seat adjustments, resets).",
  },
  {
    id: "escalation",
    name: "Policy Escalation",
    description: "Route ticket to specialized engineering, compliance, or human legal queues.",
  },
  {
    id: "ticket_summary",
    name: "Ticket Summary",
    description: "Compile comprehensive resolution audit summary and update ticket status.",
  },
  {
    id: "memory_update",
    name: "Memory Update",
    description: "Record durable customer preferences and relationship learnings into long-term memory.",
  },
];

/**
 * Derives step states and micro-telemetry for the 12 LangGraph nodes (CLAUDE.md §13 & §16).
 */
export function deriveSteps(
  completedNodes: string[] = [],
  currentNode?: string | null,
  status?: string,
  events: WorkflowEvent[] = []
): DerivedStep[] {
  const isWorkflowCompleted =
    status === "completed" || status === "resolved" || status === "closed";
  const isWaitingApproval =
    status === "waiting_on_approval" || currentNode === "human_approval";

  // Build telemetry lookup by node name from events
  const eventsByNode = new Map<string, WorkflowEvent>();
  for (const evt of events) {
    if (evt.node_name) {
      eventsByNode.set(evt.node_name, evt);
    }
  }

  // Branch routing detection
  const executedResolution = completedNodes.includes("execute_resolution");
  const escalated = completedNodes.includes("escalation");

  return CANONICAL_STEPS.map((step) => {
    let state: StepState = "pending";

    // 1. Check if node is completed
    if (completedNodes.includes(step.id)) {
      state = "completed";
    }
    // 2. Check if node is paused for approval
    else if (step.id === "human_approval" && isWaitingApproval) {
      state = "paused";
    }
    // 3. Check if node is actively executing
    else if (currentNode === step.id) {
      state = isWaitingApproval ? "paused" : "active";
    }
    // 4. Check conditional branch skips
    else if (step.id === "escalation" && executedResolution) {
      state = "skipped";
    } else if (step.id === "execute_resolution" && escalated) {
      state = "skipped";
    } else if (
      isWorkflowCompleted &&
      !completedNodes.includes(step.id) &&
      (step.id === "human_approval" || step.id === "escalation" || step.id === "execute_resolution")
    ) {
      state = "skipped";
    }

    // Attach telemetry from events
    const evt = eventsByNode.get(step.id);
    const durationMs = evt?.duration_ms;
    const tokensUsed = evt?.tokens_used;
    const costEstimate = evt?.cost_estimate;
    const eventData = evt?.data;

    return {
      id: step.id,
      name: step.name,
      description: step.description,
      state,
      durationMs,
      tokensUsed,
      costEstimate,
      eventData,
    };
  });
}

interface WorkflowStepsProps {
  steps: DerivedStep[];
  currentStepId?: string | null;
}

export function WorkflowSteps({ steps, currentStepId }: WorkflowStepsProps) {
  const [expandedStep, setExpandedStep] = useState<string | null>(null);

  const toggleExpand = (stepId: string) => {
    setExpandedStep((prev) => (prev === stepId ? null : stepId));
  };

  const renderStateBadge = (state: StepState) => {
    switch (state) {
      case "completed":
        return (
          <Badge variant="success" size="sm">
            Done
          </Badge>
        );
      case "active":
        return (
          <Badge variant="warning" size="sm" className="inline-flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-ping inline-block" />
            Active
          </Badge>
        );
      case "paused":
        return (
          <Badge variant="danger" size="sm">
            Paused (Approval)
          </Badge>
        );
      case "skipped":
        return (
          <Badge variant="neutral" size="sm">
            Bypassed
          </Badge>
        );
      case "failed":
        return (
          <Badge variant="danger" size="sm">
            Failed
          </Badge>
        );
      case "pending":
      default:
        return (
          <Badge variant="neutral" size="sm">
            Pending
          </Badge>
        );
    }
  };

  return (
    <div className="space-y-1.5 border border-slate-200 rounded-lg p-2.5 bg-slate-50">
      {steps.map((step, idx) => {
        const isCurrent = step.state === "active" || step.id === currentStepId;
        const isPaused = step.state === "paused";
        const isCompleted = step.state === "completed";
        const isExpanded = expandedStep === step.id;

        return (
          <div
            key={step.id}
            className={`rounded-md border text-xs transition-colors overflow-hidden ${
              isPaused
                ? "bg-rose-50 border-rose-200 text-rose-950 shadow-xs"
                : isCurrent
                ? "bg-amber-50/80 border-amber-300 text-amber-950 font-medium shadow-xs"
                : isCompleted
                ? "bg-white border-slate-200 text-slate-800"
                : "bg-transparent border-transparent text-slate-400"
            }`}
          >
            <div
              onClick={() => toggleExpand(step.id)}
              className="flex items-center justify-between p-2 cursor-pointer hover:bg-slate-100/60 select-none"
            >
              <div className="flex items-center space-x-2.5 truncate">
                <span className="font-mono text-2xs w-4 text-slate-400">
                  {(idx + 1).toString().padStart(2, "0")}
                </span>
                <span className="truncate">{step.name}</span>
              </div>

              <div className="flex items-center space-x-2 shrink-0">
                {step.durationMs !== undefined && (
                  <span className="font-mono text-2xs text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded">
                    {step.durationMs}ms
                  </span>
                )}
                {step.tokensUsed !== undefined && step.tokensUsed > 0 && (
                  <span className="font-mono text-2xs text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded hidden sm:inline">
                    {step.tokensUsed} tok
                  </span>
                )}
                {renderStateBadge(step.state)}
              </div>
            </div>

            {/* Expandable details */}
            {isExpanded && (
              <div className="px-3 pb-2.5 pt-1 border-t border-slate-200/60 text-2xs text-slate-600 bg-white space-y-1.5">
                <p className="font-sans text-slate-600">{step.description}</p>
                {step.costEstimate !== undefined && step.costEstimate > 0 && (
                  <div className="flex items-center justify-between text-slate-500">
                    <span>Estimated Cost:</span>
                    <span className="font-mono font-medium text-slate-700">
                      ${step.costEstimate.toFixed(5)}
                    </span>
                  </div>
                )}
                {step.eventData && Object.keys(step.eventData).length > 0 && (
                  <div className="mt-1 pt-1 border-t border-slate-100">
                    <span className="text-slate-400 font-mono">Payload:</span>
                    <pre className="font-mono text-2xs bg-slate-50 p-1.5 rounded mt-0.5 overflow-x-auto text-slate-700">
                      {JSON.stringify(step.eventData, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
