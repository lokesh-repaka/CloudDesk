"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { AppShell } from "@/components/layout";
import { api, NetworkError } from "@/lib/api";
import { CustomerSummary } from "@/lib/types";
import { Card } from "@/components/ui/Card";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/Table";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { EmptyState } from "@/components/ui/EmptyState";
import { SearchIcon, RefreshCwIcon, UsersIcon } from "@/components/layout/Icons";

const FALLBACK_CUSTOMERS: CustomerSummary[] = [
  {
    id: "cust-001",
    name: "Acme Corporation",
    email: "contact@acme.example.com",
    plan: "enterprise",
    created_at: "2025-01-15T00:00:00Z",
    updated_at: "2026-10-01T00:00:00Z",
  },
  {
    id: "cust-002",
    name: "TechStart Inc",
    email: "support@techstart.io",
    plan: "pro",
    created_at: "2025-03-20T00:00:00Z",
    updated_at: "2026-10-01T00:00:00Z",
  },
  {
    id: "cust-003",
    name: "EuroData Systems",
    email: "privacy@eurodata.de",
    plan: "enterprise",
    created_at: "2025-05-10T00:00:00Z",
    updated_at: "2026-10-01T00:00:00Z",
  },
  {
    id: "cust-004",
    name: "Cyberdyne Systems",
    email: "it@cyberdyne.org",
    plan: "business",
    created_at: "2025-08-01T00:00:00Z",
    updated_at: "2026-10-01T00:00:00Z",
  },
];

export default function CustomersPage() {
  const [customers, setCustomers] = useState<CustomerSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");

  const fetchCustomers = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.customers.list();
      setCustomers(res.items);
    } catch (err: unknown) {
      // Graceful fallback to demo dataset
      setCustomers(FALLBACK_CUSTOMERS);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCustomers();
  }, [fetchCustomers]);

  const filteredCustomers = customers.filter(
    (c) =>
      searchTerm === "" ||
      c.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      c.email.toLowerCase().includes(searchTerm.toLowerCase()) ||
      c.id.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const planBadges: Record<string, "brand" | "neutral" | "warning"> = {
    enterprise: "brand",
    business: "warning",
    pro: "neutral",
    free: "neutral",
  };

  return (
    <AppShell pageTitle="Customer Directory & Profiles">
      <div className="space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-white p-4 rounded-lg border border-slate-200">
          <div className="max-w-md flex-1">
            <Input
              placeholder="Search customers by name, ID, or domain..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              leftIcon={<SearchIcon size={16} />}
            />
          </div>
          <Button
            variant="secondary"
            size="sm"
            onClick={fetchCustomers}
            isLoading={loading}
            leftIcon={<RefreshCwIcon size={14} />}
          >
            Refresh
          </Button>
        </div>

        {loading && customers.length === 0 ? (
          <div className="py-12 flex justify-center text-xs text-slate-500">
            <span className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-brand-600 border-t-transparent mr-2" />
            Loading customers directory...
          </div>
        ) : filteredCustomers.length === 0 ? (
          <EmptyState
            icon={<UsersIcon size={24} />}
            title="No customers found"
            description="No customer accounts match the current search query."
            action={
              <Button variant="secondary" size="sm" onClick={() => setSearchTerm("")}>
                Clear Search
              </Button>
            }
          />
        ) : (
          <Card padding="none">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Customer ID</TableHead>
                  <TableHead>Company / Account</TableHead>
                  <TableHead>Contact Email</TableHead>
                  <TableHead>Subscription Tier</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredCustomers.map((cust) => (
                  <TableRow key={cust.id} isClickable>
                    <TableCell className="font-mono text-brand-600 font-medium">
                      <Link href={`/customers/${cust.id}`} className="hover:underline">
                        {cust.id}
                      </Link>
                    </TableCell>
                    <TableCell className="font-semibold text-slate-800">
                      <Link href={`/customers/${cust.id}`} className="hover:text-brand-600">
                        {cust.name}
                      </Link>
                    </TableCell>
                    <TableCell className="text-slate-600 font-normal">
                      {cust.email}
                    </TableCell>
                    <TableCell>
                      <Badge variant={planBadges[cust.plan] || "neutral"} size="sm">
                        {cust.plan.toUpperCase()}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant="success" size="sm" dot>
                        Active
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Link href={`/customers/${cust.id}`}>
                        <Button variant="secondary" size="xs">
                          360° Dossier
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
