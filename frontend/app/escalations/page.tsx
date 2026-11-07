"use client";

import React from "react";
import { AppShell } from "@/components/layout";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/Table";
import { StatusPill } from "@/components/ui/StatusPill";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";

export default function EscalationsPage() {
  const escalations = [
    {
      id: "CD-1005",
      team: "legal_and_compliance",
      reason: "GDPR Article 17 Erasure Request",
      severity: "critical",
      priority: "P1",
      customer: "Max Müller (EuroData)",
      escalatedAt: "1 hour ago",
    },
    {
      id: "CD-1006",
      team: "security_operations",
      reason: "Credential stuffing alert & unauthorized access claim",
      severity: "critical",
      priority: "P1",
      customer: "Alice Walker (Apex)",
      escalatedAt: "3 hours ago",
    },
    {
      id: "CD-1009",
      team: "infrastructure_platform",
      reason: "Production cluster outage impacting all regions",
      severity: "high",
      priority: "P2",
      customer: "Global Logistics Ltd",
      escalatedAt: "4 hours ago",
    },
  ];

  return (
    <AppShell pageTitle="Deterministic Policy Escalations" userRole="agent">
      <div className="space-y-6">
        <div className="p-4 rounded-lg border border-purple-200 bg-purple-50/50">
          <h3 className="text-xs font-semibold text-purple-900">
            Escalation Routing Rule Engine (CLAUDE.md §7)
          </h3>
          <p className="text-2xs text-purple-700 mt-0.5">
            Hard business rules deterministically route critical compliance, security, and infrastructure issues directly to specialized engineering teams, overriding model autonomy.
          </p>
        </div>

        <Card padding="none">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Ticket ID</TableHead>
                <TableHead>Target Specialist Team</TableHead>
                <TableHead>Trigger Reason</TableHead>
                <TableHead>Customer</TableHead>
                <TableHead>Severity</TableHead>
                <TableHead>Escalated At</TableHead>
                <TableHead>Action</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {escalations.map((item) => (
                <TableRow key={item.id}>
                  <TableCell className="font-mono font-semibold text-purple-700">
                    {item.id}
                  </TableCell>
                  <TableCell>
                    <Badge variant="brand" size="sm">
                      {item.team}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-slate-800 font-medium">
                    {item.reason}
                  </TableCell>
                  <TableCell className="text-slate-600">{item.customer}</TableCell>
                  <TableCell>
                    <StatusPill status={item.severity} size="sm" />
                  </TableCell>
                  <TableCell className="text-slate-400 text-3xs">{item.escalatedAt}</TableCell>
                  <TableCell>
                    <Button variant="secondary" size="xs">
                      Inspect Route
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      </div>
    </AppShell>
  );
}

