"use client";

import React, { useState, useRef, useEffect } from "react";
import { Breadcrumbs } from "./Breadcrumbs";
import { MenuIcon, LogOutIcon, UsersIcon, ShieldIcon, CheckCircleIcon } from "./Icons";
import { Role } from "@/lib/types";
import { useAuth, DEMO_USERS_MAP } from "@/lib/auth";

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
  onSwitchPersona?: (role: Role) => void;
}

export function Header({
  pageTitle,
  user = { name: "Support Agent", email: "agent@clouddesk.dev", role: "agent" },
  backendStatus = "online",
  onToggleSidebar,
  onLogout,
  onSwitchPersona,
}: HeaderProps) {
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const { loginWithDemo, role: currentRole } = useAuth();

  const handleSwitch = async (targetRole: Role) => {
    setDropdownOpen(false);
    if (onSwitchPersona) {
      onSwitchPersona(targetRole);
    } else {
      await loginWithDemo(targetRole);
    }
  };

  // Close dropdown on click outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setDropdownOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const roleBadgeStyles: Record<Role, string> = {
    viewer: "bg-slate-100 text-slate-700 border-slate-300",
    agent: "bg-brand-50 text-brand-700 border-brand-200",
    admin: "bg-purple-50 text-purple-700 border-purple-200",
  };

  const activeRole = user.role || currentRole || "agent";

  return (
    <header className="sticky top-0 z-30 flex h-16 w-full items-center justify-between border-b border-slate-200 bg-white px-4 sm:px-6 shadow-xs">
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

      <div className="flex items-center gap-3 sm:gap-4">
        {/* Backend Connectivity Status */}
        <div
          className="hidden sm:flex items-center gap-2 px-2.5 py-1 rounded-full text-xs font-medium border border-slate-200 bg-slate-50"
          title={`Backend status: ${backendStatus}`}
        >
          {backendStatus === "online" ? (
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
            </span>
          ) : (
            <span
              className={`h-2 w-2 rounded-full ${
                backendStatus === "checking" ? "bg-amber-400 animate-pulse" : "bg-rose-500"
              }`}
            />
          )}
          <span className="text-slate-600 text-xs">
            {backendStatus === "online"
              ? "API Online"
              : backendStatus === "checking"
              ? "Connecting..."
              : "API Offline"}
          </span>
        </div>

        {/* Demo Persona Switcher Dropdown */}
        <div className="relative" ref={dropdownRef}>
          <button
            type="button"
            onClick={() => setDropdownOpen(!dropdownOpen)}
            className="flex items-center gap-2 p-1.5 sm:px-3 sm:py-1.5 rounded-lg border border-slate-200 hover:border-slate-300 hover:bg-slate-50 transition-colors focus:outline-none focus:ring-2 focus:ring-brand-500"
            aria-expanded={dropdownOpen}
            aria-haspopup="true"
            title="Switch demo persona"
          >
            <div className="flex h-7 w-7 items-center justify-center rounded-full bg-slate-100 text-slate-700 font-semibold text-xs border border-slate-200 flex-shrink-0">
              {user.name.charAt(0)}
            </div>

            <div className="hidden md:flex flex-col text-left">
              <span className="text-xs font-semibold text-slate-900 leading-tight">
                {user.name}
              </span>
              <span className="text-3xs text-slate-500 font-normal leading-none capitalize">
                {activeRole} Role
              </span>
            </div>

            <span
              className={`inline-flex items-center px-1.5 py-0.5 rounded text-3xs font-medium border uppercase tracking-wider ${
                roleBadgeStyles[activeRole] ?? roleBadgeStyles.viewer
              }`}
            >
              {activeRole}
            </span>

            <svg
              className={`h-4 w-4 text-slate-400 transition-transform ${dropdownOpen ? "rotate-180" : ""}`}
              viewBox="0 0 20 20"
              fill="currentColor"
            >
              <path
                fillRule="evenodd"
                d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z"
                clipRule="evenodd"
              />
            </svg>
          </button>

          {/* Dropdown Menu */}
          {dropdownOpen && (
            <div className="absolute right-0 mt-2 w-72 rounded-lg bg-white border border-slate-200 shadow-card py-2 z-50 text-slate-900 animate-in fade-in-50 duration-100">
              <div className="px-3 pb-2 mb-1 border-b border-slate-100">
                <p className="text-2xs font-semibold uppercase tracking-wider text-slate-400">
                  Switch Demo Persona
                </p>
                <p className="text-3xs text-slate-500 mt-0.5">
                  Test role-based access control and execution privileges
                </p>
              </div>

              {/* Persona Options */}
              <div className="space-y-1 px-1">
                {/* Sam Agent */}
                <button
                  type="button"
                  onClick={() => handleSwitch("agent")}
                  className={`w-full text-left px-3 py-2 rounded-md flex items-center justify-between text-xs transition-colors ${
                    activeRole === "agent" ? "bg-brand-50 text-brand-900 font-medium" : "hover:bg-slate-50"
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <div className="h-6 w-6 rounded-full bg-brand-100 text-brand-700 flex items-center justify-center font-bold text-2xs">
                      S
                    </div>
                    <div>
                      <div className="font-semibold text-slate-900">Sam Agent</div>
                      <div className="text-3xs text-slate-500">Full workflow actions, replies, approvals</div>
                    </div>
                  </div>
                  {activeRole === "agent" && (
                    <CheckCircleIcon size={14} className="text-brand-600 flex-shrink-0" />
                  )}
                </button>

                {/* Alice Admin */}
                <button
                  type="button"
                  onClick={() => handleSwitch("admin")}
                  className={`w-full text-left px-3 py-2 rounded-md flex items-center justify-between text-xs transition-colors ${
                    activeRole === "admin" ? "bg-purple-50 text-purple-900 font-medium" : "hover:bg-slate-50"
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <div className="h-6 w-6 rounded-full bg-purple-100 text-purple-700 flex items-center justify-center font-bold text-2xs">
                      A
                    </div>
                    <div>
                      <div className="font-semibold text-slate-900">Alice Admin</div>
                      <div className="text-3xs text-slate-500">Agent access + KB reindexing & settings</div>
                    </div>
                  </div>
                  {activeRole === "admin" && (
                    <CheckCircleIcon size={14} className="text-purple-600 flex-shrink-0" />
                  )}
                </button>

                {/* Vic Viewer */}
                <button
                  type="button"
                  onClick={() => handleSwitch("viewer")}
                  className={`w-full text-left px-3 py-2 rounded-md flex items-center justify-between text-xs transition-colors ${
                    activeRole === "viewer" ? "bg-slate-100 text-slate-900 font-medium" : "hover:bg-slate-50"
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <div className="h-6 w-6 rounded-full bg-slate-200 text-slate-700 flex items-center justify-center font-bold text-2xs">
                      V
                    </div>
                    <div>
                      <div className="font-semibold text-slate-900">Vic Viewer</div>
                      <div className="text-3xs text-slate-500">Read-only auditing (action buttons disabled)</div>
                    </div>
                  </div>
                  {activeRole === "viewer" && (
                    <CheckCircleIcon size={14} className="text-slate-600 flex-shrink-0" />
                  )}
                </button>
              </div>

              {onLogout && (
                <div className="mt-2 pt-2 border-t border-slate-100 px-1">
                  <button
                    type="button"
                    onClick={() => {
                      setDropdownOpen(false);
                      onLogout();
                    }}
                    className="w-full text-left px-3 py-1.5 rounded-md flex items-center gap-2 text-xs text-rose-600 hover:bg-rose-50 transition-colors"
                  >
                    <LogOutIcon size={14} />
                    <span>Sign Out</span>
                  </button>
                </div>
              )}
            </div>
          )}
        </div>

        {onLogout && (
          <button
            type="button"
            onClick={onLogout}
            className="hidden sm:inline-flex p-2 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-md focus:outline-none focus:ring-2 focus:ring-brand-500"
            title="Sign out"
            aria-label="Sign out"
          >
            <LogOutIcon size={16} />
          </button>
        )}
      </div>
    </header>
  );
}
