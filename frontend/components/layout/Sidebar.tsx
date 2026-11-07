"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { NAV_SECTIONS } from "./nav";
import { NavItems } from "./NavItems";
import { ChevronLeftIcon, ChevronRightIcon, BotIcon, XIcon } from "./Icons";
import { Role } from "@/lib/types";

export interface SidebarProps {
  userRole?: Role;
  collapsed?: boolean;
  onToggleCollapse?: () => void;
  isOpenMobile?: boolean;
  onCloseMobile?: () => void;
  badgeCounts?: Record<string, number>;
}

export function Sidebar({
  userRole = "agent",
  collapsed = false,
  onToggleCollapse,
  isOpenMobile = false,
  onCloseMobile,
  badgeCounts = {},
}: SidebarProps) {
  const pathname = usePathname() || "/dashboard";

  return (
    <>
      {/* Mobile Backdrop */}
      {isOpenMobile && (
        <div
          className="fixed inset-0 z-40 bg-slate-900/50 backdrop-blur-none lg:hidden"
          onClick={onCloseMobile}
          aria-hidden="true"
        />
      )}

      {/* Sidebar Container */}
      <aside
        className={`fixed top-0 bottom-0 left-0 z-50 flex flex-col bg-white border-r border-slate-200 transition-all duration-200 ease-in-out ${
          collapsed ? "w-16" : "w-64"
        } ${
          isOpenMobile ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
        }`}
        aria-label="Application sidebar"
      >
        {/* Brand Header */}
        <div className="flex h-16 items-center justify-between px-4 border-b border-slate-200 bg-white">
          <Link
            href="/dashboard"
            className="flex items-center gap-2.5 overflow-hidden focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 rounded"
          >
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-white flex-shrink-0 font-bold shadow-sm">
              <BotIcon size={20} className="text-white" />
            </div>
            {!collapsed && (
              <div className="flex flex-col min-w-0">
                <span className="text-sm font-bold tracking-tight text-slate-900 truncate">
                  CloudDesk
                </span>
                <span className="text-2xs font-medium text-slate-500 tracking-wider uppercase">
                  Support AI
                </span>
              </div>
            )}
          </Link>

          {/* Close on mobile */}
          <button
            type="button"
            onClick={onCloseMobile}
            className="lg:hidden p-1.5 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded focus:outline-none"
            aria-label="Close navigation"
          >
            <XIcon size={18} />
          </button>
        </div>

        {/* Navigation Sections */}
        <div className="flex-1 overflow-y-auto px-3 py-4 space-y-6">
          {NAV_SECTIONS.map((section) => (
            <div key={section.title} className="space-y-1">
              {!collapsed && (
                <h3 className="px-3 text-3xs font-semibold uppercase tracking-wider text-slate-400">
                  {section.title}
                </h3>
              )}
              <NavItems
                items={section.items}
                currentPath={pathname}
                userRole={userRole}
                collapsed={collapsed}
                badgeCounts={badgeCounts}
                onItemClick={onCloseMobile}
              />
            </div>
          ))}
        </div>

        {/* Collapse toggle (Desktop only) */}
        <div className="hidden lg:flex items-center justify-between border-t border-slate-200 p-3 bg-slate-50">
          {!collapsed && (
            <span className="text-xs text-slate-500 font-medium">Collapse navigation</span>
          )}
          <button
            type="button"
            onClick={onToggleCollapse}
            className={`p-1.5 rounded text-slate-500 hover:text-slate-800 hover:bg-slate-200 transition-colors focus:outline-none focus:ring-2 focus:ring-brand-500 ${
              collapsed ? "mx-auto" : ""
            }`}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {collapsed ? <ChevronRightIcon size={16} /> : <ChevronLeftIcon size={16} />}
          </button>
        </div>
      </aside>
    </>
  );
}

