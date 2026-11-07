"use client";

import React, { useState } from "react";
import { Sidebar } from "./Sidebar";
import { Header, HeaderUser } from "./Header";
import { Role } from "@/lib/types";

export interface AppShellProps {
  children: React.ReactNode;
  pageTitle?: string;
  userRole?: Role;
  backendStatus?: "online" | "offline" | "checking";
}

export function AppShell({
  children,
  pageTitle,
  userRole = "agent",
  backendStatus = "online",
}: AppShellProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  const currentUser: HeaderUser = {
    name: "Alex Rivera",
    email: "alex.rivera@clouddesk.dev",
    role: userRole,
  };

  const badgeCounts = {
    openTickets: 12,
    pendingApprovals: 3,
    escalations: 2,
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 flex">
      {/* Sidebar Navigation */}
      <Sidebar
        userRole={userRole}
        collapsed={collapsed}
        onToggleCollapse={() => setCollapsed(!collapsed)}
        isOpenMobile={mobileOpen}
        onCloseMobile={() => setMobileOpen(false)}
        badgeCounts={badgeCounts}
      />

      {/* Main Content Area */}
      <div
        className={`flex-1 flex flex-col min-w-0 transition-all duration-200 ease-in-out ${
          collapsed ? "lg:pl-16" : "lg:pl-64"
        }`}
      >
        {/* Top Header */}
        <Header
          pageTitle={pageTitle}
          user={currentUser}
          backendStatus={backendStatus}
          onToggleSidebar={() => setMobileOpen(true)}
          onLogout={() => {
            if (typeof window !== "undefined") {
              window.location.href = "/login";
            }
          }}
        />

        {/* Page Main Content */}
        <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-7xl w-full mx-auto">
          {children}
        </main>
      </div>
    </div>
  );
}

