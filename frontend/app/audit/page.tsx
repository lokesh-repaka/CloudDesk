"use client";

import React, { useState } from "react";
import { AppShell } from "@/components/layout";
import { AuditLogResponse } from "@/lib/types";
import { Card } from "@/components/ui/Card";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/Table";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Select";
import { EmptyState } from "@/components/ui/EmptyState";
import { ShieldIcon, RefreshCwIcon } from "@/components/layout/Icons";

const SAMPLE_AUDIT_LOGS: AuditLogResponse[] = [
  {
    id: "AUD-9011",
    timestamp: "2026-11-08 02:45:10",
    actor: "agent@clouddesk.demo",
    action: "APPROVAL_DECIDED",
    target: "ticket:CD-1002",
    detail: "Approved refund action ($49.00). Reason: Verified duplicate billing record",
    ip_address: "127.0.0.1",
  },
  {
    id: "AUD-9010",
    timestamp: "2026-11-08 02:40:22",
    actor: "system:workflow",
    action: "INTERRUPT_TRIGGERED",
    target: "ticket:CD-1002",
    detail: "Consequential action requires human approval before dispatching funds",
    ip_address: "internal",
  },
  {
    id: "AUD-9009",
    timestamp: "2026-11-08 02:35:01",
    actor: "system:policy",
    action: "POLICY_ESCALATION",
    target: "ticket:CD-1005",
    detail: "Deterministic rule ESC-001 triggered: GDPR erasure routed to legal_and_compliance",
    ip_address: "internal",
  },
  {
    id: "AUD-9008",
    timestamp: "2026-11-08 02:20:15",
    actor: "agent@clouddesk.demo",
    action: "WORKFLOW_TRIGGERED",
    target: "ticket:CD-1001",
    detail: "Initiated multi-agent investigation workflow",
    ip_address: "127.0.0.1",
  },
  {
    id: "AUD-9007",
    timestamp: "2026-11-08 01:10:00",
    actor: "admin@clouddesk.demo",
    action: "KNOWLEDGE_REINDEX",
    target: "qdrant:clouddesk_knowledge",
    detail: "Reindexed 4 knowledge base articles and 35 vector chunks",
    ip_address: "127.0.0.1",
  },
];

export default function AuditPage() {
  const [logs, setLogs] = useState<AuditLogResponse[]>(SAMPLE_AUDIT_LOGS);
  const [actionFilter, setActionFilter] = useState("all");
  const [loading, setLoading] = useState(false);

  const handleRefresh = () => {
    setLoading(true);
    setTimeout(() => {
      setLogs(SAMPLE_AUDIT_LOGS);
      setLoading(false);
    }, 300);
  };

  const filteredLogs = logs.filter((log) => {
    if (actionFilter === "all") return true;
    return log.action === actionFilter;
  });

  return (
    <AppShell pageTitle="Audit & Compliance Logs">
      <div className="space-y-6">
        {/* Header Alert */}
        <div className="flex items-center justify-between bg-white p-4 rounded-lg border border-slate-200">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded bg-slate-100 text-slate-700">
              <ShieldIcon size={18} />
            </div>
            <div>
              <h3 className="text-xs font-semibold text-slate-900">Immutable Audit Trail (N6)</h3>
              <p className="text-2xs text-slate-500">
                Every sensitive mutation, approval decision, policy rule match, and access event is recorded.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="w-48">
              <Select
                value={actionFilter}
                onChange={(e) => setActionFilter(e.target.value)}
                options={[
                  { value: "all", label: "All Actions" },
                  { value: "APPROVAL_DECIDED", label: "Approval Decided" },
                  { value: "INTERRUPT_TRIGGERED", label: "Interrupt Triggered" },
                  { value: "POLICY_ESCALATION", label: "Policy Escalation" },
                  { value: "WORKFLOW_TRIGGERED", label: "Workflow Triggered" },
                  { value: "KNOWLEDGE_REINDEX", label: "Knowledge Reindex" },
                ]}
              />
            </div>
            <Button
              variant="secondary"
              size="sm"
              onClick={handleRefresh}
              isLoading={loading}
              leftIcon={<RefreshCwIcon size={14} />}
            >
              Refresh
            </Button>
          </div>
        </div>

        {filteredLogs.length === 0 ? (
          <EmptyState
            icon={<ShieldIcon size={24} />}
            title="No audit events found"
            description="No audit logs match the selected action filter."
            action={
              <Button variant="secondary" size="sm" onClick={() => setActionFilter("all")}>
                Reset Filter
              </Button>
            }
          />
        ) : (
          <Card padding="none">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Audit ID</TableHead>
                  <TableHead>Timestamp (UTC)</TableHead>
                  <TableHead>Actor</TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead>Target Entity</TableHead>
                  <TableHead>Event Details</TableHead>
                  <TableHead>Client IP</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredLogs.map((log) => (
                  <TableRow key={log.id}>
                    <TableCell className="font-mono text-3xs text-slate-500">{log.id}</TableCell>
                    <TableCell className="font-mono text-3xs text-slate-600">{log.timestamp}</TableCell>
                    <TableCell className="font-mono text-xs text-slate-800">{log.actor}</TableCell>
                    <TableCell>
                      <Badge variant="brand" size="sm">
                        {log.action}
                      </Badge>
                    </TableCell>
                    <TableCell className="font-mono text-xs font-semibold text-brand-600">
                      {log.target}
                    </TableCell>
                    <TableCell className="text-slate-700 max-w-sm truncate text-2xs">
                      {log.detail}
                    </TableCell>
                    <TableCell className="font-mono text-3xs text-slate-400">{log.ip_address}</TableCell>
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
