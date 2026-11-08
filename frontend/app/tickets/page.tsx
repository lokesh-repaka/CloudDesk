"use client";

import React, { useState, useEffect, useCallback, useMemo } from "react";
import Link from "next/link";
import { AppShell } from "@/components/layout";
import { api, NetworkError } from "@/lib/api";
import { TicketSummary } from "@/lib/types";
import { Card } from "@/components/ui/Card";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/Table";
import { StatusPill } from "@/components/ui/StatusPill";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { EmptyState } from "@/components/ui/EmptyState";
import { Alert } from "@/components/ui/Alert";
import { SearchIcon, RefreshCwIcon, TicketIcon, ArrowRightIcon } from "@/components/layout/Icons";

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

  const counts = useMemo(() => {
    return {
      all: tickets.length,
      waiting_on_approval: tickets.filter((t) => t.status === "waiting_on_approval").length,
      in_progress: tickets.filter((t) => t.status === "in_progress").length,
      escalated: tickets.filter((t) => t.status === "escalated").length,
      resolved: tickets.filter((t) => t.status === "resolved").length,
    };
  }, [tickets]);

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

        {/* Quick Filter Status Tabs */}
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => setStatusFilter("all")}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors flex items-center gap-1.5 ${
              statusFilter === "all"
                ? "bg-slate-900 text-white shadow-xs"
                : "bg-white text-slate-600 hover:bg-slate-100 border border-slate-200"
            }`}
          >
            <span>All Tickets</span>
            <span
              className={`px-1.5 py-0.2 rounded-full text-3xs ${
                statusFilter === "all" ? "bg-slate-700 text-white" : "bg-slate-100 text-slate-600"
              }`}
            >
              {counts.all}
            </span>
          </button>

          <button
            type="button"
            onClick={() => setStatusFilter("waiting_on_approval")}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors flex items-center gap-1.5 ${
              statusFilter === "waiting_on_approval"
                ? "bg-amber-600 text-white shadow-xs"
                : "bg-white text-amber-800 hover:bg-amber-50 border border-amber-200"
            }`}
          >
            <span>Needs Approval</span>
            <span
              className={`px-1.5 py-0.2 rounded-full text-3xs ${
                statusFilter === "waiting_on_approval"
                  ? "bg-amber-800 text-white"
                  : "bg-amber-100 text-amber-800"
              }`}
            >
              {counts.waiting_on_approval}
            </span>
          </button>

          <button
            type="button"
            onClick={() => setStatusFilter("in_progress")}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors flex items-center gap-1.5 ${
              statusFilter === "in_progress"
                ? "bg-blue-600 text-white shadow-xs"
                : "bg-white text-blue-800 hover:bg-blue-50 border border-blue-200"
            }`}
          >
            <span>In Progress</span>
            <span
              className={`px-1.5 py-0.2 rounded-full text-3xs ${
                statusFilter === "in_progress" ? "bg-blue-800 text-white" : "bg-blue-100 text-blue-800"
              }`}
            >
              {counts.in_progress}
            </span>
          </button>

          <button
            type="button"
            onClick={() => setStatusFilter("escalated")}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors flex items-center gap-1.5 ${
              statusFilter === "escalated"
                ? "bg-purple-600 text-white shadow-xs"
                : "bg-white text-purple-800 hover:bg-purple-50 border border-purple-200"
            }`}
          >
            <span>Escalated</span>
            <span
              className={`px-1.5 py-0.2 rounded-full text-3xs ${
                statusFilter === "escalated" ? "bg-purple-800 text-white" : "bg-purple-100 text-purple-800"
              }`}
            >
              {counts.escalated}
            </span>
          </button>

          <button
            type="button"
            onClick={() => setStatusFilter("resolved")}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors flex items-center gap-1.5 ${
              statusFilter === "resolved"
                ? "bg-emerald-600 text-white shadow-xs"
                : "bg-white text-emerald-800 hover:bg-emerald-50 border border-emerald-200"
            }`}
          >
            <span>Resolved</span>
            <span
              className={`px-1.5 py-0.2 rounded-full text-3xs ${
                statusFilter === "resolved"
                  ? "bg-emerald-800 text-white"
                  : "bg-emerald-100 text-emerald-800"
              }`}
            >
              {counts.resolved}
            </span>
          </button>
        </div>

        {/* Filter Controls Bar */}
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 bg-white p-4 rounded-lg border border-slate-200 shadow-xs">
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
                      <div className="flex items-center gap-2">
                        <div className="h-6 w-6 rounded-full bg-slate-100 text-slate-700 font-bold text-3xs flex items-center justify-center border border-slate-200 flex-shrink-0">
                          {(ticket.customer_name || ticket.customer_id || "C").charAt(0).toUpperCase()}
                        </div>
                        <div className="min-w-0">
                          <div className="truncate font-semibold text-slate-900">
                            {ticket.customer_name || ticket.customer_id}
                          </div>
                          {ticket.customer_email && (
                            <div className="text-3xs text-slate-400 font-normal truncate">
                              {ticket.customer_email}
                            </div>
                          )}
                        </div>
                      </div>
                    </TableCell>
                    <TableCell className="max-w-xs">
                      <Link href={`/tickets/${ticket.id}`} className="hover:text-brand-600">
                        <div className="font-normal text-slate-900 truncate">{ticket.subject}</div>
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
                        <Button variant="secondary" size="xs" rightIcon={<ArrowRightIcon size={12} />}>
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
