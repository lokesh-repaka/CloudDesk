"use client";

import React, { use, useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import {
  TicketDetail,
  CustomerDetail,
  WorkflowStateResponse,
  WorkflowEvent,
  Severity,
} from "@/lib/types";
import { useAuth } from "@/lib/auth";
import { usePolling } from "@/lib/usePolling";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import {
  TicketHeader,
  TicketConversation,
  CustomerDossier,
  WorkflowPanel,
  ApproveModal,
  RejectModal,
  ReplyModal,
  EscalateModal,
} from "@/components/tickets";

interface TicketPageProps {
  params: Promise<{ id: string }>;
}

export default function TicketDetailPage({ params }: TicketPageProps) {
  const resolvedParams = use(params);
  const ticketId = resolvedParams.id;

  const { canAct, role } = useAuth();

  const [ticket, setTicket] = useState<TicketDetail | null>(null);
  const [customer, setCustomer] = useState<CustomerDetail | null>(null);
  const [workflowState, setWorkflowState] = useState<WorkflowStateResponse | null>(null);
  const [events, setEvents] = useState<WorkflowEvent[]>([]);
  const [pendingApprovalId, setPendingApprovalId] = useState<string | null>(null);

  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingCustomer, setIsLoadingCustomer] = useState(false);
  const [isLoadingWorkflow, setIsLoadingWorkflow] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);

  // Modal open states
  const [isApproveOpen, setIsApproveOpen] = useState(false);
  const [isRejectOpen, setIsRejectOpen] = useState(false);
  const [isReplyOpen, setIsReplyOpen] = useState(false);
  const [isEscalateOpen, setIsEscalateOpen] = useState(false);

  const fetchTicketData = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);

      // 1. Fetch ticket detail
      const ticketData = await api.tickets.get(ticketId);
      setTicket(ticketData);

      // 2. Fetch customer dossier if customer_id is present
      if (ticketData.customer_id) {
        setIsLoadingCustomer(true);
        try {
          const customerData = await api.customers.get(ticketData.customer_id);
          setCustomer(customerData);
        } catch {
          setCustomer(null);
        } finally {
          setIsLoadingCustomer(false);
        }
      }

      // 3. Fetch workflow state if available
      try {
        const wfState = await api.tickets.getWorkflowState(ticketId);
        setWorkflowState(wfState);
      } catch {
        setWorkflowState(null);
      }

      // 4. Fetch telemetry events
      try {
        const evts = await api.tickets.getEvents(ticketId);
        setEvents(evts);
      } catch {
        setEvents([]);
      }

      // 5. Check for active pending approvals
      try {
        const approvals = await api.approvals.list({ ticket_id: ticketId, status: "pending" });
        if (approvals && approvals.length > 0) {
          setPendingApprovalId(approvals[0].id);
        } else {
          setPendingApprovalId(null);
        }
      } catch {
        setPendingApprovalId(null);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load ticket details");
    } finally {
      setIsLoading(false);
    }
  }, [ticketId]);

  useEffect(() => {
    fetchTicketData();
  }, [fetchTicketData]);

  // Live workflow polling (2 seconds interval per AC-053 and CLAUDE.md §11)
  const isWorkflowActive =
    ticket?.status === "in_progress" ||
    workflowState?.status === "running" ||
    workflowState?.status === "waiting_on_approval" ||
    isLoadingWorkflow;

  usePolling(
    async () => {
      if (!ticketId) return;
      try {
        const state = await api.tickets.getWorkflowState(ticketId);
        setWorkflowState(state);

        try {
          const evts = await api.tickets.getEvents(ticketId);
          setEvents(evts);
        } catch {
          // Non-critical telemetry fetch fail
        }

        // Check for approvals during poll
        if (state.status === "waiting_on_approval") {
          try {
            const approvals = await api.approvals.list({ ticket_id: ticketId, status: "pending" });
            if (approvals && approvals.length > 0) {
              setPendingApprovalId(approvals[0].id);
            }
          } catch {
            // Ignore
          }
        }

        // Check if workflow reached terminal state or paused for approval
        if (
          state.status === "completed" ||
          state.status === "waiting_on_approval" ||
          state.status === "failed"
        ) {
          const updatedTicket = await api.tickets.get(ticketId);
          setTicket(updatedTicket);

          // Stop polling if fully completed
          if (state.status === "completed" || state.status === "failed") {
            return false;
          }
        }
      } catch {
        // No active workflow
      }
    },
    {
      intervalMs: 2000,
      enabled: isWorkflowActive,
    }
  );

  // Dispatch message via inline composer
  const handleSendMessage = async (body: string) => {
    if (!canAct) {
      throw new Error("Viewer role cannot dispatch messages (AC-054)");
    }
    await api.tickets.reply(ticketId, { message: body });
    const updated = await api.tickets.get(ticketId);
    setTicket(updated);
    setActionNotice("Reply dispatched successfully to customer.");
    setTimeout(() => setActionNotice(null), 4000);
  };

  // Run or re-trigger workflow pipeline
  const handleRunWorkflow = async () => {
    if (!canAct) return;
    try {
      setIsLoadingWorkflow(true);
      await api.tickets.runWorkflow(ticketId);
      const state = await api.tickets.getWorkflowState(ticketId);
      setWorkflowState(state);

      try {
        const evts = await api.tickets.getEvents(ticketId);
        setEvents(evts);
      } catch {
        // Non-blocking telemetry
      }

      const updated = await api.tickets.get(ticketId);
      setTicket(updated);
      setActionNotice("LangGraph workflow analysis initiated.");
      setTimeout(() => setActionNotice(null), 4000);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to trigger workflow run");
    } finally {
      setIsLoadingWorkflow(false);
    }
  };

  // Modal Actions
  const handleConfirmApprove = async (
    approvalId: string,
    reason?: string,
    modifications?: Record<string, unknown>
  ) => {
    await api.approvals.approve(approvalId, { reason, modifications });
    setActionNotice("Proposed action approved. Workflow execution resumed.");
    setTimeout(() => setActionNotice(null), 4000);
    await fetchTicketData();
  };

  const handleConfirmReject = async (approvalId: string, reason: string) => {
    await api.approvals.reject(approvalId, { reason });
    setActionNotice("Action rejected. Ticket routed to policy escalation.");
    setTimeout(() => setActionNotice(null), 4000);
    await fetchTicketData();
  };

  const handleConfirmReply = async (message: string, internalNote?: string) => {
    await api.tickets.reply(ticketId, { message, internal_note: internalNote });
    setActionNotice("Customer reply dispatched successfully.");
    setTimeout(() => setActionNotice(null), 4000);
    await fetchTicketData();
  };

  const handleConfirmEscalate = async (
    targetTeam: string,
    policyReason: string,
    severity?: Severity
  ) => {
    await api.tickets.escalate(ticketId, {
      target_team: targetTeam,
      policy_reason: policyReason,
      severity,
    });
    setActionNotice(`Ticket escalated to ${targetTeam}.`);
    setTimeout(() => setActionNotice(null), 4000);
    await fetchTicketData();
  };

  // Loading skeleton
  if (isLoading && !ticket) {
    return (
      <div className="space-y-6">
        <div className="h-6 w-48 bg-slate-200 rounded animate-pulse" />
        <div className="h-32 bg-white rounded-lg border border-slate-200 p-6 animate-pulse space-y-4">
          <div className="h-6 bg-slate-200 rounded w-1/3" />
          <div className="h-4 bg-slate-100 rounded w-1/2" />
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <div className="lg:col-span-4 h-96 bg-white rounded-lg border border-slate-200 animate-pulse" />
          <div className="lg:col-span-4 h-96 bg-white rounded-lg border border-slate-200 animate-pulse" />
          <div className="lg:col-span-4 h-96 bg-white rounded-lg border border-slate-200 animate-pulse" />
        </div>
      </div>
    );
  }

  // Error state
  if (error && !ticket) {
    return (
      <div className="space-y-6 max-w-2xl mx-auto py-12">
        <Alert variant="danger" title="Unable to Load Ticket">
          {error}
        </Alert>
        <div className="flex items-center space-x-3">
          <Button variant="primary" onClick={fetchTicketData}>
            Retry
          </Button>
          <Link href="/tickets">
            <Button variant="secondary">Back to Tickets</Button>
          </Link>
        </div>
      </div>
    );
  }

  if (!ticket) {
    return (
      <div className="space-y-6 max-w-xl mx-auto py-12 text-center">
        <h2 className="text-xl font-bold text-slate-800">Ticket Not Found</h2>
        <p className="text-slate-500 text-sm">
          The requested ticket #{ticketId} could not be located in the database.
        </p>
        <Link href="/tickets">
          <Button variant="secondary">Return to Ticket Queue</Button>
        </Link>
      </div>
    );
  }

  const proposedAction =
    workflowState?.resolution_plan?.action ||
    (workflowState?.resolution_plan as any)?.action_name ||
    "create_refund_request";
  const proposedPayload =
    (workflowState?.resolution_plan?.action_payload as Record<string, unknown>) ||
    (workflowState?.resolution_plan?.parameters as Record<string, unknown>) ||
    null;
  const proposedReply =
    workflowState?.resolution_plan?.customer_reply ||
    (workflowState?.resolution_plan?.summary as string) ||
    "";

  return (
    <div className="space-y-6">
      {/* Role Banner for Viewers (AC-054) */}
      {!canAct && (
        <Alert variant="warning" title="Viewer Access (Read-Only)">
          You are currently signed in as a <strong>{role}</strong>. All write actions,
          message dispatching, workflow execution, and approvals are disabled.
        </Alert>
      )}

      {/* Action Notice feedback */}
      {actionNotice && (
        <Alert variant="info" title="Notification">
          {actionNotice}
        </Alert>
      )}

      {/* Ticket Header & Metadata */}
      <TicketHeader
        ticket={ticket}
        onRefresh={fetchTicketData}
        isRefreshing={isLoading}
      />

      {/* Three-Column Agent Workspace Layout (AC-052 & CLAUDE.md §11) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column: Messages & Composer */}
        <div className="lg:col-span-4 xl:col-span-5 flex flex-col h-[780px]">
          <TicketConversation
            messages={ticket.messages || []}
            ticketId={ticket.id}
            onSendMessage={handleSendMessage}
            canAct={canAct}
          />
        </div>

        {/* Center Column: Customer 360° Dossier */}
        <div className="lg:col-span-4 xl:col-span-3 flex flex-col h-[780px]">
          <CustomerDossier customer={customer} isLoading={isLoadingCustomer} />
        </div>

        {/* Right Column: Workflow Steps, Diagnosis, Citations & Actions */}
        <div className="lg:col-span-4 xl:col-span-4 flex flex-col h-[780px]">
          <WorkflowPanel
            ticket={ticket}
            workflowState={workflowState}
            events={events}
            isLoadingWorkflow={isLoadingWorkflow}
            onRunWorkflow={handleRunWorkflow}
            onApprove={() => setIsApproveOpen(true)}
            onReject={() => setIsRejectOpen(true)}
            onSendReply={() => setIsReplyOpen(true)}
            onEscalate={() => setIsEscalateOpen(true)}
            canAct={canAct}
          />
        </div>
      </div>

      {/* Action Modals (P13-3) */}
      <ApproveModal
        isOpen={isApproveOpen}
        onClose={() => setIsApproveOpen(false)}
        ticketId={ticket.id}
        approvalId={pendingApprovalId || `appr-${ticket.id}`}
        actionName={String(proposedAction)}
        actionPayload={proposedPayload}
        proposedReply={proposedReply}
        onApprove={handleConfirmApprove}
        canAct={canAct}
      />

      <RejectModal
        isOpen={isRejectOpen}
        onClose={() => setIsRejectOpen(false)}
        ticketId={ticket.id}
        approvalId={pendingApprovalId || `appr-${ticket.id}`}
        actionName={String(proposedAction)}
        onReject={handleConfirmReject}
        canAct={canAct}
      />

      <ReplyModal
        isOpen={isReplyOpen}
        onClose={() => setIsReplyOpen(false)}
        ticketId={ticket.id}
        initialMessage={proposedReply}
        onSendReply={handleConfirmReply}
        canAct={canAct}
      />

      <EscalateModal
        isOpen={isEscalateOpen}
        onClose={() => setIsEscalateOpen(false)}
        ticketId={ticket.id}
        currentSeverity={ticket.severity}
        onEscalate={handleConfirmEscalate}
        canAct={canAct}
      />
    </div>
  );
}
