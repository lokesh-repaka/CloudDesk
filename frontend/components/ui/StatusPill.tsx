import React from "react";

export type KnownStatus =
  | "new"
  | "in_progress"
  | "waiting_on_customer"
  | "waiting_on_approval"
  | "escalated"
  | "resolved"
  | "closed"
  | "low"
  | "medium"
  | "high"
  | "critical"
  | "pending"
  | "approved"
  | "rejected"
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "online"
  | "offline";

export interface StatusPillProps {
  status: string;
  label?: string;
  dot?: boolean;
  size?: "sm" | "md";
  className?: string;
}

interface StatusStyle {
  container: string;
  dot: string;
  defaultLabel: string;
}

const statusConfig: Record<string, StatusStyle> = {
  // Ticket / Workflow
  new: {
    container: "bg-sky-50 text-sky-700 border-sky-200",
    dot: "bg-sky-500",
    defaultLabel: "New",
  },
  in_progress: {
    container: "bg-blue-50 text-blue-700 border-blue-200",
    dot: "bg-blue-500",
    defaultLabel: "In Progress",
  },
  running: {
    container: "bg-blue-50 text-blue-700 border-blue-200",
    dot: "bg-blue-500 animate-pulse",
    defaultLabel: "Running",
  },
  queued: {
    container: "bg-slate-100 text-slate-700 border-slate-200",
    dot: "bg-slate-400",
    defaultLabel: "Queued",
  },
  waiting_on_customer: {
    container: "bg-amber-50 text-amber-800 border-amber-200",
    dot: "bg-amber-500",
    defaultLabel: "Waiting on Customer",
  },
  waiting_on_approval: {
    container: "bg-amber-50 text-amber-800 border-amber-300 font-semibold",
    dot: "bg-amber-500 animate-pulse",
    defaultLabel: "Waiting on Approval",
  },
  pending: {
    container: "bg-amber-50 text-amber-800 border-amber-300",
    dot: "bg-amber-500",
    defaultLabel: "Pending Approval",
  },
  approved: {
    container: "bg-emerald-50 text-emerald-700 border-emerald-200",
    dot: "bg-emerald-500",
    defaultLabel: "Approved",
  },
  resolved: {
    container: "bg-emerald-50 text-emerald-700 border-emerald-200",
    dot: "bg-emerald-500",
    defaultLabel: "Resolved",
  },
  completed: {
    container: "bg-emerald-50 text-emerald-700 border-emerald-200",
    dot: "bg-emerald-500",
    defaultLabel: "Completed",
  },
  escalated: {
    container: "bg-purple-50 text-purple-700 border-purple-200 font-medium",
    dot: "bg-purple-500",
    defaultLabel: "Escalated",
  },
  rejected: {
    container: "bg-rose-50 text-rose-700 border-rose-200",
    dot: "bg-rose-500",
    defaultLabel: "Rejected",
  },
  closed: {
    container: "bg-slate-100 text-slate-600 border-slate-200",
    dot: "bg-slate-400",
    defaultLabel: "Closed",
  },
  failed: {
    container: "bg-rose-50 text-rose-700 border-rose-200",
    dot: "bg-rose-500",
    defaultLabel: "Failed",
  },

  // Severity levels
  low: {
    container: "bg-slate-100 text-slate-700 border-slate-200",
    dot: "bg-slate-500",
    defaultLabel: "Low",
  },
  medium: {
    container: "bg-sky-50 text-sky-700 border-sky-200",
    dot: "bg-sky-500",
    defaultLabel: "Medium",
  },
  high: {
    container: "bg-amber-50 text-amber-800 border-amber-200",
    dot: "bg-amber-500",
    defaultLabel: "High",
  },
  critical: {
    container: "bg-rose-50 text-rose-700 border-rose-300 font-semibold",
    dot: "bg-rose-600",
    defaultLabel: "Critical",
  },

  // Connectivity
  online: {
    container: "bg-emerald-50 text-emerald-700 border-emerald-200",
    dot: "bg-emerald-500",
    defaultLabel: "Online",
  },
  offline: {
    container: "bg-rose-50 text-rose-700 border-rose-200",
    dot: "bg-rose-500",
    defaultLabel: "Offline",
  },
};

export function StatusPill({
  status,
  label,
  dot = true,
  size = "md",
  className = "",
}: StatusPillProps) {
  const normalizedKey = status.toLowerCase().replace(/[\s-]+/g, "_");
  const config = statusConfig[normalizedKey] || {
    container: "bg-slate-100 text-slate-700 border-slate-200",
    dot: "bg-slate-400",
    defaultLabel: status.replace(/_/g, " "),
  };

  const displayLabel = label ?? config.defaultLabel;
  const sizeClasses =
    size === "sm"
      ? "px-1.5 py-0.5 text-3xs gap-1"
      : "px-2.5 py-0.5 text-xs gap-1.5";

  return (
    <span
      className={`inline-flex items-center font-medium border rounded-full whitespace-nowrap ${
        config.container
      } ${sizeClasses} ${className}`}
      data-status={normalizedKey}
    >
      {dot && (
        <span
          className={`h-1.5 w-1.5 rounded-full flex-shrink-0 ${config.dot}`}
          aria-hidden="true"
        />
      )}
      <span>{displayLabel}</span>
    </span>
  );
}

