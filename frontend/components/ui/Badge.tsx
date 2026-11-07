import React from "react";

export type BadgeVariant =
  | "default"
  | "brand"
  | "neutral"
  | "success"
  | "warning"
  | "danger"
  | "info";

export type BadgeSize = "sm" | "md";

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
  size?: BadgeSize;
  dot?: boolean;
}

const variantStyles: Record<BadgeVariant, { container: string; dot: string }> = {
  default: {
    container: "bg-slate-100 text-slate-700 border-slate-200",
    dot: "bg-slate-500",
  },
  neutral: {
    container: "bg-slate-100 text-slate-700 border-slate-200",
    dot: "bg-slate-500",
  },
  brand: {
    container: "bg-brand-50 text-brand-700 border-brand-200",
    dot: "bg-brand-600",
  },
  success: {
    container: "bg-emerald-50 text-emerald-700 border-emerald-200",
    dot: "bg-emerald-500",
  },
  warning: {
    container: "bg-amber-50 text-amber-800 border-amber-200",
    dot: "bg-amber-500",
  },
  danger: {
    container: "bg-rose-50 text-rose-700 border-rose-200",
    dot: "bg-rose-500",
  },
  info: {
    container: "bg-sky-50 text-sky-700 border-sky-200",
    dot: "bg-sky-500",
  },
};

const sizeStyles: Record<BadgeSize, string> = {
  sm: "px-1.5 py-0.5 text-2xs gap-1",
  md: "px-2 py-0.5 text-xs gap-1.5",
};

export function Badge({
  children,
  variant = "default",
  size = "md",
  dot = false,
  className = "",
  ...props
}: BadgeProps) {
  const styles = variantStyles[variant] || variantStyles.default;

  return (
    <span
      className={`inline-flex items-center font-medium border rounded-md whitespace-nowrap ${
        styles.container
      } ${sizeStyles[size]} ${className}`}
      {...props}
    >
      {dot && (
        <span
          className={`h-1.5 w-1.5 rounded-full flex-shrink-0 ${styles.dot}`}
          aria-hidden="true"
        />
      )}
      {children}
    </span>
  );
}

