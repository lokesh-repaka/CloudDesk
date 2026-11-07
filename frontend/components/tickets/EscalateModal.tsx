"use client";

import React, { useState } from "react";
import { Modal } from "@/components/ui/Modal";
import { Button } from "@/components/ui/Button";
import { Alert } from "@/components/ui/Alert";
import { Severity } from "@/lib/types";

export interface EscalateModalProps {
  isOpen: boolean;
  onClose: () => void;
  ticketId: string;
  currentSeverity?: Severity;
  onEscalate: (
    targetTeam: string,
    policyReason: string,
    severity?: Severity
  ) => Promise<void>;
  canAct?: boolean;
}

const TEAMS = [
  { id: "tier2_engineering", name: "Tier-2 Engineering & Platform Ops" },
  { id: "billing_specialist", name: "Billing & Finance Specialists" },
  { id: "security", name: "Security, Trust & Safety" },
  { id: "compliance_legal", name: "Legal & GDPR Compliance" },
  { id: "enterprise_support", name: "Enterprise Customer Success" },
];

export function EscalateModal({
  isOpen,
  onClose,
  ticketId,
  currentSeverity = "high",
  onEscalate,
  canAct = true,
}: EscalateModalProps) {
  const [targetTeam, setTargetTeam] = useState(TEAMS[0].id);
  const [policyReason, setPolicyReason] = useState("");
  const [severity, setSeverity] = useState<Severity>(currentSeverity);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canAct) return;

    if (!policyReason.trim()) {
      setError("A policy reason is required when escalating a ticket.");
      return;
    }

    try {
      setIsSubmitting(true);
      setError(null);
      await onEscalate(targetTeam, policyReason.trim(), severity);
      setPolicyReason("");
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to escalate ticket");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Policy Escalation"
      description={`Escalate ticket #${ticketId} to a human specialist team.`}
      size="md"
      footer={
        <div className="flex items-center justify-end space-x-2.5">
          <Button variant="secondary" onClick={onClose} disabled={isSubmitting}>
            Cancel
          </Button>
          <Button
            variant="primary"
            onClick={handleSubmit}
            disabled={!canAct || !policyReason.trim() || isSubmitting}
            isLoading={isSubmitting}
            className="bg-amber-600 hover:bg-amber-700 active:bg-amber-800 text-white"
            leftIcon={
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                />
              </svg>
            }
          >
            Confirm Escalation
          </Button>
        </div>
      }
    >
      <div className="space-y-4 text-xs">
        {!canAct && (
          <Alert variant="warning" title="Viewer Access">
            Viewer role does not have authorization to escalate tickets (AC-054).
          </Alert>
        )}

        {error && (
          <Alert variant="danger" title="Escalation Error">
            {error}
          </Alert>
        )}

        <div className="space-y-1.5">
          <label htmlFor="target-team" className="font-semibold text-slate-700 block">
            Target Specialist Queue:
          </label>
          <select
            id="target-team"
            value={targetTeam}
            onChange={(e) => setTargetTeam(e.target.value)}
            disabled={!canAct || isSubmitting}
            className="w-full rounded-md border border-slate-300 p-2.5 text-xs text-slate-800 focus:outline-none focus:ring-1 focus:ring-amber-500 bg-white"
          >
            {TEAMS.map((team) => (
              <option key={team.id} value={team.id}>
                {team.name}
              </option>
            ))}
          </select>
        </div>

        <div className="space-y-1.5">
          <label htmlFor="escalate-severity" className="font-semibold text-slate-700 block">
            Adjusted Severity:
          </label>
          <select
            id="escalate-severity"
            value={severity}
            onChange={(e) => setSeverity(e.target.value as Severity)}
            disabled={!canAct || isSubmitting}
            className="w-full rounded-md border border-slate-300 p-2.5 text-xs text-slate-800 focus:outline-none focus:ring-1 focus:ring-amber-500 bg-white"
          >
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
            <option value="critical">Critical</option>
          </select>
        </div>

        <div className="space-y-1.5">
          <label htmlFor="policy-reason" className="font-semibold text-slate-700 block">
            Policy Escalation Reason (Required):
          </label>
          <textarea
            id="policy-reason"
            rows={4}
            value={policyReason}
            onChange={(e) => setPolicyReason(e.target.value)}
            disabled={!canAct || isSubmitting}
            placeholder="e.g. Critical platform outage affecting enterprise SSO customer. Immediate engineer intervention required."
            className="w-full rounded-md border border-slate-300 p-2.5 text-xs text-slate-800 focus:outline-none focus:ring-1 focus:ring-amber-500"
          />
        </div>
      </div>
    </Modal>
  );
}
