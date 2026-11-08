import React from "react";
import { AlertTriangleIcon, CheckCircleIcon, XCircleIcon, InfoIcon } from "../layout/Icons";

export type AlertVariant = "info" | "success" | "warning" | "danger";

export interface AlertProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: AlertVariant;
  title?: string;
  onClose?: () => void;
}

const variantStyles: Record<
  AlertVariant,
  { container: string; title: string; body: string; icon: string }
> = {
  info: {
    container: "bg-[#092227] border-[#134954] text-cyan-200",
    title: "text-cyan-300",
    body: "text-cyan-200/90",
    icon: "text-[#00d2b4]",
  },
  success: {
    container: "bg-[#09251c] border-[#13513a] text-emerald-200",
    title: "text-emerald-300",
    body: "text-emerald-200/90",
    icon: "text-[#10b981]",
  },
  warning: {
    container: "bg-[#291f08] border-[#59400e] text-amber-200",
    title: "text-amber-300",
    body: "text-amber-200/90",
    icon: "text-[#f59e0b]",
  },
  danger: {
    container: "bg-[#290e15] border-[#5e1927] text-rose-200",
    title: "text-rose-300",
    body: "text-rose-200/90",
    icon: "text-[#f43f5e]",
  },
};

export function Alert({
  children,
  variant = "info",
  title,
  onClose,
  className = "",
  ...props
}: AlertProps) {
  const styles = variantStyles[variant] || variantStyles.info;

  const renderIcon = () => {
    switch (variant) {
      case "success":
        return <CheckCircleIcon size={18} className={styles.icon} />;
      case "warning":
        return <AlertTriangleIcon size={18} className={styles.icon} />;
      case "danger":
        return <XCircleIcon size={18} className={styles.icon} />;
      case "info":
      default:
        return <InfoIcon size={18} className={styles.icon} />;
    }
  };

  return (
    <div
      role="alert"
      className={`rounded-xl border p-4 shadow-sm flex items-start gap-3 ${styles.container} ${className}`}
      {...props}
    >
      <div className="flex-shrink-0 mt-0.5">{renderIcon()}</div>
      <div className="flex-1 min-w-0">
        {title && <h5 className={`text-xs font-bold leading-tight ${styles.title}`}>{title}</h5>}
        <div className={`text-xs mt-1 leading-relaxed ${styles.body}`}>{children}</div>
      </div>
      {onClose && (
        <button
          type="button"
          onClick={onClose}
          className="text-slate-400 hover:text-white p-1 rounded transition-colors"
          aria-label="Dismiss alert"
        >
          <XCircleIcon size={16} />
        </button>
      )}
    </div>
  );
}
