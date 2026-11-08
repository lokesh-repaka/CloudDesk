"use client";

import React from "react";
import { TicketDetail, WorkflowStateResponse, WorkflowEvent } from "@/lib/types";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Alert } from "@/components/ui/Alert";
import { WorkflowSteps, deriveSteps } from "./WorkflowSteps";

export interface WorkflowPanelProps {
  ticket: TicketDetail;
  workflowState?: WorkflowStateResponse | null;
  events?: WorkflowEvent[];
  isLoadingWorkflow?: boolean;
  onRunWorkflow?: () => Promise<void>;
  onApprove?: () => void;
  onReject?: () => void;
  onEscalate?: () => void;
  onSendReply?: () => void;
  canAct?: boolean;
}

export function WorkflowPanel({
  ticket,
  workflowState,
  events = [],
  isLoadingWorkflow = false,
  onRunWorkflow,
  onApprove,
  onReject,
  onEscalate,
  onSendReply,
  canAct = true,
}: WorkflowPanelProps) {
  const isPendingApproval =
    ticket.status === "waiting_on_approval" ||
    workflowState?.status === "waiting_on_approval";

  const isCompleted =
    ticket.status === "resolved" ||
    ticket.status === "closed" ||
    workflowState?.status === "completed";

  const isRunning =
    workflowState?.status === "running" ||
    ticket.status === "in_progress";

  const diagnosis = workflowState?.diagnosis;
  const resolutionPlan = workflowState?.resolution_plan;

  // Derive steps using the 12 LangGraph nodes and telemetry events
  const derivedSteps = deriveSteps(
    workflowState?.completed_nodes || [],
    workflowState?.current_node,
    workflowState?.status || (isPendingApproval ? "waiting_on_approval" : undefined),
    events
  );

  // Compute aggregate telemetry
  const totalTokens =
    workflowState?.token_usage?.total_tokens ||
    events.reduce((sum, e) => sum + (e.tokens_used || 0), 0);
  const promptTokens = workflowState?.token_usage?.prompt_tokens || 0;
  const completionTokens = workflowState?.token_usage?.completion_tokens || 0;

  const totalDurationMs = events.reduce((sum, e) => sum + (e.duration_ms || 0), 0);
  const totalCost = events.reduce((sum, e) => sum + (e.cost_estimate || 0), 0);

  return (
    <Card padding="none" className="flex flex-col h-full overflow-hidden">
      <CardHeader className="px-5 py-4 border-b border-[#162d36] mb-0 bg-[#0c181d]">
        <div className="flex items-center justify-between w-full">
          <CardTitle className="text-sm font-extrabold text-white flex items-center gap-2">
            <span>Workflow Engine</span>
            {isRunning && <Badge variant="warning">RUNNING</Badge>}
            {isPendingApproval && <Badge variant="danger">PAUSED (APPROVAL)</Badge>}
            {isCompleted && <Badge variant="success">COMPLETED</Badge>}
            {!isRunning && !isPendingApproval && !isCompleted && (
              <Badge variant="neutral">READY</Badge>
            )}
          </CardTitle>

          {onRunWorkflow && (
            <Button
              variant="primary"
              size="xs"
              onClick={onRunWorkflow}
              disabled={!canAct || isRunning || isLoadingWorkflow}
              isLoading={isLoadingWorkflow}
              leftIcon={
                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"
                  />
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
              }
            >
              Run Pipeline
            </Button>
          )}
        </div>
      </CardHeader>

      <div className="p-4 sm:p-5 space-y-6 overflow-y-auto flex-1 bg-[#0c181d]">
        {!canAct && (
          <Alert variant="warning" title="Viewer Authorization">
            Workflow actions and approvals are disabled in read-only mode (AC-054).
          </Alert>
        )}

        {/* Telemetry Metrics Bar (CLAUDE.md §16) */}
        {(totalTokens > 0 || totalDurationMs > 0) && (
          <div className="grid grid-cols-3 gap-2 p-3 bg-[#0f2127] border border-[#193641] rounded-xl text-xs">
            <div>
              <span className="text-3xs text-[#7e9aa6] block">Total Tokens</span>
              <span className="font-mono font-bold text-[#00d2b4]">
                {totalTokens.toLocaleString()}
              </span>
              {promptTokens > 0 && completionTokens > 0 && (
                <span className="text-3xs text-[#5a7683] block font-mono">
                  {promptTokens}p / {completionTokens}c
                </span>
              )}
            </div>

            <div>
              <span className="text-3xs text-[#7e9aa6] block">Pipeline Runtime</span>
              <span className="font-mono font-bold text-white">
                {totalDurationMs > 1000
                  ? `${(totalDurationMs / 1000).toFixed(2)}s`
                  : `${totalDurationMs}ms`}
              </span>
              <span className="text-3xs text-[#5a7683] block">
                {events.length} events
              </span>
            </div>

            <div>
              <span className="text-3xs text-[#7e9aa6] block">Estimated Cost</span>
              <span className="font-mono font-bold text-[#facc15]">
                ${totalCost.toFixed(5)}
              </span>
              <span className="text-3xs text-[#5a7683] block">USD</span>
            </div>
          </div>
        )}

        {/* 12-Step LangGraph Pipeline Execution Steps (AC-053) */}
        <div>
          <div className="flex items-center justify-between mb-2.5">
            <h4 className="text-3xs font-bold text-[#6e8a96] uppercase tracking-wider">
              12-Step Pipeline Execution
            </h4>
            <span className="text-3xs text-[#00d2b4] font-mono">
              {workflowState?.current_node || (isCompleted ? "Completed" : "Idle")}
            </span>
          </div>

          <WorkflowSteps
            steps={derivedSteps}
            currentStepId={workflowState?.current_node}
          />
        </div>

        {/* Diagnosis & Root Cause */}
        <div>
          <h4 className="text-3xs font-bold text-[#6e8a96] uppercase tracking-wider mb-2.5">
            Diagnosis & Root Cause
          </h4>
          <div className="border border-[#193641] rounded-xl p-3.5 bg-[#0f2127] space-y-2 text-xs">
            {diagnosis ? (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-[#8fa7b3] font-medium">Classified Root Cause:</span>
                  <Badge variant="brand">{String(diagnosis.root_cause || "Identified")}</Badge>
                </div>
                {Boolean(diagnosis.summary) && (
                  <p className="text-slate-200 text-xs leading-relaxed font-sans">
                    {String(diagnosis.summary)}
                  </p>
                )}
                {Boolean(diagnosis.confidence) && (
                  <div className="flex items-center justify-between pt-1 border-t border-[#193641] text-3xs text-[#7e9aa6]">
                    <span>Confidence Score:</span>
                    <span className="font-mono font-bold text-[#00d2b4]">
                      {Math.round(Number(diagnosis.confidence) * 100)}%
                    </span>
                  </div>
                )}
              </div>
            ) : (
              <p className="text-[#7e9aa6] italic text-xs">
                {isRunning
                  ? "Analyzing issue and determining root cause..."
                  : "No diagnostic findings recorded yet. Run the pipeline to analyze."}
              </p>
            )}
          </div>
        </div>

        {/* Evidence & Knowledge Citations */}
        <div>
          <h4 className="text-3xs font-bold text-[#6e8a96] uppercase tracking-wider mb-2.5">
            Evidence Citations
          </h4>
          <div className="border border-[#193641] rounded-xl p-3.5 bg-[#0f2127] space-y-2 text-xs">
            {resolutionPlan?.citations &&
            Array.isArray(resolutionPlan.citations) &&
            resolutionPlan.citations.length > 0 ? (
              <div className="space-y-2">
                {resolutionPlan.citations.map((cite: any, i: number) => (
                  <div
                    key={i}
                    className="p-2.5 bg-[#0c181d] rounded-lg border border-[#162d36] text-xs space-y-1"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-white">
                        {cite.title || `Source #${i + 1}`}
                      </span>
                      {Boolean(cite.score) && (
                        <Badge variant="info" size="sm">
                          Score: {(cite.score * 100).toFixed(0)}%
                        </Badge>
                      )}
                    </div>
                    {Boolean(cite.snippet) && (
                      <p className="text-[#8fa7b3] text-2xs font-sans line-clamp-2">
                        {cite.snippet}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-[#7e9aa6] italic text-xs">
                No citations referenced. Retrieved articles will appear here after RAG search.
              </p>
            )}
          </div>
        </div>

        {/* Action Panel */}
        <div className="pt-2 border-t border-[#162d36]">
          <h4 className="text-3xs font-bold text-[#6e8a96] uppercase tracking-wider mb-3">
            Workflow Actions
          </h4>

          {isPendingApproval && (
            <div className="mb-3 p-3 bg-[#241a06] border border-[#523d0e] rounded-xl">
              <p className="text-xs font-bold text-[#facc15] mb-1">Approval Required</p>
              <p className="text-3xs text-[#d1b87a]">
                This workflow contains consequential actions (such as a customer refund or tier change)
                awaiting human authorization.
              </p>
            </div>
          )}

          <div className="grid grid-cols-2 gap-2">
            <Button
              variant="primary"
              size="sm"
              onClick={onApprove}
              disabled={!canAct || !isPendingApproval}
              className={isPendingApproval ? "bg-[#10b981] hover:bg-[#34d399] text-[#06120d] font-bold" : ""}
              leftIcon={
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              }
            >
              Approve
            </Button>

            <Button
              variant="danger"
              size="sm"
              onClick={onReject}
              disabled={!canAct || !isPendingApproval}
              leftIcon={
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              }
            >
              Reject
            </Button>

            <Button
              variant="secondary"
              size="sm"
              onClick={onSendReply}
              disabled={!canAct}
              leftIcon={
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
                  />
                </svg>
              }
            >
              Dispatch Reply
            </Button>

            <Button
              variant="outline"
              size="sm"
              onClick={onEscalate}
              disabled={!canAct}
              leftIcon={
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                  />
                </svg>
              }
            >
              Escalate
            </Button>
          </div>
        </div>
      </div>
    </Card>
  );
}
