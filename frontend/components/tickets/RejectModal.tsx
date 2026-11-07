"use client";

import React, { useState } from "react";
import { Modal } from "@/components/ui/Modal";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Alert } from "@/components/ui/Alert";

export interface RejectModalProps {
  isOpen: boolean;
  onClose: () => void;
  ticketId: string;
  approvalId?: string | null;
  actionName?: string | null;
  onReject: (approvalId: string, reason: string) => Promise<void>;
  canAct?: boolean;
}

export function RejectModal({
  isOpen,
  onClose,
  ticketId,
  approvalId,
  actionName,
  onReject,
  canAct = true,
}: RejectModalProps) {
  const [reason, setReason] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canAct || !approvalId) return;

    if (!reason.trim()) {
      setError("A rejection reason is required for compliance audit logs.");
      return;
    }

    try {
      setIsSubmitting(true);
      setError(null);
      await onReject(approvalId, reason.trim());
      setReason("");
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to reject resolution");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Reject Proposed Resolution"
      description={`Rejecting this action will cancel tool execution and route ticket #${ticketId} to escalation.`}
      size="md"
      footer={
        <div className="flex items-center justify-end space-x-2.5">
          <Button variant="secondary" onClick={onClose} disabled={isSubmitting}>
            Cancel
          </Button>
          <Button
            variant="danger"
            onClick={handleSubmit}
            disabled={!canAct || !approvalId || !reason.trim() || isSubmitting}
            isLoading={isSubmitting}
            leftIcon={
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            }
          >
            Reject & Escalate
          </Button>
        </div>
      }
    >
      <div className="space-y-4 text-xs">
        {!canAct && (
          <Alert variant="warning" title="Viewer Access">
            Viewer role does not have authorization to reject actions (AC-054).
          </Alert>
        )}

        {error && (
          <Alert variant="danger" title="Validation / Error">
            {error}
          </Alert>
        )}

        <div className="p-3.5 bg-rose-50/60 border border-rose-200 rounded-lg space-y-1.5">
          <div className="flex items-center justify-between">
            <span className="font-semibold text-rose-900">Action to Reject:</span>
            <Badge variant="danger">{actionName || "create_refund_request"}</Badge>
          </div>
          <p className="text-2xs text-rose-800">
            Per LangGraph routing rules, rejecting a pending human approval automatically routes
            this ticket into the <code>escalation</code> node for specialist oversight.
          </p>
        </div>

        <div className="space-y-1.5">
          <label htmlFor="reject-reason" className="font-medium text-slate-700 block">
            Rejection Reason (Required):
          </label>
          <textarea
            id="reject-reason"
            rows={3}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            disabled={!canAct || isSubmitting}
            placeholder="e.g. Refund amount exceeds standard tier policy limit. Requires managerial sign-off."
            className="w-full rounded-md border border-slate-300 p-2.5 text-xs text-slate-800 focus:outline-none focus:ring-1 focus:ring-rose-500"
          />
        </div>
      </div>
    </Modal>
  );
}
