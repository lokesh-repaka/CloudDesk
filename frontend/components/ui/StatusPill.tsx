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
    container: "bg-[#0d2a2f] text-[#2dd4bf] border-[#164a52]",
    dot: "bg-[#2dd4bf]",
    defaultLabel: "New",
  },
  in_progress: {
    container: "bg-[#2f2b10] text-[#facc15] border-[#4d4414]",
    dot: "bg-[#facc15]",
    defaultLabel: "In Progress",
  },
  running: {
    container: "bg-[#0d2a2f] text-[#2dd4bf] border-[#164a52]",
    dot: "bg-[#2dd4bf] animate-pulse",
    defaultLabel: "Running",
  },
  queued: {
    container: "bg-[#132026] text-[#8ea8b4] border-[#1d323c]",
    dot: "bg-[#8ea8b4]",
    defaultLabel: "Queued",
  },
  waiting_on_customer: {
    container: "bg-[#2f2b10] text-[#facc15] border-[#4d4414]",
    dot: "bg-[#facc15]",
    defaultLabel: "Waiting on Customer",
  },
  waiting_on_approval: {
    container: "bg-[#342609] text-[#fbbf24] border-[#5e440e] font-semibold",
    dot: "bg-[#f59e0b] animate-pulse",
    defaultLabel: "Waiting on Approval",
  },
  pending: {
    container: "bg-[#342609] text-[#fbbf24] border-[#5e440e]",
    dot: "bg-[#f59e0b]",
    defaultLabel: "Pending Approval",
  },
  approved: {
    container: "bg-[#0e2c21] text-[#34d399] border-[#154d38]",
    dot: "bg-[#10b981]",
    defaultLabel: "Approved",
  },
  resolved: {
    container: "bg-[#0e2c21] text-[#34d399] border-[#154d38]",
    dot: "bg-[#10b981]",
    defaultLabel: "Resolved",
  },
  completed: {
    container: "bg-[#0e2c21] text-[#34d399] border-[#154d38]",
    dot: "bg-[#10b981]",
    defaultLabel: "Completed",
  },
  escalated: {
    container: "bg-[#27153b] text-[#c084fc] border-[#4a2472] font-medium",
    dot: "bg-[#a855f7]",
    defaultLabel: "Escalated",
  },
  rejected: {
    container: "bg-[#33141a] text-[#fb7185] border-[#591e2b]",
    dot: "bg-[#f43f5e]",
    defaultLabel: "Rejected",
  },
  closed: {
    container: "bg-[#132026] text-[#7e9aa6] border-[#1e343e]",
    dot: "bg-[#7e9aa6]",
    defaultLabel: "Closed",
  },
  failed: {
    container: "bg-[#33141a] text-[#fb7185] border-[#591e2b]",
    dot: "bg-[#f43f5e]",
    defaultLabel: "Failed",
  },

  // Severity levels
  low: {
    container: "bg-[#132026] text-[#7e9aa6] border-[#1e343e]",
    dot: "bg-[#7e9aa6]",
    defaultLabel: "Low",
  },
  medium: {
    container: "bg-[#0d2a2f] text-[#2dd4bf] border-[#164a52]",
    dot: "bg-[#2dd4bf]",
    defaultLabel: "Medium",
  },
  high: {
    container: "bg-[#342609] text-[#fb923c] border-[#5e440e]",
    dot: "bg-[#f97316]",
    defaultLabel: "High",
  },
  critical: {
    container: "bg-[#33141a] text-[#fb7185] border-[#591e2b] font-semibold",
    dot: "bg-[#f43f5e] animate-pulse",
    defaultLabel: "Critical",
  },

  // Agent / Connectivity
  online: {
    container: "bg-[#0e2c21] text-[#34d399] border-[#154d38]",
    dot: "bg-[#10b981]",
    defaultLabel: "Online",
  },
  offline: {
    container: "bg-[#33141a] text-[#fb7185] border-[#591e2b]",
    dot: "bg-[#f43f5e]",
    defaultLabel: "Offline",
  },
};

const defaultFallbackStyle: StatusStyle = {
  container: "bg-[#132026] text-[#8ea8b4] border-[#1d323c]",
  dot: "bg-[#8ea8b4]",
  defaultLabel: "Unknown",
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
    ...defaultFallbackStyle,
    defaultLabel: status.replace(/_/g, " "),
  };

  const displayLabel = label ?? config.defaultLabel;

  const sizeClasses =
    size === "sm" ? "px-2 py-0.5 text-3xs gap-1" : "px-2.5 py-1 text-xs gap-1.5";

  return (
    <span
      data-status={normalizedKey}
      className={`inline-flex items-center rounded-full font-medium border uppercase tracking-wider ${config.container} ${sizeClasses} ${className}`}
    >
      {dot && (
        <span
          className={`h-1.5 w-1.5 rounded-full flex-shrink-0 ${config.dot}`}
          aria-hidden="true"
        />
      )}
      <span className="capitalize">{displayLabel}</span>
    </span>
  );
}
