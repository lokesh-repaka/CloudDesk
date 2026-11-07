import React from "react";

export interface TabItem {
  id: string;
  label: string;
  count?: number;
  disabled?: boolean;
}

export interface TabsProps {
  tabs: TabItem[];
  activeTab: string;
  onChange: (tabId: string) => void;
  className?: string;
}

export function Tabs({ tabs, activeTab, onChange, className = "" }: TabsProps) {
  return (
    <div className={`border-b border-slate-200 ${className}`}>
      <nav className="-mb-px flex space-x-6 overflow-x-auto" aria-label="Tabs" role="tablist">
        {tabs.map((tab) => {
          const isActive = tab.id === activeTab;

          return (
            <button
              key={tab.id}
              role="tab"
              aria-selected={isActive}
              aria-controls={`tabpanel-${tab.id}`}
              id={`tab-${tab.id}`}
              disabled={tab.disabled}
              onClick={() => onChange(tab.id)}
              className={`whitespace-nowrap py-3 px-1 border-b-2 text-xs font-medium transition-colors flex items-center gap-2 outline-none focus-visible:ring-2 focus-visible:ring-brand-500 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer ${
                isActive
                  ? "border-brand-600 text-brand-600 font-semibold"
                  : "border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300"
              }`}
            >
              <span>{tab.label}</span>
              {typeof tab.count === "number" && (
                <span
                  className={`px-1.5 py-0.2 rounded-full text-3xs font-semibold ${
                    isActive
                      ? "bg-brand-100 text-brand-700"
                      : "bg-slate-100 text-slate-600"
                  }`}
                >
                  {tab.count}
                </span>
              )}
            </button>
          );
        })}
      </nav>
    </div>
  );
}

