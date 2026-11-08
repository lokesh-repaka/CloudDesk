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
      <CardHeader className="px-5 py-4 border-b border-[#162d36] mb-0 bg-[#0c181d]">
        <div className="flex items-center justify-between w-full">
          <CardTitle className="text-sm font-extrabold text-white flex items-center gap-2">
            <span>Conversation</span>
            <span className="text-3xs font-semibold text-[#00d2b4] bg-[#0f2a32] px-2 py-0.5 rounded-full border border-[#164a52]">
              {messages.length} {messages.length === 1 ? "message" : "messages"}
            </span>
          </CardTitle>
          <span className="font-mono text-3xs text-[#7e9aa6]">ID: #{ticketId}</span>
        </div>
      </CardHeader>

      {/* Messages stream */}
      <div className="p-4 sm:p-5 space-y-4 overflow-y-auto max-h-[560px] flex-1 bg-[#091216]">
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
                className={`p-4 rounded-xl border text-sm transition-all ${
                  isSystem
                    ? "bg-[#0c181d] border-[#162d36] text-[#7e9aa6]"
                    : isAgent
                    ? "bg-[#0d2a2f] border-[#164a52] text-white"
                    : "bg-[#101e24] border-[#1a3541] text-white shadow-card"
                }`}
              >
                <div className="flex items-center justify-between gap-2 mb-2 pb-1.5 border-b border-[#162d36]">
                  <div className="flex items-center gap-2">
                    {getAuthorBadge(msg.author_role)}
                    <span className="font-semibold text-xs text-white">
                      {msg.author_id || (msg.author_role === "customer" ? "Customer" : "Agent")}
                    </span>
                  </div>
                  <time className="text-3xs text-[#7e9aa6] font-mono">
                    {new Date(msg.created_at).toLocaleTimeString(undefined, {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </time>
                </div>
                <div className="whitespace-pre-wrap leading-relaxed break-words font-sans text-slate-200 text-xs">
                  {msg.body}
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Composer Section */}
      <div className="p-4 sm:p-5 border-t border-[#162d36] bg-[#0c181d]">
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
          <div className="flex items-center justify-between text-3xs text-[#7e9aa6]">
            <label htmlFor="message-composer" className="font-bold text-white uppercase tracking-wider">
              Composer
            </label>
            <span>{draft.length} characters</span>
          </div>

          <textarea
            id="message-composer"
            rows={3}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            disabled={!canAct || isSending}
            placeholder={
              canAct
                ? "Draft reply to customer or internal note..."
                : "Replies disabled in viewer read-only mode."
            }
            className="w-full p-3 rounded-xl border text-xs text-white bg-[#0d1a1f] border-[#182c34] placeholder-[#5a7683] transition-colors focus:outline-none focus:ring-2 focus:ring-[#00d2b4]/30 focus:border-[#00d2b4] disabled:bg-[#070e11] disabled:text-[#4b636f] resize-none"
          />

          <div className="flex items-center justify-between pt-1">
            <span className="text-3xs text-[#5a7683]">
              Dispatches via customer notification channel
            </span>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              disabled={!draft.trim() || !canAct || isSending}
              isLoading={isSending}
            >
              Send Reply
            </Button>
          </div>
        </form>
      </div>
    </Card>
  );
}
