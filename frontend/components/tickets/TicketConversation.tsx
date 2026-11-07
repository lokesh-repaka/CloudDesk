"use client";

import React, { useState } from "react";
import { TicketMessage } from "@/lib/types";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { Alert } from "@/components/ui/Alert";

interface TicketConversationProps {
  messages: TicketMessage[];
  ticketId: string;
  onSendMessage?: (body: string, isInternal?: boolean) => Promise<void>;
  canAct?: boolean;
}

export function TicketConversation({
  messages,
  ticketId,
  onSendMessage,
  canAct = true,
}: TicketConversationProps) {
  const [draft, setDraft] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!draft.trim() || !onSendMessage || !canAct) return;

    try {
      setIsSending(true);
      setSendError(null);
      await onSendMessage(draft.trim());
      setDraft("");
    } catch (err: unknown) {
      setSendError(err instanceof Error ? err.message : "Failed to dispatch reply");
    } finally {
      setIsSending(false);
    }
  };

  const getAuthorBadge = (role: string) => {
    switch (role) {
      case "customer":
        return <Badge variant="brand">Customer</Badge>;
      case "agent":
        return <Badge variant="success">Support Agent</Badge>;
      case "system":
        return <Badge variant="neutral">System</Badge>;
      default:
        return <Badge variant="default">{role}</Badge>;
    }
  };

  return (
    <Card padding="none" className="flex flex-col h-full overflow-hidden">
      <CardHeader className="px-5 py-4 border-b border-slate-200 mb-0">
        <div className="flex items-center justify-between w-full">
          <CardTitle className="text-base font-semibold text-slate-900 flex items-center gap-2">
            <span>Conversation</span>
            <span className="text-xs font-normal text-slate-500 bg-slate-100 px-2 py-0.5 rounded-full">
              {messages.length} {messages.length === 1 ? "message" : "messages"}
            </span>
          </CardTitle>
          <span className="font-mono text-2xs text-slate-400">ID: {ticketId}</span>
        </div>
      </CardHeader>

      {/* Messages stream */}
      <div className="p-4 sm:p-5 space-y-4 overflow-y-auto max-h-[560px] flex-1 bg-slate-50">
        {messages.length === 0 ? (
          <EmptyState
            title="No conversation messages yet"
            description="The ticket message history is currently empty."
          />
        ) : (
          messages.map((msg) => {
            const isSystem = msg.author_role === "system";
            const isAgent = msg.author_role === "agent";

            return (
              <div
                key={msg.id}
                className={`p-4 rounded-lg border text-sm transition-shadow ${
                  isSystem
                    ? "bg-slate-100 border-slate-200 text-slate-600"
                    : isAgent
                    ? "bg-blue-50/60 border-blue-200 text-slate-800"
                    : "bg-white border-slate-200 text-slate-800 shadow-xs"
                }`}
              >
                <div className="flex items-center justify-between gap-2 mb-2 pb-1.5 border-b border-slate-100">
                  <div className="flex items-center gap-2">
                    {getAuthorBadge(msg.author_role)}
                    <span className="font-medium text-xs text-slate-700">
                      {msg.author_id || (msg.author_role === "customer" ? "Customer" : "Agent")}
                    </span>
                  </div>
                  <time className="text-2xs text-slate-500 font-mono">
                    {new Date(msg.created_at).toLocaleTimeString(undefined, {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </time>
                </div>
                <div className="whitespace-pre-wrap leading-relaxed break-words font-sans text-slate-700">
                  {msg.body}
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Composer Section */}
      <div className="p-4 sm:p-5 border-t border-slate-200 bg-white">
        {!canAct && (
          <div className="mb-3">
            <Alert variant="warning" title="Read-Only Mode">
              Viewer role does not have permission to send replies or modify tickets.
            </Alert>
          </div>
        )}

        {sendError && (
          <div className="mb-3">
            <Alert variant="danger" title="Dispatch Error">
              {sendError}
            </Alert>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="flex items-center justify-between text-xs text-slate-500">
            <label htmlFor="message-composer" className="font-medium text-slate-700">
              Composer
            </label>
            <span>{draft.length} characters</span>
          </div>

          <textarea
            id="message-composer"
            rows={4}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            disabled={!canAct || isSending}
            placeholder={
              canAct
                ? "Type a response to the customer or leave an internal note..."
                : "Composer disabled for read-only viewer role."
            }
            className={`w-full rounded-md border text-sm p-3 focus:outline-none focus:ring-1 focus:ring-brand-500 ${
              canAct
                ? "border-slate-300 bg-white text-slate-900 placeholder:text-slate-400"
                : "border-slate-200 bg-slate-50 text-slate-400 cursor-not-allowed"
            }`}
          />

          <div className="flex items-center justify-between pt-1">
            <span className="text-2xs text-slate-500">
              Shift + Enter for new lines
            </span>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              disabled={!canAct || !draft.trim() || isSending}
              isLoading={isSending}
              leftIcon={
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
                  />
                </svg>
              }
            >
              Send Reply
            </Button>
          </div>
        </form>
      </div>
    </Card>
  );
}
