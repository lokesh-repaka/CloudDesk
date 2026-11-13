"use client";

import React, { useState, useRef, useEffect } from "react";
import { Breadcrumbs } from "./Breadcrumbs";
import { MenuIcon, LogOutIcon, CheckCircleIcon, SearchIcon } from "./Icons";
import { Role } from "@/lib/types";
import { useAuth } from "@/lib/auth";

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
    viewer: "bg-[#132026] text-[#8ea8b4] border-[#1d323c]",
    agent: "bg-[#0d2a2f] text-[#2dd4bf] border-[#164a52]",
    admin: "bg-[#27153b] text-[#c084fc] border-[#4a2472]",
  };

  const activeRole = user.role || currentRole || "agent";

  return (
    <header className="sticky top-0 z-30 flex h-16 w-full items-center justify-between border-b border-[#112026] bg-[#070d10] px-4 sm:px-6 shadow-xs">
      <div className="flex items-center gap-3 min-w-0">
        <button
          type="button"
          onClick={onToggleSidebar}
          className="lg:hidden p-2 rounded-xl text-[#7d97a3] hover:text-white hover:bg-[#112026] focus:outline-none focus:ring-2 focus:ring-[#00d2b4]"
          aria-label="Toggle navigation menu"
        >
          <MenuIcon size={20} />
        </button>

        <div className="flex flex-col min-w-0">
          <Breadcrumbs />
          {pageTitle && (
            <h1 className="text-base font-bold text-white truncate tracking-tight">
              {pageTitle}
            </h1>
          )}
        </div>
      </div>

      <div className="flex items-center gap-3 sm:gap-4">
        {/* Backend Connectivity Status */}
        <div
          className="hidden sm:flex items-center gap-2 px-2.5 py-1 rounded-full text-xs font-medium border border-[#162d36] bg-[#0a1519]"
          title={`Backend status: ${backendStatus}`}
        >
          {backendStatus === "online" ? (
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#10b981] opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-[#10b981]" />
            </span>
          ) : (
            <span
              className={`h-2 w-2 rounded-full ${
                backendStatus === "checking" ? "bg-amber-400 animate-pulse" : "bg-rose-500"
              }`}
            />
          )}
          <span className="text-[#8ea8b4] text-3xs font-medium">
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
            className="flex items-center gap-2.5 p-1.5 sm:px-3 sm:py-1.5 rounded-xl border border-[#182c34] bg-[#0d1a1f] hover:border-[#24424e] hover:bg-[#112229] transition-all focus:outline-none focus:ring-2 focus:ring-[#00d2b4]"
            aria-expanded={dropdownOpen}
            aria-haspopup="true"
            title="Switch demo persona"
          >
            <div className="flex h-7 w-7 items-center justify-center rounded-full bg-[#142830] text-[#00d2b4] font-bold text-xs border border-[#1f3e4b] flex-shrink-0">
              {user.name.charAt(0)}
            </div>

            <div className="hidden md:flex flex-col text-left">
              <span className="text-xs font-semibold text-white leading-tight">
                {user.name}
              </span>
              <span className="text-3xs text-[#7e9aa6] font-normal leading-none capitalize">
                {activeRole} Role
              </span>
            </div>

            <span
              className={`inline-flex items-center px-1.5 py-0.5 rounded text-3xs font-semibold border uppercase tracking-wider ${
                roleBadgeStyles[activeRole] ?? roleBadgeStyles.viewer
              }`}
            >
              {activeRole}
            </span>

            <svg
              className={`h-3.5 w-3.5 text-[#5a7683] transition-transform ${dropdownOpen ? "rotate-180" : ""}`}
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
            <div className="absolute right-0 mt-2 w-72 rounded-xl bg-[#0e1c22] border border-[#1e3845] shadow-card-hover py-2 z-50 text-white animate-in fade-in-50 duration-100">
              <div className="px-3 pb-2 mb-1 border-b border-[#182f3a]">
                <p className="text-2xs font-bold uppercase tracking-wider text-[#4d6a77]">
                  Switch Demo Persona
                </p>
                <p className="text-3xs text-[#7e9aa6] mt-0.5">
                  Test role-based access control and execution privileges
                </p>
              </div>

              {/* Persona Options */}
              <div className="space-y-1 px-1">
                {/* Sam Agent */}
                <button
                  type="button"
                  onClick={() => handleSwitch("agent")}
                  className={`w-full text-left px-3 py-2 rounded-lg flex items-center justify-between text-xs transition-colors ${
                    activeRole === "agent" ? "bg-[#142932] text-white font-medium" : "hover:bg-[#12232a]"
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <div className="h-6 w-6 rounded-full bg-[#0d2a2f] text-[#2dd4bf] flex items-center justify-center font-bold text-2xs border border-[#164a52]">
                      S
                    </div>
                    <div>
                      <div className="font-semibold text-white">Sam Agent</div>
                      <div className="text-3xs text-[#7e9aa6]">Full workflow actions, replies, approvals</div>
                    </div>
                  </div>
                  {activeRole === "agent" && (
                    <CheckCircleIcon size={14} className="text-[#00d2b4] flex-shrink-0" />
                  )}
                </button>

                {/* Alice Admin */}
                <button
                  type="button"
                  onClick={() => handleSwitch("admin")}
                  className={`w-full text-left px-3 py-2 rounded-lg flex items-center justify-between text-xs transition-colors ${
                    activeRole === "admin" ? "bg-[#20152d] text-white font-medium" : "hover:bg-[#12232a]"
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <div className="h-6 w-6 rounded-full bg-[#27153b] text-[#c084fc] flex items-center justify-center font-bold text-2xs border border-[#4a2472]">
                      A
                    </div>
                    <div>
                      <div className="font-semibold text-white">Alice Admin</div>
                      <div className="text-3xs text-[#7e9aa6]">Agent access + KB reindexing & settings</div>
                    </div>
                  </div>
                  {activeRole === "admin" && (
                    <CheckCircleIcon size={14} className="text-[#a855f7] flex-shrink-0" />
                  )}
                </button>

                {/* Vic Viewer */}
                <button
                  type="button"
                  onClick={() => handleSwitch("viewer")}
                  className={`w-full text-left px-3 py-2 rounded-lg flex items-center justify-between text-xs transition-colors ${
                    activeRole === "viewer" ? "bg-[#17252c] text-white font-medium" : "hover:bg-[#12232a]"
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <div className="h-6 w-6 rounded-full bg-[#132026] text-[#8ea8b4] flex items-center justify-center font-bold text-2xs border border-[#1d323c]">
                      V
                    </div>
                    <div>
                      <div className="font-semibold text-white">Vic Viewer</div>
                      <div className="text-3xs text-[#7e9aa6]">Read-only auditing (action buttons disabled)</div>
                    </div>
                  </div>
                  {activeRole === "viewer" && (
                    <CheckCircleIcon size={14} className="text-[#8ea8b4] flex-shrink-0" />
                  )}
                </button>
              </div>

              {onLogout && (
                <div className="mt-2 pt-2 border-t border-[#182f3a] px-1">
                  <button
                    type="button"
                    onClick={() => {
                      setDropdownOpen(false);
                      onLogout();
                    }}
                    className="w-full text-left px-3 py-1.5 rounded-lg flex items-center gap-2 text-xs text-rose-400 hover:bg-[#201015] transition-colors"
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
            className="hidden sm:inline-flex p-2 text-[#7d97a3] hover:text-white hover:bg-[#112026] rounded-xl focus:outline-none focus:ring-2 focus:ring-[#00d2b4]"
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
