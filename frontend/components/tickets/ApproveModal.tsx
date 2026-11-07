"use client";

import React, { useState } from "react";
import { Modal } from "@/components/ui/Modal";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Alert } from "@/components/ui/Alert";

export interface ApproveModalProps {
  isOpen: boolean;
  onClose: () => void;
  ticketId: string;
  approvalId?: string | null;
  actionName?: string | null;
  actionPayload?: Record<string, unknown> | null;
  proposedReply?: string | null;
  onApprove: (
    approvalId: string,
    reason?: string,
    modifications?: Record<string, unknown>
  ) => Promise<void>;
  canAct?: boolean;
}

export function ApproveModal({
  isOpen,
  onClose,
  ticketId,
  approvalId,
  actionName,
  actionPayload,
  proposedReply,
  onApprove,
  canAct = true,
}: ApproveModalProps) {
  const [reason, setReason] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canAct || !approvalId) return;

    try {
      setIsSubmitting(true);
      setError(null);
      await onApprove(approvalId, reason.trim() || undefined);
      setReason("");
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to approve resolution");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Approve Consequential Action"
      description={`Review and authorize the proposed resolution for ticket #${ticketId}.`}
      size="lg"
      footer={
        <div className="flex items-center justify-end space-x-2.5">
          <Button variant="secondary" onClick={onClose} disabled={isSubmitting}>
            Cancel
          </Button>
          <Button
            variant="primary"
            onClick={handleSubmit}
            disabled={!canAct || !approvalId || isSubmitting}
            isLoading={isSubmitting}
            className="bg-emerald-600 hover:bg-emerald-700 active:bg-emerald-800 text-white"
            leftIcon={
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            }
          >
            Authorize Action
          </Button>
        </div>
      }
    >
      <div className="space-y-4 text-xs">
        {!canAct && (
          <Alert variant="warning" title="Viewer Access">
            Viewer role does not have authorization to approve actions (AC-054).
          </Alert>
        )}

        {error && (
          <Alert variant="danger" title="Approval Failed">
            {error}
          </Alert>
        )}

        {/* Proposed Action Summary */}
        <div className="p-3.5 bg-slate-50 border border-slate-200 rounded-lg space-y-2">
          <div className="flex items-center justify-between">
            <span className="font-semibold text-slate-700">Proposed Tool Invocations:</span>
            <Badge variant="brand">{actionName || "create_refund_request"}</Badge>
          </div>

          {actionPayload && Object.keys(actionPayload).length > 0 && (
            <div className="pt-2 border-t border-slate-200">
              <span className="text-2xs text-slate-500 font-mono block mb-1">
                Action Parameters:
              </span>
              <pre className="font-mono text-2xs bg-white p-2 rounded border border-slate-200 overflow-x-auto text-slate-800">
                {JSON.stringify(actionPayload, null, 2)}
              </pre>
            </div>
          )}
        </div>

        {/* Proposed Customer Reply Preview */}
        {proposedReply && (
          <div className="p-3.5 bg-slate-50 border border-slate-200 rounded-lg space-y-1">
            <span className="font-semibold text-slate-700 block">
              Associated Customer Response:
            </span>
            <p className="text-slate-600 font-sans leading-relaxed text-xs">
              {proposedReply}
            </p>
          </div>
        )}

        {/* Approval Rationale Input */}
        <div className="space-y-1.5 pt-1">
          <label htmlFor="approve-reason" className="font-medium text-slate-700 block">
            Approval Rationale (Optional audit record):
          </label>
          <textarea
            id="approve-reason"
            rows={3}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            disabled={!canAct || isSubmitting}
            placeholder="e.g. Verified customer billing history, refund complies with standard SLA policy."
            className="w-full rounded-md border border-slate-300 p-2.5 text-xs text-slate-800 focus:outline-none focus:ring-1 focus:ring-emerald-500"
          />
        </div>
      </div>
    </Modal>
  );
}
