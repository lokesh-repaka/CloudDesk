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
    <div className="space-y-1.5 border border-[#162d36] rounded-xl p-2.5 bg-[#091418]">
      {steps.map((step, idx) => {
        const isCurrent = step.state === "active" || step.id === currentStepId;
        const isPaused = step.state === "paused";
        const isCompleted = step.state === "completed";
        const isExpanded = expandedStep === step.id;

        return (
          <div
            key={step.id}
            className={`rounded-xl border text-xs transition-colors overflow-hidden ${
              isPaused
                ? "bg-[#251b07] border-[#5c400d] text-amber-200 shadow-xs"
                : isCurrent
                ? "bg-[#0d2a2f] border-[#00d2b4]/50 text-[#2dd4bf] font-semibold shadow-glow"
                : isCompleted
                ? "bg-[#0e1f26] border-[#183641] text-slate-200"
                : "bg-transparent border-transparent text-[#5a7683]"
            }`}
          >
            <div
              onClick={() => toggleExpand(step.id)}
              className="flex items-center justify-between p-2 cursor-pointer hover:bg-[#12272e] select-none transition-colors"
            >
              <div className="flex items-center space-x-2.5 truncate">
                <span className="font-mono text-3xs w-4 text-[#5a7683]">
                  {(idx + 1).toString().padStart(2, "0")}
                </span>
                <span className="truncate">{step.name}</span>
              </div>

              <div className="flex items-center space-x-2 shrink-0">
                {step.durationMs !== undefined && (
                  <span className="font-mono text-3xs text-[#7e9aa6] bg-[#0c181d] px-1.5 py-0.5 rounded border border-[#162d36]">
                    {step.durationMs}ms
                  </span>
                )}
                {step.tokensUsed !== undefined && step.tokensUsed > 0 && (
                  <span className="font-mono text-3xs text-[#7e9aa6] bg-[#0c181d] px-1.5 py-0.5 rounded border border-[#162d36] hidden sm:inline">
                    {step.tokensUsed} tok
                  </span>
                )}
                {renderStateBadge(step.state)}
              </div>
            </div>

            {/* Expandable details */}
            {isExpanded && (
              <div className="px-3 pb-2.5 pt-1.5 border-t border-[#183641] text-3xs text-[#8fa7b3] bg-[#081216] space-y-1.5">
                <p className="font-sans text-slate-300">{step.description}</p>
                {step.costEstimate !== undefined && step.costEstimate > 0 && (
                  <div className="flex items-center justify-between text-[#7e9aa6]">
                    <span>Estimated Cost:</span>
                    <span className="font-mono font-medium text-[#facc15]">
                      ${step.costEstimate.toFixed(5)}
                    </span>
                  </div>
                )}
                {step.eventData && Object.keys(step.eventData).length > 0 && (
                  <div className="mt-1 pt-1 border-t border-[#162d36]">
                    <span className="text-[#5a7683] font-mono">Payload:</span>
                    <pre className="font-mono text-3xs bg-[#050a0c] p-1.5 rounded-lg mt-0.5 overflow-x-auto text-[#00d2b4] border border-[#162d36]">
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
