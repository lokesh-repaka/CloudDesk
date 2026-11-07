"use client";

import React, { useState } from "react";
import { AppShell } from "@/components/layout";
import { Card } from "@/components/ui/Card";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/Table";
import { Badge } from "@/components/ui/Badge";
import { Input } from "@/components/ui/Input";
import { SearchIcon } from "@/components/layout/Icons";

export default function CustomersPage() {
  const [searchTerm, setSearchTerm] = useState("");

  const sampleCustomers = [
    {
      id: "CUST-001",
      name: "Acme Corporation",
      email: "contact@acme.example.com",
      plan: "enterprise",
      arr: "$120,000",
      ticketsCount: 14,
      status: "active",
    },
    {
      id: "CUST-002",
      name: "TechStart Inc",
      email: "support@techstart.io",
      plan: "pro",
      arr: "$24,000",
      ticketsCount: 5,
      status: "active",
    },
    {
      id: "CUST-003",
      name: "Cyberdyne Systems",
      email: "it@cyberdyne.corp",
      plan: "enterprise",
      arr: "$250,000",
      ticketsCount: 22,
      status: "active",
    },
  ];

  const planBadges: Record<string, "brand" | "neutral" | "warning"> = {
    enterprise: "brand",
    business: "warning",
    pro: "neutral",
    free: "neutral",
  };

  return (
    <AppShell pageTitle="Customer Directory & Profiles" userRole="viewer">
      <div className="space-y-6">
        <div className="max-w-md">
          <Input
            placeholder="Search customers by name, ID, or domain..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            leftIcon={<SearchIcon size={16} />}
          />
        </div>

        <Card padding="none">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Customer ID</TableHead>
                <TableHead>Company / Account</TableHead>
                <TableHead>Contact Email</TableHead>
                <TableHead>Subscription Plan</TableHead>
                <TableHead>ARR</TableHead>
                <TableHead>Total Tickets</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sampleCustomers.map((cust) => (
                <TableRow key={cust.id} isClickable>
                  <TableCell className="font-mono text-brand-600 font-medium">
                    {cust.id}
                  </TableCell>
                  <TableCell className="font-semibold text-slate-800">
                    {cust.name}
                  </TableCell>
                  <TableCell className="text-slate-600">{cust.email}</TableCell>
                  <TableCell>
                    <Badge variant={planBadges[cust.plan] || "neutral"} size="sm">
                      {cust.plan.toUpperCase()}
                    </Badge>
                  </TableCell>
                  <TableCell className="font-mono text-slate-700">{cust.arr}</TableCell>
                  <TableCell className="text-slate-700">{cust.ticketsCount}</TableCell>
                  <TableCell>
                    <Badge variant="success" size="sm" dot>
                      Active
                    </Badge>
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

