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
    container: "bg-sky-50 border-sky-200 text-sky-900",
    title: "text-sky-900",
    body: "text-sky-800",
    icon: "text-sky-500",
  },
  success: {
    container: "bg-emerald-50 border-emerald-200 text-emerald-900",
    title: "text-emerald-900",
    body: "text-emerald-800",
    icon: "text-emerald-500",
  },
  warning: {
    container: "bg-amber-50 border-amber-200 text-amber-900",
    title: "text-amber-900",
    body: "text-amber-800",
    icon: "text-amber-500",
  },
  danger: {
    container: "bg-rose-50 border-rose-200 text-rose-900",
    title: "text-rose-900",
    body: "text-rose-800",
    icon: "text-rose-500",
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
      className={`rounded-lg border p-3.5 flex items-start gap-3 ${styles.container} ${className}`}
      {...props}
    >
      <div className="flex-shrink-0 mt-0.5">{renderIcon()}</div>
      <div className="flex-1 text-xs">
        {title && <h5 className={`font-semibold mb-0.5 ${styles.title}`}>{title}</h5>}
        <div className={styles.body}>{children}</div>
      </div>
      {onClose && (
        <button
          type="button"
          onClick={onClose}
          className="text-slate-400 hover:text-slate-600 p-0.5 rounded focus:outline-none"
          aria-label="Dismiss alert"
        >
          <XCircleIcon size={16} />
        </button>
      )}
    </div>
  );
}

