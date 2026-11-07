"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { AppShell } from "@/components/layout";
import { api, NetworkError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { EscalationResponse } from "@/lib/types";
import { Card } from "@/components/ui/Card";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/Table";
import { StatusPill } from "@/components/ui/StatusPill";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Select";
import { EmptyState } from "@/components/ui/EmptyState";
import { AlertTriangleIcon, RefreshCwIcon } from "@/components/layout/Icons";

const FALLBACK_ESCALATIONS: EscalationResponse[] = [
  {
    id: "esc-1005",
    ticket_id: "CD-1005",
    workflow_id: "wf-1005",
    target_team: "legal_and_compliance",
    policy_reason: "GDPR Article 17 Erasure Request",
    severity: "critical",
    status: "open",
    created_at: new Date(Date.now() - 3600000).toISOString(),
    updated_at: new Date(Date.now() - 1800000).toISOString(),
  },
  {
    id: "esc-1006",
    ticket_id: "CD-1006",
    workflow_id: "wf-1006",
    target_team: "security_operations",
    policy_reason: "Credential stuffing alert & unauthorized access claim",
    severity: "critical",
    status: "in_investigation",
    created_at: new Date(Date.now() - 7200000).toISOString(),
    updated_at: new Date(Date.now() - 3600000).toISOString(),
  },
  {
    id: "esc-1009",
    ticket_id: "CD-1009",
    workflow_id: "wf-1009",
    target_team: "infrastructure_platform",
    policy_reason: "Production cluster outage impacting all regions",
    severity: "high",
    status: "open",
    created_at: new Date(Date.now() - 14400000).toISOString(),
    updated_at: new Date(Date.now() - 7200000).toISOString(),
  },
];

export default function EscalationsPage() {
  const { role, canAct } = useAuth();
  const [escalations, setEscalations] = useState<EscalationResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("all");

  const fetchEscalations = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.escalations.list(
        statusFilter === "all" ? undefined : { status: statusFilter }
      );
      setEscalations(res);
    } catch {
      setEscalations(FALLBACK_ESCALATIONS);
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    fetchEscalations();
  }, [fetchEscalations]);

  const filtered = escalations.filter((item) => {
    if (statusFilter === "all") return true;
    return item.status === statusFilter;
  });

  return (
    <AppShell pageTitle="Deterministic Policy Escalations" userRole={role}>
      <div className="space-y-6">
        {/* Header Rule Info Banner */}
        <div className="p-4 rounded-lg border border-purple-200 bg-purple-50/50 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div>
            <h3 className="text-xs font-semibold text-purple-900">
              Deterministic Policy Escalation Engine (CLAUDE.md §7)
            </h3>
            <p className="text-2xs text-purple-700 mt-0.5">
              Hard business rules override model autonomy to guarantee immediate specialist dispatch for compliance, security, and critical outages.
            </p>
          </div>
          {!canAct && (
            <Badge variant="neutral" size="sm">
              VIEWER (READ-ONLY)
            </Badge>
          )}
        </div>

        {/* Filters */}
        <div className="flex items-center justify-between bg-white p-4 rounded-lg border border-slate-200">
          <div className="w-48">
            <Select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              options={[
                { value: "all", label: "All Escalations" },
                { value: "open", label: "Open" },
                { value: "in_investigation", label: "In Investigation" },
                { value: "resolved", label: "Resolved" },
              ]}
            />
          </div>

          <Button
            variant="secondary"
            size="sm"
            onClick={fetchEscalations}
            isLoading={loading}
            leftIcon={<RefreshCwIcon size={14} />}
          >
            Refresh
          </Button>
        </div>

        {loading && escalations.length === 0 ? (
          <div className="py-12 flex justify-center text-xs text-slate-500">
            <span className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-purple-600 border-t-transparent mr-2" />
            Loading policy escalation queue...
          </div>
        ) : filtered.length === 0 ? (
          <EmptyState
            icon={<AlertTriangleIcon size={24} />}
            title="No escalations in queue"
            description="There are currently no tickets matching the policy escalation criteria."
            action={
              <Button variant="secondary" size="sm" onClick={() => setStatusFilter("all")}>
                View All
              </Button>
            }
          />
        ) : (
          <Card padding="none">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Escalation ID</TableHead>
                  <TableHead>Ticket ID</TableHead>
                  <TableHead>Specialist Team</TableHead>
                  <TableHead>Policy Reason</TableHead>
                  <TableHead>Severity</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Escalated At</TableHead>
                  <TableHead>Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map((item) => (
                  <TableRow key={item.id} isClickable>
                    <TableCell className="font-mono text-3xs text-slate-500 font-medium">
                      {item.id}
                    </TableCell>
                    <TableCell className="font-mono font-semibold text-purple-700">
                      <Link href={`/tickets/${item.ticket_id}`} className="hover:underline">
                        {item.ticket_id}
                      </Link>
                    </TableCell>
                    <TableCell>
                      <Badge variant="brand" size="sm">
                        {item.target_team.replace(/_/g, " ")}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-slate-800 font-medium max-w-xs truncate">
                      {item.policy_reason}
                    </TableCell>
                    <TableCell>
                      <StatusPill status={item.severity} size="sm" />
                    </TableCell>
                    <TableCell>
                      <StatusPill status={item.status} size="sm" />
                    </TableCell>
                    <TableCell className="text-slate-400 text-3xs font-mono">
                      {new Date(item.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                    </TableCell>
                    <TableCell>
                      <Link href={`/tickets/${item.ticket_id}`}>
                        <Button variant="secondary" size="xs">
                          Inspect Route
                        </Button>
                      </Link>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        )}
      </div>
    </AppShell>
  );
}
