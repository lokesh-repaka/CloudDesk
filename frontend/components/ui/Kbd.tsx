import React from "react";

export interface KbdProps extends React.HTMLAttributes<HTMLElement> {
  size?: "sm" | "md";
}

export function Kbd({ children, size = "md", className = "", ...props }: KbdProps) {
  const sizeClasses = size === "sm" ? "px-1 text-3xs" : "px-1.5 py-0.5 text-2xs";

  return (
    <kbd
      className={`inline-flex items-center justify-center font-mono font-medium text-slate-600 bg-slate-100 border border-slate-300 rounded shadow-2xs ${sizeClasses} ${className}`}
      {...props}
    >
      {children}
    </kbd>
  );
}

