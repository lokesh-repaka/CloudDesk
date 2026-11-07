import React from "react";

export type ButtonVariant = "primary" | "secondary" | "danger" | "ghost" | "outline";
export type ButtonSize = "xs" | "sm" | "md" | "lg";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  isLoading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

const variantStyles: Record<ButtonVariant, string> = {
  primary:
    "bg-brand-600 text-white hover:bg-brand-700 active:bg-brand-800 border-transparent shadow-xs focus-visible:ring-brand-500",
  secondary:
    "bg-white text-slate-700 hover:bg-slate-50 active:bg-slate-100 border-slate-300 shadow-xs focus-visible:ring-slate-400",
  outline:
    "bg-transparent text-slate-700 hover:bg-slate-100 border-slate-300 focus-visible:ring-slate-400",
  danger:
    "bg-rose-600 text-white hover:bg-rose-700 active:bg-rose-800 border-transparent shadow-xs focus-visible:ring-rose-500",
  ghost:
    "bg-transparent text-slate-600 hover:bg-slate-100 hover:text-slate-900 border-transparent focus-visible:ring-slate-400",
};

const sizeStyles: Record<ButtonSize, string> = {
  xs: "px-2 py-1 text-2xs gap-1 rounded",
  sm: "px-2.5 py-1.5 text-xs gap-1.5 rounded-md",
  md: "px-3.5 py-2 text-sm gap-2 rounded-md",
  lg: "px-4 py-2.5 text-base gap-2.5 rounded-lg",
};

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      children,
      variant = "primary",
      size = "md",
      isLoading = false,
      leftIcon,
      rightIcon,
      disabled = false,
      className = "",
      type = "button",
      ...props
    },
    ref
  ) => {
    const isDisabled = disabled || isLoading;

    return (
      <button
        ref={ref}
        type={type}
        disabled={isDisabled}
        className={`inline-flex items-center justify-center font-medium border transition-colors outline-none focus-visible:ring-2 focus-visible:ring-offset-1 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer ${
          variantStyles[variant]
        } ${sizeStyles[size]} ${className}`}
        {...props}
      >
        {isLoading ? (
          <span
            className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent mr-2"
            aria-hidden="true"
          />
        ) : (
          leftIcon && <span className="flex-shrink-0" aria-hidden="true">{leftIcon}</span>
        )}
        <span>{children}</span>
        {!isLoading && rightIcon && (
          <span className="flex-shrink-0" aria-hidden="true">{rightIcon}</span>
        )}
      </button>
    );
  }
);

Button.displayName = "Button";

