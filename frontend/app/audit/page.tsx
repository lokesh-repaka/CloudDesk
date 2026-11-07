"use client";

import React from "react";
import { AppShell } from "@/components/layout";
import { Card } from "@/components/ui/Card";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/Table";
import { Badge } from "@/components/ui/Badge";
import { ShieldIcon } from "@/components/layout/Icons";

export default function AuditPage() {
  const auditLogs = [
    {
      id: "AUD-9011",
      timestamp: "2026-11-07 17:35:10",
      actor: "agent@clouddesk.dev",
      action: "APPROVAL_DECIDED",
      target: "ticket:CD-1002",
      detail: "Approved refund action ($49.00). Reason: Verified billing record duplicate",
      ipAddress: "127.0.0.1",
    },
    {
      id: "AUD-9010",
      timestamp: "2026-11-07 17:30:22",
      actor: "system:workflow",
      action: "INTERRUPT_TRIGGERED",
      target: "ticket:CD-1002",
      detail: "Consequential action requires human approval before dispatching funds",
      ipAddress: "internal",
    },
    {
      id: "AUD-9009",
      timestamp: "2026-11-07 17:28:01",
      actor: "system:policy",
      action: "POLICY_ESCALATION",
      target: "ticket:CD-1005",
      detail: "Deterministic rule ESC-001 triggered: GDPR erasure routed to legal_and_compliance",
      ipAddress: "internal",
    },
    {
      id: "AUD-9008",
      timestamp: "2026-11-07 17:20:15",
      actor: "agent@clouddesk.dev",
      action: "WORKFLOW_TRIGGERED",
      target: "ticket:CD-1001",
      detail: "Initiated multi-agent investigation workflow",
      ipAddress: "127.0.0.1",
    },
  ];

  return (
    <AppShell pageTitle="Audit & Compliance Logs" userRole="viewer">
      <div className="space-y-6">
        <div className="flex items-center gap-3 bg-white p-4 rounded-lg border border-slate-200">
          <div className="p-2 rounded bg-slate-100 text-slate-700">
            <ShieldIcon size={18} />
          </div>
          <div>
            <h3 className="text-xs font-semibold text-slate-900">Immutable Audit Trail</h3>
            <p className="text-2xs text-slate-500">
              Every sensitive action, approval decision, policy rule match, and role access is permanently recorded.
            </p>
          </div>
        </div>

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
              {auditLogs.map((log) => (
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
                  <TableCell className="font-mono text-3xs text-slate-400">{log.ipAddress}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      </div>
    </AppShell>
  );
}

