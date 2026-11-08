"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { AppShell } from "@/components/layout";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import { StatusPill } from "@/components/ui/StatusPill";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import {
  TicketIcon,
  UsersIcon,
  ShieldIcon,
  BotIcon,
  RefreshCwIcon,
  ArrowRightIcon,
  CheckCircleIcon,
  BookOpenIcon,
  FilterIcon,
} from "@/components/layout/Icons";
import {
  ApprovalRequestResponse,
  EscalationResponse,
  TicketSummary,
} from "@/lib/types";

export default function DashboardPage() {
  const { user, role } = useAuth();
  const [ticketCount, setTicketCount] = useState<number>(13);
  const [approvalCount, setApprovalCount] = useState<number>(1);
  const [escalationCount, setEscalationCount] = useState<number>(4);
  const [resolvedCount, setResolvedCount] = useState<number>(2);
  const [recentTickets, setRecentTickets] = useState<TicketSummary[]>([]);
  const [pendingApprovals, setPendingApprovals] = useState<ApprovalRequestResponse[]>([]);
  const [escalations, setEscalations] = useState<EscalationResponse[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchMetrics = useCallback(async () => {
    setLoading(true);
    try {
      const [ticketsRes, approvalsRes, escalationsRes] = await Promise.allSettled([
        api.tickets.list(),
        api.approvals.list(),
        api.escalations.list(),
      ]);

      if (ticketsRes.status === "fulfilled") {
        const items = ticketsRes.value.items;
        setTicketCount(ticketsRes.value.total ?? items.length);
        setRecentTickets(items.slice(0, 5));
        setResolvedCount(items.filter((t) => t.status === "resolved").length);
      }
      if (approvalsRes.status === "fulfilled") {
        setApprovalCount(approvalsRes.value.length);
        setPendingApprovals(approvalsRes.value.slice(0, 3));
      }
      if (escalationsRes.status === "fulfilled") {
        setEscalationCount(escalationsRes.value.length);
        setEscalations(escalationsRes.value.slice(0, 3));
      }
    } catch {
      // Keep demo fallback counts
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchMetrics();
  }, [fetchMetrics]);

  return (
    <AppShell pageTitle="Overview" userRole={role}>
      <div className="space-y-6">
        {/* Top Header / Greeting Bar */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <div className="flex items-center gap-2.5">
              <h2 className="text-xl sm:text-2xl font-extrabold text-white tracking-tight">
                Support Overview
              </h2>
              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-3xs font-bold bg-[#0d2a2f] text-[#2dd4bf] border border-[#164a52] uppercase tracking-wider">
                {role} Mode
              </span>
            </div>
            <p className="text-xs text-[#7e9aa6] mt-0.5">
              Autonomous customer resolution platform with LangGraph specialist swarm & human-in-the-loop governance.
            </p>
          </div>

          <div className="flex items-center gap-2.5">
            <Button
              variant="secondary"
              size="sm"
              onClick={fetchMetrics}
              isLoading={loading}
              leftIcon={<RefreshCwIcon size={14} />}
            >
              Refresh
            </Button>
            <Link href="/tickets">
              <Button variant="primary" size="sm" rightIcon={<ArrowRightIcon size={12} />}>
                View All Tickets
              </Button>
            </Link>
          </div>
        </div>

        {/* Top 3 Metric Cards — Talkvia Dark Theme Style */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Card 1: Ticket Today / Queue (Cyan Accent) */}
          <Link href="/tickets" className="block group">
            <div className="rounded-2xl p-5 bg-[#0b181d] border border-[#142d36] hover:border-[#1d4350] transition-all shadow-card cursor-pointer">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 rounded-xl bg-[#0f2a32] text-[#00d2b4] flex items-center justify-center font-bold shadow-glow">
                    <TicketIcon size={20} />
                  </div>
                  <div>
                    <span className="text-xs font-semibold text-[#8ba4b0] block">Ticket Today</span>
                    <span className="text-2xs text-[#52707d]">Total Active Queue</span>
                  </div>
                </div>
                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-3xs font-semibold bg-[#102d35] text-[#2dd4bf] border border-[#194551]">
                  +25% ↗
                </span>
              </div>

              <div className="mt-4 flex items-baseline justify-between">
                <span className="text-3xl font-extrabold text-[#00d2b4] tracking-tight">
                  {ticketCount}
                </span>
                <span className="text-3xs text-[#52707d] font-medium">In Last Month</span>
              </div>
            </div>
          </Link>

          {/* Card 2: Ticket Resolved (Emerald Accent) */}
          <div className="rounded-2xl p-5 bg-[#0a1a15] border border-[#133529] hover:border-[#1c4b3a] transition-all shadow-card">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="h-10 w-10 rounded-xl bg-[#0f3025] text-[#10b981] flex items-center justify-center font-bold shadow-glow-emerald">
                  <CheckCircleIcon size={20} />
                </div>
                <div>
                  <span className="text-xs font-semibold text-[#8ba4b0] block">Ticket Resolved</span>
                  <span className="text-2xs text-[#52707d]">Closed & Addressed</span>
                </div>
              </div>
              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-3xs font-semibold bg-[#113527] text-[#34d399] border border-[#1a513c]">
                +25% ↗
              </span>
            </div>

            <div className="mt-4 flex items-baseline justify-between">
              <span className="text-3xl font-extrabold text-[#10b981] tracking-tight">
                {resolvedCount > 0 ? resolvedCount : 2}
              </span>
              <span className="text-3xs text-[#52707d] font-medium">In Last Month</span>
            </div>
          </div>

          {/* Card 3: Ticket Pending / Approvals (Gold / Olive Accent) */}
          <Link href="/tickets?status=waiting_on_approval" className="block group">
            <div className="rounded-2xl p-5 bg-[#17190d] border border-[#2e3115] hover:border-[#444a1e] transition-all shadow-card cursor-pointer">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 rounded-xl bg-[#2b2b11] text-[#facc15] flex items-center justify-center font-bold shadow-glow-amber">
                    <ShieldIcon size={20} />
                  </div>
                  <div>
                    <span className="text-xs font-semibold text-[#8ba4b0] block">Ticket Pending</span>
                    <span className="text-2xs text-[#52707d]">Awaiting Confirmation</span>
                  </div>
                </div>
                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-3xs font-semibold bg-[#2a2b10] text-[#facc15] border border-[#444618]">
                  +25% ↗
                </span>
              </div>

              <div className="mt-4 flex items-baseline justify-between">
                <span className="text-3xl font-extrabold text-[#facc15] tracking-tight">
                  {approvalCount}
                </span>
                <span className="text-3xs text-[#52707d] font-medium">Human Review Gated</span>
              </div>
            </div>
          </Link>
        </div>

        {/* Main Content Grid: Left Table & Category (8 cols) + Right Agents & Approvals (4 cols) */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* Left Column (8 cols): Recent Tickets Table + Category Breakdown */}
          <div className="lg:col-span-8 space-y-6">
            {/* Recent Tickets Card */}
            <div className="rounded-2xl bg-[#0c181d] border border-[#162d36] p-5 shadow-card">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="text-sm font-extrabold text-white tracking-tight">
                    Recent Tickets
                  </h3>
                  <p className="text-3xs text-[#7e9aa6] mt-0.5">
                    Total {ticketCount} active cases in triage
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <Link href="/tickets">
                    <Button variant="secondary" size="xs" leftIcon={<FilterIcon size={12} />}>
                      Filter
                    </Button>
                  </Link>
                  <Link href="/tickets">
                    <Button variant="ghost" size="xs" rightIcon={<ArrowRightIcon size={12} />}>
                      See More
                    </Button>
                  </Link>
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-xs">
                  <thead>
                    <tr className="border-b border-[#162d36] text-3xs font-bold uppercase tracking-wider text-[#6e8a96]">
                      <th className="py-2.5 px-3">Ticket ID</th>
                      <th className="py-2.5 px-3">Customer</th>
                      <th className="py-2.5 px-3">Issue Type</th>
                      <th className="py-2.5 px-3">Severity</th>
                      <th className="py-2.5 px-3">Status</th>
                      <th className="py-2.5 px-3 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#14232a]">
                    {recentTickets.length > 0 ? (
                      recentTickets.map((t) => (
                        <tr key={t.id} className="hover:bg-[#112026] transition-colors">
                          <td className="py-3 px-3 font-mono font-bold text-[#00d2b4]">
                            <Link href={`/tickets/${t.id}`} className="hover:underline">
                              #{t.id}
                            </Link>
                          </td>
                          <td className="py-3 px-3">
                            <div className="flex items-center gap-2">
                              <div className="h-6 w-6 rounded-full bg-[#142830] text-[#00d2b4] font-bold text-3xs flex items-center justify-center border border-[#1f3e4b] flex-shrink-0">
                                {(t.customer_name || t.customer_id || "C").charAt(0).toUpperCase()}
                              </div>
                              <span className="font-semibold text-white truncate max-w-[130px]">
                                {t.customer_name || t.customer_id}
                              </span>
                            </div>
                          </td>
                          <td className="py-3 px-3">
                            <Badge variant="neutral" size="sm">
                              {t.category.replace(/_/g, " ")}
                            </Badge>
                          </td>
                          <td className="py-3 px-3">
                            <StatusPill status={t.severity} size="sm" />
                          </td>
                          <td className="py-3 px-3">
                            <StatusPill status={t.status} size="sm" />
                          </td>
                          <td className="py-3 px-3 text-right">
                            <Link href={`/tickets/${t.id}`}>
                              <Button variant="secondary" size="xs" rightIcon={<ArrowRightIcon size={10} />}>
                                Inspect
                              </Button>
                            </Link>
                          </td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={6} className="py-6 text-center text-xs text-[#7e9aa6]">
                          Loading tickets queue...
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Bottom Row: Category Breakdown & Customer Feedback */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {/* Category Breakdown (Order-related issues style from image) */}
              <div className="rounded-2xl bg-[#0c181d] border border-[#162d36] p-5 shadow-card">
                <h4 className="text-xs font-bold text-white mb-3 tracking-tight">
                  Triage Category Breakdown
                </h4>
                <div className="space-y-2.5 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="text-[#8ba4b0] flex items-center gap-2">
                      <span className="h-2 w-2 rounded-full bg-[#00d2b4]" />
                      SAML Login & SSO Issues
                    </span>
                    <span className="font-mono font-bold text-white">40%</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-[#8ba4b0] flex items-center gap-2">
                      <span className="h-2 w-2 rounded-full bg-[#facc15]" />
                      Billing & Refund Requests
                    </span>
                    <span className="font-mono font-bold text-white">25%</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-[#8ba4b0] flex items-center gap-2">
                      <span className="h-2 w-2 rounded-full bg-[#38bdf8]" />
                      API 429 & Rate Limits
                    </span>
                    <span className="font-mono font-bold text-white">15%</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-[#8ba4b0] flex items-center gap-2">
                      <span className="h-2 w-2 rounded-full bg-[#c084fc]" />
                      Security & GDPR Article 17
                    </span>
                    <span className="font-mono font-bold text-white">10%</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-[#8ba4b0] flex items-center gap-2">
                      <span className="h-2 w-2 rounded-full bg-[#94a3b8]" />
                      Workspace Permissions & Quota
                    </span>
                    <span className="font-mono font-bold text-white">10%</span>
                  </div>
                </div>
              </div>

              {/* Customer Feedback / AI Reasoning */}
              <div className="rounded-2xl bg-[#0c181d] border border-[#162d36] p-5 shadow-card flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <h4 className="text-xs font-bold text-white tracking-tight">
                      Customer Sentiment
                    </h4>
                    <span className="inline-flex items-center gap-1 text-2xs font-bold text-[#facc15] bg-[#2a2b10] px-2 py-0.5 rounded-full border border-[#444618]">
                      ★ 4.9 / 5
                    </span>
                  </div>
                  <div className="mt-3 p-3 rounded-xl bg-[#0f2127] border border-[#193641] text-xs space-y-1">
                    <div className="flex items-center gap-2">
                      <div className="h-5 w-5 rounded-full bg-[#00d2b4] text-[#050a0c] font-bold text-3xs flex items-center justify-center">
                        A
                      </div>
                      <span className="font-bold text-white text-xs">Acme Corporation</span>
                      <span className="text-3xs text-[#00d2b4] font-mono">#CD-1001</span>
                    </div>
                    <p className="text-3xs text-[#8fa7b3] leading-relaxed pt-1">
                      &quot;The automated SAML guide resolved our outage in 2 minutes. Excellent accuracy.&quot;
                    </p>
                  </div>
                </div>

                <div className="pt-3 border-t border-[#162d36] flex items-center justify-between">
                  <span className="text-3xs text-[#7e9aa6]">Resolution Rate: 92%</span>
                  <Link href="/tickets/CD-1001">
                    <span className="text-3xs font-bold text-[#00d2b4] hover:underline">
                      Inspect Trace →
                    </span>
                  </Link>
                </div>
              </div>
            </div>
          </div>

          {/* Right Column (4 cols): Live AI Specialists + Human Approvals */}
          <div className="lg:col-span-4 space-y-6">
            {/* Live Specialists Card (Matching Live Chat style from image) */}
            <div className="rounded-2xl bg-[#0c181d] border border-[#162d36] p-5 shadow-card">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <h4 className="text-xs font-bold text-white tracking-tight">
                    AI Specialist Swarm
                  </h4>
                  <span className="text-3xs text-[#7e9aa6]">6 Agents Active</span>
                </div>
                <Link href="/agents">
                  <Button variant="ghost" size="xs" rightIcon={<ArrowRightIcon size={12} />}>
                    See Swarm
                  </Button>
                </Link>
              </div>

              {/* Active Specialist Preview */}
              <div className="p-3.5 rounded-xl bg-[#0e2229] border border-[#183944] mb-4">
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center gap-2">
                    <div className="h-7 w-7 rounded-xl bg-[#00d2b4] text-[#050a0c] font-bold flex items-center justify-center text-xs shadow-glow">
                      <BotIcon size={16} />
                    </div>
                    <div>
                      <div className="text-xs font-bold text-white">Supervisor Agent</div>
                      <div className="text-3xs text-[#00d2b4]">LangGraph Orchestrator</div>
                    </div>
                  </div>
                  <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-3xs font-semibold bg-[#0e2c21] text-[#34d399] border border-[#154d38]">
                    <span className="h-1.5 w-1.5 rounded-full bg-[#10b981] animate-ping" />
                    Online
                  </span>
                </div>
                <p className="text-3xs text-[#8fa7b3] leading-relaxed">
                  Triage, category understanding, deterministic severity assessment, and wrap-up summaries.
                </p>
              </div>

              {/* Specialists Avatar Row */}
              <div className="flex items-center justify-between pt-1">
                <span className="text-3xs font-semibold text-[#6e8a96] uppercase tracking-wider">
                  Swarm Roster:
                </span>
                <div className="flex items-center -space-x-1.5">
                  <div className="h-7 w-7 rounded-full bg-[#0d2a2f] text-[#2dd4bf] flex items-center justify-center font-bold text-3xs border border-[#164a52]" title="Supervisor">
                    S
                  </div>
                  <div className="h-7 w-7 rounded-full bg-[#132d38] text-[#38bdf8] flex items-center justify-center font-bold text-3xs border border-[#1b4b5e]" title="CustomerContext">
                    C
                  </div>
                  <div className="h-7 w-7 rounded-full bg-[#192b3a] text-[#818cf8] flex items-center justify-center font-bold text-3xs border border-[#243e54]" title="KnowledgeRetrieval">
                    K
                  </div>
                  <div className="h-7 w-7 rounded-full bg-[#27153b] text-[#c084fc] flex items-center justify-center font-bold text-3xs border border-[#4a2472]" title="Troubleshooting">
                    T
                  </div>
                  <div className="h-7 w-7 rounded-full bg-[#2d1b15] text-[#fb923c] flex items-center justify-center font-bold text-3xs border border-[#4d2a1f]" title="Resolution">
                    R
                  </div>
                  <div className="h-7 w-7 rounded-full bg-[#33141a] text-[#fb7185] flex items-center justify-center font-bold text-3xs border border-[#591e2b]" title="Escalation">
                    E
                  </div>
                </div>
              </div>
            </div>

            {/* Human Approvals Gated */}
            <div className="rounded-2xl bg-[#0c181d] border border-[#162d36] p-5 shadow-card">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <ShieldIcon size={16} className="text-[#facc15]" />
                  <h4 className="text-xs font-bold text-white tracking-tight">
                    Human Approvals
                  </h4>
                </div>
                <Badge variant="warning" size="sm">
                  {pendingApprovals.length > 0 ? `${pendingApprovals.length} Pending` : "1 Pending"}
                </Badge>
              </div>

              <div className="space-y-2.5">
                {pendingApprovals.length > 0 ? (
                  pendingApprovals.map((appr) => (
                    <div
                      key={appr.id}
                      className="p-3 rounded-xl bg-[#141d18] border border-[#1d3d2c] hover:border-[#27573d] transition-all"
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-mono text-xs font-bold text-[#00d2b4]">
                          {appr.ticket_id}
                        </span>
                        <StatusPill status="waiting_on_approval" size="sm" />
                      </div>
                      <p className="text-xs text-white font-medium truncate">
                        {appr.action_name}: {appr.action_payload?.amount ? `$${appr.action_payload.amount}` : "Review"}
                      </p>
                      <div className="mt-2 flex justify-end">
                        <Link href={`/tickets/${appr.ticket_id}`}>
                          <Button variant="primary" size="xs" rightIcon={<ArrowRightIcon size={10} />}>
                            Decide
                          </Button>
                        </Link>
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="p-3 rounded-xl bg-[#17190d] border border-[#2e3115]">
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-mono text-xs font-bold text-[#00d2b4]">
                        CD-1002
                      </span>
                      <StatusPill status="waiting_on_approval" size="sm" />
                    </div>
                    <p className="text-xs text-white font-medium">Refund approval: $49.00</p>
                    <p className="text-3xs text-[#7e9aa6]">TechStart Inc · Duplicate charge</p>
                    <div className="mt-2.5 flex justify-end">
                      <Link href="/tickets/CD-1002">
                        <Button variant="primary" size="xs" rightIcon={<ArrowRightIcon size={10} />}>
                          Decide
                        </Button>
                      </Link>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Policy Escalations */}
            <div className="rounded-2xl bg-[#0c181d] border border-[#162d36] p-5 shadow-card">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <UsersIcon size={16} className="text-[#c084fc]" />
                  <h4 className="text-xs font-bold text-white tracking-tight">
                    Policy Escalations
                  </h4>
                </div>
                <Badge variant="neutral" size="sm">Rule Bound</Badge>
              </div>

              <div className="space-y-2">
                <div className="p-2.5 rounded-xl bg-[#181124] border border-[#301e4a]">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs font-bold text-[#c084fc]">CD-1005</span>
                    <Badge variant="neutral" size="sm">legal_compliance</Badge>
                  </div>
                  <p className="text-3xs text-[#b8a4cc] mt-1">GDPR Article 17 Data Erasure Request</p>
                </div>

                <div className="p-2.5 rounded-xl bg-[#181124] border border-[#301e4a]">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs font-bold text-[#c084fc]">CD-1011</span>
                    <Badge variant="neutral" size="sm">billing_disputes</Badge>
                  </div>
                  <p className="text-3xs text-[#b8a4cc] mt-1">Payment dispute threatening legal escalation</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
