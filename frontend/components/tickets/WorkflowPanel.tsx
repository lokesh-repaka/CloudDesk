"use client";

import React from "react";
import { TicketDetail, WorkflowStateResponse } from "@/lib/types";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Alert } from "@/components/ui/Alert";

export interface WorkflowPanelProps {
  ticket: TicketDetail;
  workflowState?: WorkflowStateResponse | null;
  isLoadingWorkflow?: boolean;
  onRunWorkflow?: () => Promise<void>;
  onApprove?: () => void;
  onReject?: () => void;
  onEscalate?: () => void;
  onSendReply?: () => void;
  canAct?: boolean;
}

// 12 canonical steps in the CloudDesk LangGraph pipeline
export const PIPELINE_STEPS = [
  { id: "ticket_intake", name: "Ticket Intake", description: "Parse payload & initial metadata" },
  { id: "customer_context", name: "Customer Context", description: "Fetch 360° dossier & workspace state" },
  { id: "triage_classification", name: "Triage & Category", description: "Classify intent, urgency, severity" },
  { id: "knowledge_retrieval", name: "RAG Retrieval", description: "Hybrid vector search over articles" },
  { id: "specialist_routing", name: "Specialist Routing", description: "Assign specialist agent graph node" },
  { id: "resolution_planning", name: "Diagnostic Planning", description: "Root cause diagnosis & resolution plan" },
  { id: "tool_execution", name: "Tool Execution", description: "Run diagnostics or policy-checked tools" },
  { id: "approval_gate", name: "Human Approval Gate", description: "Interrupt if consequential actions proposed" },
  { id: "resume_resolution", name: "Action Execution", description: "Execute approved financial or write actions" },
  { id: "policy_escalation", name: "Policy Escalation", description: "Compliance, GDPR or tier auto-escalation" },
  { id: "customer_reply", name: "Customer Reply", description: "Generate grounded, empathetic response" },
  { id: "record_resolution", name: "Telemetry & Memory", description: "Record audit log, token metrics & memory" },
];

