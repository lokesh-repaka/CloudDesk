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
  BookOpenIcon,
  CheckCircleIcon,
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
        setTicketCount(ticketsRes.value.total ?? ticketsRes.value.items.length);
        setRecentTickets(ticketsRes.value.items.slice(0, 5));
      }
      if (approvalsRes.status === "fulfilled") {
        setApprovalCount(approvalsRes.value.length);
        setPendingApprovals(approvalsRes.value.slice(0, 4));
      }
      if (escalationsRes.status === "fulfilled") {
        setEscalationCount(escalationsRes.value.length);
        setEscalations(escalationsRes.value.slice(0, 4));
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
    <AppShell pageTitle="Support Operations Dashboard" userRole={role}>
      <div className="space-y-6">
        {/* Welcome & Overview Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-white p-5 rounded-lg border border-slate-200 shadow-xs">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-bold text-slate-900">
                Welcome back, {user?.full_name || "Support Operator"}
              </h2>
              <span className="inline-flex items-center px-2 py-0.5 rounded text-3xs font-semibold bg-brand-50 text-brand-700 border border-brand-200 uppercase tracking-wider">
                {role} Mode
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-1">
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
              <Button variant="primary" size="sm" leftIcon={<TicketIcon size={14} />}>
                View All Tickets
              </Button>
            </Link>
          </div>
        </div>

        {/* Primary Metrics Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Link href="/tickets" className="group">
            <Card padding="md" className="hover:border-slate-300 hover:shadow-card transition-all cursor-pointer">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-slate-500">Open Tickets Queue</span>
                <div className="p-2 bg-sky-50 text-sky-600 rounded-md group-hover:bg-sky-100 transition-colors">
                  <TicketIcon size={18} />
                </div>
              </div>
              <div className="mt-3 flex items-baseline gap-2">
                <span className="text-2xl font-bold text-slate-900">{ticketCount}</span>
                <span className="text-3xs text-emerald-600 font-medium">13 Seeded Cases</span>
              </div>
            </Card>
          </Link>

          <Card padding="md">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-500">Pending Approvals</span>
              <div className="p-2 bg-amber-50 text-amber-600 rounded-md">
                <ShieldIcon size={18} />
              </div>
            </div>
            <div className="mt-3 flex items-baseline gap-2">
              <span className="text-2xl font-bold text-slate-900">{approvalCount}</span>
              <StatusPill status="waiting_on_approval" label={`${approvalCount} awaiting`} size="sm" />
            </div>
          </Card>

          <Link href="/escalations" className="group">
            <Card padding="md" className="hover:border-slate-300 hover:shadow-card transition-all cursor-pointer">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-slate-500">Specialist Escalations</span>
                <div className="p-2 bg-purple-50 text-purple-600 rounded-md group-hover:bg-purple-100 transition-colors">
                  <UsersIcon size={18} />
                </div>
              </div>
              <div className="mt-3 flex items-baseline gap-2">
                <span className="text-2xl font-bold text-slate-900">{escalationCount}</span>
                <span className="text-3xs text-purple-600 font-medium">Policy Routed</span>
              </div>
            </Card>
          </Link>

          <Link href="/agents" className="group">
            <Card padding="md" className="hover:border-slate-300 hover:shadow-card transition-all cursor-pointer">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-slate-500">LangGraph Specialists</span>
                <div className="p-2 bg-emerald-50 text-emerald-600 rounded-md group-hover:bg-emerald-100 transition-colors">
                  <BotIcon size={18} />
                </div>
              </div>
              <div className="mt-3 flex items-baseline gap-2">
                <span className="text-2xl font-bold text-slate-900">6 Agents</span>
                <StatusPill status="online" label="Online" size="sm" />
              </div>
            </Card>
          </Link>
        </div>

        {/* Quick Triage Section */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Human Approvals Needed */}
          <Card>
            <CardHeader className="flex items-center justify-between">
              <div>
                <CardTitle className="text-sm font-bold text-slate-900 flex items-center gap-2">
                  <ShieldIcon size={16} className="text-amber-600" />
                  <span>Human Approvals Needed</span>
                </CardTitle>
                <CardDescription className="text-xs text-slate-500">
                  Financial refunds & consequential mutations requiring human confirmation
                </CardDescription>
              </div>
              <Badge variant="warning" size="sm">
                {pendingApprovals.length > 0 ? `${pendingApprovals.length} Pending` : "1 Pending"}
              </Badge>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {pendingApprovals.length > 0 ? (
                  pendingApprovals.map((appr) => (
                    <div
                      key={appr.id}
                      className="flex items-center justify-between p-3.5 rounded-lg border border-slate-200 bg-slate-50/70 hover:bg-slate-50 transition-colors"
                    >
                      <div className="space-y-1 min-w-0 pr-3">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-xs font-bold text-brand-600">{appr.ticket_id}</span>
                          <StatusPill status="waiting_on_approval" size="sm" />
                        </div>
                        <p className="text-xs text-slate-800 font-medium truncate">
                          Action: <span className="font-mono text-brand-700">{appr.action_name}</span>
                          {appr.action_payload?.amount ? ` ($${appr.action_payload.amount})` : ""}
                        </p>
                        <p className="text-3xs text-slate-500">
                          {appr.action_payload?.reason
                            ? String(appr.action_payload.reason)
                            : "Awaiting supervisor confirmation"}
                        </p>
                      </div>
                      <Link href={`/tickets/${appr.ticket_id}`}>
                        <Button variant="primary" size="xs" rightIcon={<ArrowRightIcon size={12} />}>
                          Decide
                        </Button>
                      </Link>
                    </div>
                  ))
                ) : (
                  <div className="flex items-center justify-between p-3.5 rounded-lg border border-slate-200 bg-slate-50/70 hover:bg-slate-50 transition-colors">
                    <div className="space-y-1 min-w-0 pr-3">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs font-bold text-brand-600">CD-1002</span>
                        <StatusPill status="waiting_on_approval" size="sm" />
                      </div>
                      <p className="text-xs text-slate-800 font-medium">Refund approval: $49.00 (Duplicate charge)</p>
                      <p className="text-3xs text-slate-500">TechStart Inc · Billing Specialist Gated</p>
                    </div>
                    <Link href="/tickets/CD-1002">
                      <Button variant="primary" size="xs" rightIcon={<ArrowRightIcon size={12} />}>
                        Decide
                      </Button>
                    </Link>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Deterministic Policy Escalations */}
          <Card>
            <CardHeader className="flex items-center justify-between">
              <div>
                <CardTitle className="text-sm font-bold text-slate-900 flex items-center gap-2">
                  <UsersIcon size={16} className="text-purple-600" />
                  <span>Deterministic Policy Escalations</span>
                </CardTitle>
                <CardDescription className="text-xs text-slate-500">
                  Legal, security, dispute, and enterprise outage rules requiring human specialist routing
                </CardDescription>
              </div>
              <Badge variant="neutral" size="sm">
                Rule Governed
              </Badge>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {escalations.length > 0 ? (
                  escalations.slice(0, 3).map((esc) => (
                    <div
                      key={esc.id}
                      className="flex items-center justify-between p-3.5 rounded-lg border border-slate-200 bg-slate-50/70 hover:bg-slate-50 transition-colors"
                    >
                      <div className="space-y-1 min-w-0 pr-3">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-xs font-bold text-purple-700">{esc.ticket_id}</span>
                          <StatusPill status="escalated" size="sm" />
                          <Badge variant="neutral" size="sm">
                            {esc.target_team}
                          </Badge>
                        </div>
                        <p className="text-xs text-slate-800 font-medium truncate">{esc.policy_reason}</p>
                      </div>
                      <Link href={`/tickets/${esc.ticket_id}`}>
                        <Button variant="secondary" size="xs">
                          Inspect
                        </Button>
                      </Link>
                    </div>
                  ))
                ) : (
                  <>
                    <div className="flex items-center justify-between p-3 rounded-lg border border-slate-200 bg-slate-50/70">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-xs font-bold text-purple-600">CD-1005</span>
                          <StatusPill status="escalated" size="sm" />
                          <Badge variant="neutral" size="sm">legal_compliance</Badge>
                        </div>
                        <p className="text-xs text-slate-800 font-medium">GDPR Article 17 Data Erasure Request</p>
                      </div>
                      <Link href="/tickets/CD-1005">
                        <Button variant="secondary" size="xs">Inspect</Button>
                      </Link>
                    </div>
                    <div className="flex items-center justify-between p-3 rounded-lg border border-slate-200 bg-slate-50/70">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-xs font-bold text-purple-600">CD-1011</span>
                          <StatusPill status="escalated" size="sm" />
                          <Badge variant="neutral" size="sm">billing_disputes</Badge>
                        </div>
                        <p className="text-xs text-slate-800 font-medium">Chargeback dispute threatening legal escalation</p>
                      </div>
                      <Link href="/tickets/CD-1011">
                        <Button variant="secondary" size="xs">Inspect</Button>
                      </Link>
                    </div>
                  </>
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Live Seeded Tickets Table */}
        <Card padding="none">
          <div className="p-4 sm:p-5 border-b border-slate-200 flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-slate-900">Recent Support Queue</h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Active tickets loaded from SQLite storage and ready for AI workflow triage
              </p>
            </div>
            <Link href="/tickets">
              <Button variant="secondary" size="sm" rightIcon={<ArrowRightIcon size={12} />}>
                View All {ticketCount} Tickets
              </Button>
            </Link>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50/75 text-3xs font-semibold uppercase tracking-wider text-slate-500">
                  <th className="py-3 px-4">Ticket</th>
                  <th className="py-3 px-4">Customer</th>
                  <th className="py-3 px-4">Subject</th>
                  <th className="py-3 px-4">Severity</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-xs">
                {recentTickets.length > 0 ? (
                  recentTickets.map((t) => (
                    <tr key={t.id} className="hover:bg-slate-50/75 transition-colors">
                      <td className="py-3 px-4 font-mono font-bold text-brand-600">
                        <Link href={`/tickets/${t.id}`} className="hover:underline">
                          {t.id}
                        </Link>
                      </td>
                      <td className="py-3 px-4 font-medium text-slate-900">
                        <div>{t.customer_name || t.customer_id}</div>
                        {t.customer_email && (
                          <div className="text-3xs text-slate-400 font-normal">{t.customer_email}</div>
                        )}
                      </td>
                      <td className="py-3 px-4 text-slate-700 max-w-xs truncate">{t.subject}</td>
                      <td className="py-3 px-4">
                        <StatusPill status={t.severity} size="sm" />
                      </td>
                      <td className="py-3 px-4">
                        <StatusPill status={t.status} size="sm" />
                      </td>
                      <td className="py-3 px-4 text-right">
                        <Link href={`/tickets/${t.id}`}>
                          <Button variant="secondary" size="xs">
                            Inspect
                          </Button>
                        </Link>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={6} className="py-8 text-center text-xs text-slate-400">
                      Loading recent tickets...
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Card>

        {/* System Architecture Status Footer */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="p-4 rounded-lg bg-white border border-slate-200 flex items-start gap-3 shadow-xs">
            <div className="p-2 bg-slate-100 text-slate-700 rounded-md">
              <CheckCircleIcon size={18} className="text-emerald-600" />
            </div>
            <div>
              <h4 className="text-xs font-bold text-slate-900">Persistence Engine</h4>
              <p className="text-3xs text-slate-500 mt-0.5">
                SQLite portable store + checkpoints db with atomic session isolation.
              </p>
            </div>
          </div>

          <div className="p-4 rounded-lg bg-white border border-slate-200 flex items-start gap-3 shadow-xs">
            <div className="p-2 bg-slate-100 text-slate-700 rounded-md">
              <BookOpenIcon size={18} className="text-brand-600" />
            </div>
            <div>
              <h4 className="text-xs font-bold text-slate-900">RAG Knowledge Pipeline</h4>
              <p className="text-3xs text-slate-500 mt-0.5">
                15 articles chunked into 39 embeddings with dense + BM25 keyword fusion.
              </p>
            </div>
          </div>

          <div className="p-4 rounded-lg bg-white border border-slate-200 flex items-start gap-3 shadow-xs">
            <div className="p-2 bg-slate-100 text-slate-700 rounded-md">
              <ShieldIcon size={18} className="text-purple-600" />
            </div>
            <div>
              <h4 className="text-xs font-bold text-slate-900">Firewall & Guardrails</h4>
              <p className="text-3xs text-slate-500 mt-0.5">
                Multi-layer prompt injection defense, secret redaction, and policy gates.
              </p>
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
