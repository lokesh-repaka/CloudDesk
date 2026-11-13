import React from "react";
import { InboxIcon } from "../layout/Icons";

export interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  className = "",
}: EmptyStateProps) {
  return (
    <div
      className={`flex flex-col items-center justify-center text-center p-8 sm:p-12 rounded-2xl border-2 border-dashed border-[#182c34] bg-[#0c181d] ${className}`}
    >
      <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[#122228] text-[#00d2b4] mb-3 border border-[#1b343f]">
        {icon || <InboxIcon size={24} />}
      </div>
      <h3 className="text-sm font-semibold text-white">{title}</h3>
      {description && (
        <p className="mt-1 text-xs text-slate-500 max-w-sm">{description}</p>
      )}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}
