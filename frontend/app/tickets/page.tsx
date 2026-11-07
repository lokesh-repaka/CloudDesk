"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { AppShell } from "@/components/layout";
import { api, NetworkError } from "@/lib/api";
import { TicketSummary, TicketStatus, Severity } from "@/lib/types";
import { Card } from "@/components/ui/Card";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/Table";
import { StatusPill } from "@/components/ui/StatusPill";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { EmptyState } from "@/components/ui/EmptyState";
import { Alert } from "@/components/ui/Alert";
import { SearchIcon, RefreshCwIcon, FilterIcon, TicketIcon } from "@/components/layout/Icons";

const FALLBACK_TICKETS: TicketSummary[] = [
  {
    id: "CD-1001",
    customer_id: "cust-001",
    customer_name: "Acme Corporation",
    customer_email: "contact@acme.example.com",
    subject: "Cannot login via SAML Single Sign-On",
    category: "login_issue",
    severity: "high",
    status: "in_progress",
    channel: "email",
    created_at: new Date(Date.now() - 3600000).toISOString(),
    updated_at: new Date(Date.now() - 600000).toISOString(),
  },
  {
    id: "CD-1002",
    customer_id: "cust-002",
    customer_name: "TechStart Inc",
    customer_email: "support@techstart.io",
    subject: "Refund request for unexpected renewal charge",
    category: "billing",
    severity: "medium",
    status: "waiting_on_approval",
    channel: "web",
    created_at: new Date(Date.now() - 7200000).toISOString(),
    updated_at: new Date(Date.now() - 1500000).toISOString(),
  },
  {
    id: "CD-1005",
    customer_id: "cust-003",
    customer_name: "EuroData Systems",
    customer_email: "privacy@eurodata.de",
    subject: "GDPR Article 17 Erasure Demand",
    category: "security",
    severity: "critical",
    status: "escalated",
    channel: "email",
    created_at: new Date(Date.now() - 14400000).toISOString(),
    updated_at: new Date(Date.now() - 3600000).toISOString(),
  },
  {
    id: "CD-1007",
    customer_id: "cust-004",
    customer_name: "Cyberdyne Corp",
    customer_email: "dev@cyberdyne.org",
    subject: "Webhook delivery failure HTTP 500 error",
    category: "api_failure",
    severity: "high",
    status: "new",
    channel: "api",
    created_at: new Date(Date.now() - 28800000).toISOString(),
    updated_at: new Date(Date.now() - 7200000).toISOString(),
  },
];

export default function TicketsPage() {
  const [tickets, setTickets] = useState<TicketSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [severityFilter, setSeverityFilter] = useState<string>("all");

  const fetchTickets = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.tickets.list();
      setTickets(res.items);
    } catch (err: unknown) {
      if (err instanceof NetworkError) {
        // Fallback to sample data for offline / demo resilience
        setTickets(FALLBACK_TICKETS);
      } else {
        setError(err instanceof Error ? err.message : "Failed to load support tickets.");
        setTickets(FALLBACK_TICKETS);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTickets();
  }, [fetchTickets]);

  const filteredTickets = tickets.filter((t) => {
    const matchesSearch =
      searchTerm === "" ||
      t.id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      t.subject.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (t.customer_name && t.customer_name.toLowerCase().includes(searchTerm.toLowerCase())) ||
      (t.customer_email && t.customer_email.toLowerCase().includes(searchTerm.toLowerCase()));

    const matchesStatus = statusFilter === "all" || t.status === statusFilter;
    const matchesSeverity = severityFilter === "all" || t.severity === severityFilter;

    return matchesSearch && matchesStatus && matchesSeverity;
  });

  return (
    <AppShell pageTitle="Support Tickets Queue">
      <div className="space-y-6">
        {error && (
          <Alert variant="warning" title="Offline Mode Notice">
            {error} (Displaying offline demo cases)
          </Alert>
        )}

        {/* Filter Controls Bar */}
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 bg-white p-4 rounded-lg border border-slate-200">
          <div className="flex-1 max-w-sm">
            <Input
              placeholder="Search by ticket ID, subject, customer..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              leftIcon={<SearchIcon size={16} />}
            />
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <div className="w-40">
              <Select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                options={[
                  { value: "all", label: "All Statuses" },
                  { value: "new", label: "New" },
                  { value: "in_progress", label: "In Progress" },
                  { value: "waiting_on_approval", label: "Waiting on Approval" },
                  { value: "escalated", label: "Escalated" },
                  { value: "resolved", label: "Resolved" },
                  { value: "closed", label: "Closed" },
                ]}
              />
            </div>

            <div className="w-36">
              <Select
                value={severityFilter}
                onChange={(e) => setSeverityFilter(e.target.value)}
                options={[
                  { value: "all", label: "All Severities" },
                  { value: "low", label: "Low" },
                  { value: "medium", label: "Medium" },
                  { value: "high", label: "High" },
                  { value: "critical", label: "Critical" },
                ]}
              />
            </div>

            <Button
              variant="secondary"
              size="sm"
              onClick={fetchTickets}
              isLoading={loading}
              leftIcon={<RefreshCwIcon size={14} />}
            >
              Refresh
            </Button>
          </div>
        </div>

        {/* Table / Empty State */}
        {loading && tickets.length === 0 ? (
          <div className="py-12 flex justify-center text-xs text-slate-500">
            <span className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-brand-600 border-t-transparent mr-2" />
            Loading tickets queue...
          </div>
        ) : filteredTickets.length === 0 ? (
          <EmptyState
            icon={<TicketIcon size={24} />}
            title="No tickets found"
            description="No support tickets match the selected filters or search criteria."
            action={
              <Button
                variant="secondary"
                size="sm"
                onClick={() => {
                  setSearchTerm("");
                  setStatusFilter("all");
                  setSeverityFilter("all");
                }}
              >
                Reset Filters
              </Button>
            }
          />
        ) : (
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
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredTickets.map((ticket) => (
                  <TableRow key={ticket.id} isClickable>
                    <TableCell className="font-mono font-semibold text-brand-600">
                      <Link href={`/tickets/${ticket.id}`} className="hover:underline">
                        {ticket.id}
                      </Link>
                    </TableCell>
                    <TableCell className="font-medium text-slate-800">
                      <div>{ticket.customer_name || ticket.customer_id}</div>
                      {ticket.customer_email && (
                        <div className="text-3xs text-slate-400 font-normal">{ticket.customer_email}</div>
                      )}
                    </TableCell>
                    <TableCell className="truncate max-w-xs font-normal">
                      <Link href={`/tickets/${ticket.id}`} className="hover:text-brand-600">
                        {ticket.subject}
                      </Link>
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
                    <TableCell>
                      <Link href={`/tickets/${ticket.id}`}>
                        <Button variant="secondary" size="xs">
                          Inspect
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
