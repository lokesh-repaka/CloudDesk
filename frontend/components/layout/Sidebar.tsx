"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { NAV_SECTIONS } from "./nav";
import { NavItems } from "./NavItems";
import { ChevronLeftIcon, ChevronRightIcon, BotIcon, XIcon, ShieldIcon } from "./Icons";
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
          className="fixed inset-0 z-40 bg-black/60 backdrop-blur-xs lg:hidden"
          onClick={onCloseMobile}
          aria-hidden="true"
        />
      )}

      {/* Sidebar Container */}
      <aside
        className={`fixed top-0 bottom-0 left-0 z-50 flex flex-col bg-[#050a0c] border-r border-[#112026] transition-all duration-200 ease-in-out ${
          collapsed ? "w-16" : "w-64"
        } ${
          isOpenMobile ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
        }`}
        aria-label="Application sidebar"
      >
        {/* Brand Header */}
        <div className="flex h-16 items-center justify-between px-4 border-b border-[#112026] bg-[#050a0c]">
          <Link
            href="/dashboard"
            className="flex items-center gap-2.5 overflow-hidden focus:outline-none focus-visible:ring-2 focus-visible:ring-[#00d2b4] rounded"
          >
            <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-[#00d2b4] text-[#050a0c] flex-shrink-0 font-bold shadow-glow">
              <BotIcon size={20} className="text-[#050a0c]" />
            </div>
            {!collapsed && (
              <div className="flex flex-col min-w-0">
                <span className="text-base font-extrabold tracking-tight text-white truncate">
                  CloudDesk
                </span>
                <span className="text-3xs font-semibold text-[#00d2b4] tracking-widest uppercase">
                  Support AI
                </span>
              </div>
            )}
          </Link>

          {/* Close on mobile */}
          <button
            type="button"
            onClick={onCloseMobile}
            className="lg:hidden p-1.5 text-slate-400 hover:text-white hover:bg-[#112026] rounded-md focus:outline-none"
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
                <h3 className="px-3 text-3xs font-bold uppercase tracking-wider text-[#4d6a77]">
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

          {/* Bottom Card (Reference Style) */}
          {!collapsed && (
            <div className="pt-4">
              <div className="p-3.5 rounded-xl bg-[#0b171c] border border-[#162d36] text-xs">
                <div className="flex items-center gap-2 text-[#00d2b4] font-semibold mb-1">
                  <ShieldIcon size={14} />
                  <span>AI Guardrails Active</span>
                </div>
                <p className="text-3xs text-[#7e9aa6] leading-relaxed">
                  Prompt-injection firewall & deterministic policy engine.
                </p>
                <Link
                  href="/agents"
                  className="mt-2.5 inline-flex items-center text-3xs font-bold text-[#00d2b4] hover:underline"
                >
                  View LangGraph Swarm →
                </Link>
              </div>
            </div>
          )}
        </div>

        {/* Collapse toggle (Desktop only) */}
        <div className="hidden lg:flex items-center justify-between border-t border-[#112026] p-3 bg-[#050a0c]">
          {!collapsed && (
            <span className="text-xs text-[#5a7683] font-medium">Collapse navigation</span>
          )}
          <button
            type="button"
            onClick={onToggleCollapse}
            className={`p-1.5 rounded-lg text-[#7d97a3] hover:text-white hover:bg-[#112026] transition-colors focus:outline-none focus:ring-2 focus:ring-[#00d2b4] ${
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
