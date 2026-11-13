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
    "bg-[#00d2b4] text-[#060c0e] font-bold hover:bg-[#2dd4bf] active:bg-[#00bfa3] border-transparent shadow-glow focus-visible:ring-[#00d2b4]",
  secondary:
    "bg-[#122228] text-slate-200 hover:bg-[#182e37] active:bg-[#1d3742] border-[#1f3742] shadow-xs focus-visible:ring-slate-400",
  outline:
    "bg-transparent text-slate-300 hover:bg-[#122228] border-[#1f3742] focus-visible:ring-slate-400",
  danger:
    "bg-rose-600 text-white hover:bg-rose-500 active:bg-rose-700 border-transparent shadow-xs focus-visible:ring-rose-500",
  ghost:
    "bg-transparent text-[#7e9aa6] hover:bg-[#122228] hover:text-white border-transparent focus-visible:ring-slate-400",
};

const sizeStyles: Record<ButtonSize, string> = {
  xs: "px-2 py-1 text-2xs gap-1 rounded",
  sm: "px-2.5 py-1.5 text-xs gap-1.5 rounded-lg",
  md: "px-3.5 py-2 text-sm gap-2 rounded-lg",
  lg: "px-4 py-2.5 text-base gap-2.5 rounded-xl",
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
          <span className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-t-transparent mr-1.5" />
        ) : (
          leftIcon && <span className="flex-shrink-0">{leftIcon}</span>
        )}
        <span>{children}</span>
        {!isLoading && rightIcon && <span className="flex-shrink-0">{rightIcon}</span>}
      </button>
    );
  }
);

Button.displayName = "Button";
