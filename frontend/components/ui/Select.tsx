import React from "react";
import { ChevronDownIcon } from "../layout/Icons";

export interface SelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

export interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  options: SelectOption[];
  error?: string;
  helperText?: string;
}

export const Select = React.forwardRef<HTMLSelectElement, SelectProps>(
  (
    {
      label,
      options,
      error,
      helperText,
      id,
      disabled,
      className = "",
      ...props
    },
    ref
  ) => {
    const selectId = id || (label ? label.toLowerCase().replace(/\s+/g, "-") : undefined);

    return (
      <div className="w-full space-y-1">
        {label && (
          <label htmlFor={selectId} className="block text-xs font-medium text-[#8fa7b3]">
            {label}
          </label>
        )}
        <div className="relative rounded-lg">
          <select
            ref={ref}
            id={selectId}
            disabled={disabled}
            className={`block w-full appearance-none rounded-lg border text-xs text-white bg-[#0d1a1f] pl-3 pr-8 py-2 transition-colors focus:outline-none focus:ring-2 disabled:bg-[#081115] disabled:text-[#4b636f] disabled:cursor-not-allowed cursor-pointer ${
              error
                ? "border-rose-500 focus:border-rose-400 focus:ring-rose-500/20"
                : "border-[#182c34] focus:border-[#00d2b4] focus:ring-[#00d2b4]/20"
            } ${className}`}
            {...props}
          >
            {options.map((opt) => (
              <option key={opt.value} value={opt.value} disabled={opt.disabled} className="bg-[#0e181c] text-white">
                {opt.label}
              </option>
            ))}
          </select>
          <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-2.5 text-[#5a7683]">
            <ChevronDownIcon size={14} />
          </div>
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

Select.displayName = "Select";
