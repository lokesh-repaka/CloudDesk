"use client";

import React, { useState, useEffect } from "react";
import { Modal } from "@/components/ui/Modal";
import { Button } from "@/components/ui/Button";
import { Alert } from "@/components/ui/Alert";

export interface ReplyModalProps {
  isOpen: boolean;
  onClose: () => void;
  ticketId: string;
  initialMessage?: string | null;
  onSendReply: (message: string, internalNote?: string) => Promise<void>;
  canAct?: boolean;
}

export function ReplyModal({
  isOpen,
  onClose,
  ticketId,
  initialMessage,
  onSendReply,
  canAct = true,
}: ReplyModalProps) {
  const [message, setMessage] = useState(initialMessage || "");
  const [internalNote, setInternalNote] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (initialMessage && !message) {
      setMessage(initialMessage);
    }
  }, [initialMessage, message]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canAct || !message.trim()) return;

    try {
      setIsSubmitting(true);
      setError(null);
      await onSendReply(message.trim(), internalNote.trim() || undefined);
      setMessage("");
      setInternalNote("");
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to dispatch reply");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Dispatch Customer Reply"
      description={`Send verified response to the customer for ticket #${ticketId}.`}
      size="lg"
      footer={
        <div className="flex items-center justify-end space-x-2.5">
          <Button variant="secondary" onClick={onClose} disabled={isSubmitting}>
            Cancel
          </Button>
          <Button
            variant="primary"
            onClick={handleSubmit}
            disabled={!canAct || !message.trim() || isSubmitting}
            isLoading={isSubmitting}
            leftIcon={
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
                />
              </svg>
            }
          >
            Dispatch Reply
          </Button>
        </div>
      }
    >
      <div className="space-y-4 text-xs">
        {!canAct && (
          <Alert variant="warning" title="Viewer Access">
            Viewer role does not have authorization to send replies (AC-054).
          </Alert>
        )}

        {error && (
          <Alert variant="danger" title="Dispatch Error">
            {error}
          </Alert>
        )}

        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <label htmlFor="customer-reply-message" className="font-semibold text-slate-700">
              Customer Message (Dispatched directly to user):
            </label>
            <span className="text-2xs text-slate-400 font-mono">{message.length} chars</span>
          </div>
          <textarea
            id="customer-reply-message"
            rows={6}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            disabled={!canAct || isSubmitting}
            placeholder="Type your response to the customer..."
            className="w-full rounded-md border border-slate-300 p-2.5 text-xs text-slate-800 focus:outline-none focus:ring-1 focus:ring-brand-500 leading-relaxed font-sans"
          />
        </div>

        <div className="space-y-1.5">
          <label htmlFor="internal-note" className="font-medium text-slate-600 block">
            Internal Audit Note (Optional - visible only to support team):
          </label>
          <textarea
            id="internal-note"
            rows={2}
            value={internalNote}
            onChange={(e) => setInternalNote(e.target.value)}
            disabled={!canAct || isSubmitting}
            placeholder="e.g. Verified account history, advised customer regarding seat limit adjustments."
            className="w-full rounded-md border border-slate-300 p-2.5 text-xs text-slate-800 focus:outline-none focus:ring-1 focus:ring-slate-400 bg-slate-50"
          />
        </div>
      </div>
    </Modal>
  );
}
