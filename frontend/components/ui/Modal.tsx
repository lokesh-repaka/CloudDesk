"use client";

import React, { useEffect } from "react";
import { XIcon } from "../layout/Icons";

export interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  description?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
  size?: "sm" | "md" | "lg" | "xl";
}

export function Modal({
  isOpen,
  onClose,
  title,
  description,
  children,
  footer,
  size = "md",
}: ModalProps) {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };

    if (isOpen) {
      document.body.style.overflow = "hidden";
      window.addEventListener("keydown", handleKeyDown);
    }

    return () => {
      document.body.style.overflow = "unset";
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const sizeClasses = {
    sm: "max-w-md",
    md: "max-w-lg",
    lg: "max-w-2xl",
    xl: "max-w-4xl",
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-none"
      role="dialog"
      aria-modal="true"
    >
      {/* Backdrop Click */}
      <div className="fixed inset-0" onClick={onClose} aria-hidden="true" />

      {/* Dialog Box */}
      <div
        className={`relative z-10 w-full ${sizeClasses[size]} bg-white rounded-lg border border-slate-200 shadow-lg overflow-hidden flex flex-col max-h-[90vh]`}
      >
        {/* Header */}
        <div className="flex items-start justify-between p-4 sm:p-5 border-b border-slate-200 bg-slate-50/50">
          <div>
            {title && (
              <h3 className="text-sm sm:text-base font-semibold text-slate-900 leading-tight">
                {title}
              </h3>
            )}
            {description && (
              <p className="text-xs text-slate-500 mt-1">{description}</p>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 p-1 rounded-md hover:bg-slate-100 transition-colors focus:outline-none focus:ring-2 focus:ring-brand-500"
            aria-label="Close dialog"
          >
            <XIcon size={18} />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-4 sm:p-5 overflow-y-auto space-y-4 flex-1 text-xs text-slate-700">
          {children}
        </div>

        {/* Footer */}
        {footer && (
          <div className="flex items-center justify-end gap-2 p-3 sm:p-4 border-t border-slate-200 bg-slate-50">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}

