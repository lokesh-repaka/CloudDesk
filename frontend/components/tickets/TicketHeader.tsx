"use client";

import React from "react";
import Link from "next/link";
import { TicketDetail } from "@/lib/types";
import { StatusPill } from "@/components/ui/StatusPill";
import { Badge, BadgeVariant } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";

interface TicketHeaderProps {
  ticket: TicketDetail;
  onRefresh?: () => void;
  isRefreshing?: boolean;
}

const severityBadgeMap: Record<string, BadgeVariant> = {
  critical: "danger",
  high: "warning",
  medium: "info",
  low: "neutral",
};

export function TicketHeader({ ticket, onRefresh, isRefreshing }: TicketHeaderProps) {
  const formattedCreated = new Date(ticket.created_at).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
  const formattedUpdated = new Date(ticket.updated_at).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });

  return (
    <div className="bg-white border border-slate-200 rounded-lg p-5 mb-6 shadow-xs">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-100 pb-4 mb-4">
        <div className="flex items-center space-x-3">
          <Link
            href="/tickets"
            className="inline-flex items-center text-sm font-medium text-slate-500 hover:text-slate-800 transition-colors"
          >
            <svg
              className="w-4 h-4 mr-1 text-slate-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
            </svg>
            Tickets
          </Link>
          <span className="text-slate-300">/</span>
          <span className="font-mono text-xs font-semibold text-slate-900 bg-slate-100 px-2.5 py-1 rounded">
            {ticket.id}
          </span>
          <StatusPill status={ticket.status} />
        </div>

        {onRefresh && (
          <Button
            variant="secondary"
            size="sm"
            onClick={onRefresh}
            isLoading={isRefreshing}
            leftIcon={
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                />
              </svg>
            }
          >
            Refresh
          </Button>
        )}
      </div>

      <div className="space-y-3">
        <h1 className="text-xl sm:text-2xl font-bold text-slate-900 tracking-tight">
          {ticket.subject}
        </h1>

        <div className="flex flex-wrap items-center gap-2 pt-1">
          <Badge variant={severityBadgeMap[ticket.severity] || "default"}>
            Severity: {ticket.severity}
          </Badge>
          <Badge variant="info">Category: {ticket.category}</Badge>
          <Badge variant="neutral">Channel: {ticket.channel}</Badge>
          {ticket.customer_plan && (
            <Badge variant="brand">Plan: {ticket.customer_plan}</Badge>
          )}
          {ticket.assigned_to ? (
            <Badge variant="default">Assigned: {ticket.assigned_to}</Badge>
          ) : (
            <Badge variant="neutral">Unassigned</Badge>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-x-6 gap-y-1 text-xs text-slate-500 pt-2 border-t border-slate-100">
          <span>Created: {formattedCreated}</span>
          <span>Last Updated: {formattedUpdated}</span>
          {ticket.customer_email && (
            <span>
              Customer:{" "}
              <span className="font-medium text-slate-700">
                {ticket.customer_name ? `${ticket.customer_name} (${ticket.customer_email})` : ticket.customer_email}
              </span>
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
