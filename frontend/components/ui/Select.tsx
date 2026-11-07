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
  ({ label, options, error, helperText, id, disabled, className = "", ...props }, ref) => {
    const selectId = id || (label ? label.toLowerCase().replace(/\s+/g, "-") : undefined);

    return (
      <div className="w-full space-y-1">
        {label && (
          <label htmlFor={selectId} className="block text-xs font-medium text-slate-700">
            {label}
          </label>
        )}
        <div className="relative rounded-md">
          <select
            ref={ref}
            id={selectId}
            disabled={disabled}
            className={`block w-full appearance-none rounded-md border text-xs text-slate-900 bg-white pl-3 pr-8 py-2 transition-colors focus:outline-none focus:ring-2 disabled:bg-slate-50 disabled:text-slate-500 disabled:cursor-not-allowed cursor-pointer ${
              error
                ? "border-rose-300 focus:border-rose-500 focus:ring-rose-200"
                : "border-slate-300 focus:border-brand-500 focus:ring-brand-100"
            } ${className}`}
            {...props}
          >
            {options.map((opt) => (
              <option key={opt.value} value={opt.value} disabled={opt.disabled}>
                {opt.label}
              </option>
            ))}
          </select>
          <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-2.5 text-slate-400">
            <ChevronDownIcon size={14} />
          </div>
        </div>
        {error ? (
          <p className="text-2xs text-rose-600 mt-1">{error}</p>
        ) : helperText ? (
          <p className="text-2xs text-slate-500 mt-1">{helperText}</p>
        ) : null}
      </div>
    );
  }
);

Select.displayName = "Select";

