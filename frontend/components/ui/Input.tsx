import React from "react";

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  helperText?: string;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  (
    {
      label,
      error,
      helperText,
      leftIcon,
      rightIcon,
      id,
      disabled,
      className = "",
      ...props
    },
    ref
  ) => {
    const inputId = id || (label ? label.toLowerCase().replace(/\s+/g, "-") : undefined);

    return (
      <div className="w-full space-y-1">
        {label && (
          <label htmlFor={inputId} className="block text-xs font-medium text-[#8fa7b3]">
            {label}
          </label>
        )}
        <div className="relative rounded-lg">
          {leftIcon && (
            <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-[#5a7683]">
              {leftIcon}
            </div>
          )}
          <input
            ref={ref}
            id={inputId}
            disabled={disabled}
            className={`block w-full rounded-lg border text-xs text-white bg-[#0d1a1f] placeholder-[#5a7683] transition-colors focus:outline-none focus:ring-2 disabled:bg-[#081115] disabled:text-[#4b636f] disabled:cursor-not-allowed ${
              leftIcon ? "pl-9" : "pl-3"
            } ${rightIcon ? "pr-9" : "pr-3"} py-2 ${
              error
                ? "border-rose-500 focus:border-rose-400 focus:ring-rose-500/20"
                : "border-[#182c34] focus:border-[#00d2b4] focus:ring-[#00d2b4]/20"
            } ${className}`}
            {...props}
          />
          {rightIcon && (
            <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3 text-[#5a7683]">
              {rightIcon}
            </div>
          )}
        </div>
        {error ? (
          <p className="text-2xs text-rose-400 mt-1">{error}</p>
        ) : helperText ? (
          <p className="text-2xs text-[#7e9aa6] mt-1">{helperText}</p>
        ) : null}
      </div>
    );
  }
);

Input.displayName = "Input";
