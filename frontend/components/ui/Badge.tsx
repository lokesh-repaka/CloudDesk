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
    container: "bg-[#132026] text-[#8ea8b4] border-[#1d323c]",
    dot: "bg-[#8ea8b4]",
  },
  neutral: {
    container: "bg-[#132026] text-[#8ea8b4] border-[#1d323c]",
    dot: "bg-[#8ea8b4]",
  },
  brand: {
    container: "bg-[#0d2a2f] text-[#2dd4bf] border-[#164a52]",
    dot: "bg-[#00d2b4]",
  },
  success: {
    container: "bg-[#0e2c21] text-[#34d399] border-[#154d38]",
    dot: "bg-[#10b981]",
  },
  warning: {
    container: "bg-[#342609] text-[#fbbf24] border-[#5e440e]",
    dot: "bg-[#f59e0b]",
  },
  danger: {
    container: "bg-[#33141a] text-[#fb7185] border-[#591e2b]",
    dot: "bg-[#f43f5e]",
  },
  info: {
    container: "bg-[#0d2a2f] text-[#2dd4bf] border-[#164a52]",
    dot: "bg-[#00d2b4]",
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
      className={`inline-flex items-center font-medium border rounded-md uppercase tracking-wider ${styles.container} ${sizeStyles[size]} ${className}`}
      {...props}
    >
      {dot && (
        <span
          className={`h-1.5 w-1.5 rounded-full flex-shrink-0 ${styles.dot}`}
          aria-hidden="true"
        />
      )}
      <span>{children}</span>
    </span>
  );
}
