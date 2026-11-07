"use client";

import React from "react";
import { Breadcrumbs } from "./Breadcrumbs";
import { MenuIcon, LogOutIcon } from "./Icons";
import { Role } from "@/lib/types";

export interface HeaderUser {
  name: string;
  email: string;
  role: Role;
}

export interface HeaderProps {
  pageTitle?: string;
  user?: HeaderUser;
  backendStatus?: "online" | "offline" | "checking";
  onToggleSidebar?: () => void;
  onLogout?: () => void;
}

export function Header({
  pageTitle,
  user = { name: "Support Agent", email: "agent@clouddesk.dev", role: "agent" },
  backendStatus = "online",
  onToggleSidebar,
  onLogout,
}: HeaderProps) {
  const roleBadgeStyles: Record<Role, string> = {
    viewer: "bg-slate-100 text-slate-700 border-slate-300",
    agent: "bg-brand-50 text-brand-700 border-brand-200",
    admin: "bg-purple-50 text-purple-700 border-purple-200",
  };

  return (
    <header className="sticky top-0 z-30 flex h-16 w-full items-center justify-between border-b border-slate-200 bg-white px-4 sm:px-6">
      <div className="flex items-center gap-3 min-w-0">
        <button
          type="button"
          onClick={onToggleSidebar}
          className="lg:hidden p-2 rounded-md text-slate-500 hover:text-slate-700 hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-brand-500"
          aria-label="Toggle navigation menu"
        >
          <MenuIcon size={20} />
        </button>

        <div className="flex flex-col min-w-0">
          <Breadcrumbs />
          {pageTitle && (
            <h1 className="text-base font-semibold text-slate-900 truncate tracking-tight">
              {pageTitle}
            </h1>
          )}
        </div>
      </div>

      <div className="flex items-center gap-4">
        {/* Backend Connectivity Status */}
        <div
          className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border border-slate-200 bg-slate-50"
          title={`Backend status: ${backendStatus}`}
        >
          <span
            className={`h-2 w-2 rounded-full ${
              backendStatus === "online"
                ? "bg-emerald-500"
                : backendStatus === "checking"
                ? "bg-amber-400 animate-pulse"
                : "bg-rose-500"
            }`}
          />
          <span className="text-slate-600">
            {backendStatus === "online"
              ? "API Online"
              : backendStatus === "checking"
              ? "Connecting..."
              : "API Offline"}
          </span>
        </div>

        {/* User Identity & Role Badge */}
        <div className="flex items-center gap-3">
          <div className="hidden md:flex flex-col text-right">
            <span className="text-xs font-semibold text-slate-900 leading-none">
              {user.name}
            </span>
            <span className="text-2xs text-slate-500 truncate max-w-[140px] leading-tight">
              {user.email}
            </span>
          </div>

          <span
            className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border uppercase tracking-wider ${
              roleBadgeStyles[user.role] ?? roleBadgeStyles.viewer
            }`}
          >
            {user.role}
          </span>

          {onLogout && (
            <button
              type="button"
              onClick={onLogout}
              className="p-1.5 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded focus:outline-none focus:ring-2 focus:ring-brand-500"
              title="Sign out"
              aria-label="Sign out"
            >
              <LogOutIcon size={16} />
            </button>
          )}
        </div>
      </div>
    </header>
  );
}

