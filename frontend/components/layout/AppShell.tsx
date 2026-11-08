"use client";

import React, { useState } from "react";
import { Sidebar } from "./Sidebar";
import { Header, HeaderUser } from "./Header";
import { Role } from "@/lib/types";
import { useAuth } from "@/lib/auth";
import { AlertTriangleIcon } from "./Icons";

export interface AppShellProps {
  children: React.ReactNode;
  pageTitle?: string;
  userRole?: Role;
  backendStatus?: "online" | "offline" | "checking";
}

export function AppShell({
  children,
  pageTitle,
  userRole: propUserRole,
  backendStatus = "online",
}: AppShellProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  const { user, role: authRole, logout, loginWithDemo } = useAuth();

  const effectiveRole: Role = propUserRole || authRole || "agent";

  const currentUser: HeaderUser = {
    name: user?.full_name || (effectiveRole === "admin" ? "Alice Admin" : effectiveRole === "agent" ? "Sam Agent" : "Vic Viewer"),
    email: user?.email || `${effectiveRole}@clouddesk.demo`,
    role: effectiveRole,
  };

  const badgeCounts = {
    openTickets: 12,
    pendingApprovals: 3,
    escalations: 2,
  };

  return (
    <div className="min-h-screen bg-[#070d10] text-slate-100 flex">
      {/* Sidebar Navigation */}
      <Sidebar
        userRole={effectiveRole}
        collapsed={collapsed}
        onToggleCollapse={() => setCollapsed(!collapsed)}
        isOpenMobile={mobileOpen}
        onCloseMobile={() => setMobileOpen(false)}
        badgeCounts={badgeCounts}
      />

      {/* Main Content Area */}
      <div
        className={`flex-1 flex flex-col min-w-0 transition-all duration-200 ease-in-out bg-[#070d10] ${
          collapsed ? "lg:pl-16" : "lg:pl-64"
        }`}
      >
        {/* Top Header */}
        <Header
          pageTitle={pageTitle}
          user={currentUser}
          backendStatus={backendStatus}
          onToggleSidebar={() => setMobileOpen(true)}
          onLogout={logout}
          onSwitchPersona={loginWithDemo}
        />

        {/* Read-Only Viewer Alert Banner (AC-054) */}
        {effectiveRole === "viewer" && (
          <div className="bg-[#291f08] border-b border-[#59400e] px-4 py-2 text-xs text-amber-200 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <AlertTriangleIcon size={14} className="text-[#f59e0b] flex-shrink-0" />
              <span>
                <strong>Read-Only Mode (Viewer Role):</strong> Ticket workflow runs, customer replies, approval decisions, and escalations are disabled.
              </span>
            </div>
          </div>
        )}

        {/* Page Main Content */}
        <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-7xl w-full mx-auto space-y-6">
          {children}
        </main>
      </div>
    </div>
  );
}