export function WorkflowPanel({
  ticket,
  workflowState,
  isLoadingWorkflow = false,
  onRunWorkflow,
  onApprove,
  onReject,
  onEscalate,
  onSendReply,
  canAct = true,
}: WorkflowPanelProps) {
  const isPendingApproval =
    ticket.status === "pending_approval" ||
    workflowState?.approval_status === "pending";

  const isCompleted =
    ticket.status === "resolved" ||
    ticket.status === "closed" ||
    workflowState?.status === "completed";

  const isRunning =
    workflowState?.status === "running" ||
    ticket.status === "in_progress";

  const diagnosis = workflowState?.diagnosis;
  const resolutionPlan = workflowState?.resolution_plan;

  return (
    <Card padding="none" className="flex flex-col h-full overflow-hidden">
      <CardHeader className="px-5 py-4 border-b border-slate-200 mb-0">
        <div className="flex items-center justify-between w-full">
          <CardTitle className="text-base font-semibold text-slate-900 flex items-center gap-2">
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
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              }
            >
              Run Pipeline
            </Button>
          )}
        </div>
      </CardHeader>

      <div className="p-4 sm:p-5 space-y-6 overflow-y-auto flex-1 bg-white">
        {!canAct && (
          <Alert variant="warning" title="Viewer Authorization">
            Workflow actions and approvals are disabled in read-only mode (AC-054).
          </Alert>
        )}

        {/* 12-Step Pipeline Overview */}
        <div>
          <div className="flex items-center justify-between mb-2.5">
            <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              12-Step Pipeline Execution
            </h4>
            <span className="text-2xs text-slate-400 font-mono">
              {workflowState?.current_node || (isCompleted ? "Completed" : "Idle")}
            </span>
          </div>

          <div className="space-y-1.5 border border-slate-200 rounded-lg p-2.5 bg-slate-50">
            {PIPELINE_STEPS.map((step, idx) => {
              const isCurrent = workflowState?.current_node === step.id;
              const isStepDone =
                isCompleted ||
                (workflowState?.completed_nodes &&
                  workflowState.completed_nodes.includes(step.id));

              return (
                <div
                  key={step.id}
                  className={`flex items-center justify-between p-2 rounded text-xs transition-colors ${
                    isCurrent
                      ? "bg-amber-100 border border-amber-300 text-amber-900 font-medium"
                      : isStepDone
                      ? "bg-white border border-slate-200 text-slate-700"
                      : "bg-transparent text-slate-400"
                  }`}
                >
                  <div className="flex items-center space-x-2">
                    <span className="font-mono text-2xs w-4 text-slate-400">
                      {(idx + 1).toString().padStart(2, "0")}
                    </span>
                    <span>{step.name}</span>
                  </div>
                  {isCurrent ? (
                    <Badge variant="warning" size="sm">Active</Badge>
                  ) : isStepDone ? (
                    <Badge variant="success" size="sm">Done</Badge>
                  ) : (
                    <Badge variant="neutral" size="sm">Pending</Badge>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Diagnosis & Root Cause */}
        <div>
          <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2.5">
            Diagnosis & Root Cause
          </h4>
          <div className="border border-slate-200 rounded-lg p-3.5 bg-white space-y-2 text-xs">
            {diagnosis ? (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-slate-500 font-medium">Classified Root Cause:</span>
                  <Badge variant="brand">{String(diagnosis.root_cause || "Identified")}</Badge>
                </div>
                {diagnosis.summary && (
                  <p className="text-slate-700 text-xs leading-relaxed font-sans">
                    {String(diagnosis.summary)}
                  </p>
                )}
                {diagnosis.confidence && (
                  <div className="flex items-center justify-between pt-1 border-t border-slate-100 text-2xs text-slate-500">
                    <span>Confidence Score:</span>
                    <span className="font-mono font-medium text-slate-700">
                      {Math.round(Number(diagnosis.confidence) * 100)}%
                    </span>
                  </div>
                )}
              </div>
            ) : (
              <p className="text-slate-500 italic">
                {isRunning
                  ? "Analyzing issue and determining root cause..."
                  : "No diagnostic findings recorded yet. Run the pipeline to analyze."}
              </p>
            )}
          </div>
        </div>

        {/* Evidence & Knowledge Citations */}
        <div>
          <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2.5">
            Evidence Citations
          </h4>
          <div className="border border-slate-200 rounded-lg p-3.5 bg-white space-y-2 text-xs">
            {resolutionPlan?.citations && Array.isArray(resolutionPlan.citations) && resolutionPlan.citations.length > 0 ? (
              <div className="space-y-2">
                {resolutionPlan.citations.map((cite: any, i: number) => (
                  <div key={i} className="p-2.5 bg-slate-50 rounded border border-slate-200 text-xs space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-slate-800">{cite.title || `Source #${i + 1}`}</span>
                      {cite.score && (
                        <Badge variant="info" size="sm">
                          Score: {(cite.score * 100).toFixed(0)}%
                        </Badge>
                      )}
                    </div>
                    {cite.snippet && (
                      <p className="text-slate-600 text-2xs font-sans line-clamp-2">
                        {cite.snippet}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-slate-500 italic">
                No citations referenced. Retrieved articles will appear here after RAG search.
              </p>
            )}
          </div>
        </div>

        {/* Action Panel */}
        <div className="pt-2 border-t border-slate-200">
          <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
            Workflow Actions
          </h4>

          {isPendingApproval && (
            <div className="mb-3 p-3 bg-amber-50 border border-amber-200 rounded-md">
              <p className="text-xs font-medium text-amber-900 mb-1">
                Approval Required
              </p>
              <p className="text-2xs text-amber-700">
                This workflow contains consequential actions (such as a customer refund or tier change) awaiting human authorization.
              </p>
            </div>
          )}

          <div className="grid grid-cols-2 gap-2">
            <Button
              variant="primary"
              size="sm"
              onClick={onApprove}
              disabled={!canAct || !isPendingApproval}
              className={isPendingApproval ? "bg-emerald-600 hover:bg-emerald-700 text-white" : ""}
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
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
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
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
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
