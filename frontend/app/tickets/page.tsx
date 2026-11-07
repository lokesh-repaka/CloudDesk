"use client";

import React, { useState } from "react";
import { AppShell } from "@/components/layout";
import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/Card";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/Table";
import { StatusPill } from "@/components/ui/StatusPill";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { SearchIcon, FilterIcon } from "@/components/layout/Icons";

export default function TicketsPage() {
  const [searchTerm, setSearchTerm] = useState("");

  const sampleTickets = [
    {
      id: "CD-1001",
      customer: "John Doe (Acme Corp)",
      subject: "Cannot login via SAML Single Sign-On",
      category: "login_issue",
      severity: "high",
      status: "in_progress",
      channel: "email",
      updatedAt: "10 mins ago",
    },
    {
      id: "CD-1002",
      customer: "Jane Smith (TechStart)",
      subject: "Refund request for unexpected renewal charge",
      category: "billing",
      severity: "medium",
      status: "waiting_on_approval",
      channel: "web",
      updatedAt: "25 mins ago",
    },
    {
      id: "CD-1005",
      customer: "Max Müller (EuroData)",
      subject: "GDPR Article 17 Erasure Demand",
      category: "security",
      severity: "critical",
      status: "escalated",
      channel: "email",
      updatedAt: "1 hour ago",
    },
    {
      id: "CD-1007",
      customer: "Sarah Connor (Cyberdyne)",
      subject: "Webhook delivery failure HTTP 500 error",
      category: "api_failure",
      severity: "high",
      status: "new",
      channel: "api",
      updatedAt: "2 hours ago",
    },
  ];

  const filteredTickets = sampleTickets.filter(
    (t) =>
      t.id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      t.subject.toLowerCase().includes(searchTerm.toLowerCase()) ||
      t.customer.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <AppShell pageTitle="Support Tickets Queue" userRole="agent">
      <div className="space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="flex-1 max-w-md">
            <Input
              placeholder="Search by ticket ID, subject, customer..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              leftIcon={<SearchIcon size={16} />}
            />
          </div>
          <div className="flex items-center gap-2">
            <Button variant="secondary" size="sm" leftIcon={<FilterIcon size={14} />}>
              Filters
            </Button>
          </div>
        </div>

        <Card padding="none">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Ticket ID</TableHead>
                <TableHead>Customer</TableHead>
                <TableHead>Subject</TableHead>
                <TableHead>Category</TableHead>
                <TableHead>Severity</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Channel</TableHead>
                <TableHead>Updated</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredTickets.map((ticket) => (
                <TableRow key={ticket.id} isClickable>
                  <TableCell className="font-mono font-semibold text-brand-600">
                    {ticket.id}
                  </TableCell>
                  <TableCell className="font-medium text-slate-800">
                    {ticket.customer}
                  </TableCell>
                  <TableCell className="truncate max-w-xs font-normal">
                    {ticket.subject}
                  </TableCell>
                  <TableCell>
                    <Badge variant="neutral" size="sm">
                      {ticket.category.replace(/_/g, " ")}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <StatusPill status={ticket.severity} size="sm" />
                  </TableCell>
                  <TableCell>
                    <StatusPill status={ticket.status} size="sm" />
                  </TableCell>
                  <TableCell className="uppercase text-3xs text-slate-500 font-mono">
                    {ticket.channel}
                  </TableCell>
                  <TableCell className="text-slate-400 text-3xs">
                    {ticket.updatedAt}
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

