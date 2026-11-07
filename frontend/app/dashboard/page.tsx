"use client";

import React from "react";
import { AppShell } from "@/components/layout";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import { StatusPill } from "@/components/ui/StatusPill";
import { Button } from "@/components/ui/Button";
import { TicketIcon, UsersIcon, ShieldIcon, BotIcon } from "@/components/layout/Icons";
import Link from "next/link";

export default function DashboardPage() {
  return (
    <AppShell pageTitle="Support Operations Dashboard" userRole="agent">
      <div className="space-y-6">
        {/* Welcome & Overview Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-white p-5 rounded-lg border border-slate-200">
          <div>
            <h2 className="text-lg font-bold text-slate-900">Welcome to CloudDesk Support</h2>
            <p className="text-xs text-slate-500 mt-1">
              AI-orchestrated customer resolution platform with policy-gated automation.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Link href="/tickets">
              <Button variant="primary" size="sm" leftIcon={<TicketIcon size={14} />}>
                View Active Queue
              </Button>
            </Link>
          </div>
        </div>

        {/* Metrics Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card padding="md">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-500">Open Tickets</span>
              <div className="p-2 bg-sky-50 text-sky-600 rounded-md">
                <TicketIcon size={16} />
              </div>
            </div>
            <div className="mt-3 flex items-baseline gap-2">
              <span className="text-2xl font-bold text-slate-900">12</span>
              <span className="text-2xs text-emerald-600 font-medium">3 requiring review</span>
            </div>
          </Card>

          <Card padding="md">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-500">Pending Approvals</span>
              <div className="p-2 bg-amber-50 text-amber-600 rounded-md">
                <ShieldIcon size={16} />
              </div>
            </div>
            <div className="mt-3 flex items-baseline gap-2">
              <span className="text-2xl font-bold text-slate-900">3</span>
              <StatusPill status="pending" size="sm" />
            </div>
          </Card>

          <Card padding="md">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-500">Specialist Escalations</span>
              <div className="p-2 bg-purple-50 text-purple-600 rounded-md">
                <UsersIcon size={16} />
              </div>
            </div>
            <div className="mt-3 flex items-baseline gap-2">
              <span className="text-2xl font-bold text-slate-900">2</span>
              <span className="text-2xs text-purple-600 font-medium">Policy routed</span>
            </div>
          </Card>

          <Card padding="md">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-500">AI Agents Active</span>
              <div className="p-2 bg-emerald-50 text-emerald-600 rounded-md">
                <BotIcon size={16} />
              </div>
            </div>
            <div className="mt-3 flex items-baseline gap-2">
              <span className="text-2xl font-bold text-slate-900">8 / 8</span>
              <StatusPill status="online" size="sm" />
            </div>
          </Card>
        </div>

        {/* Quick Triage Section */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card>
            <CardHeader>
              <div>
                <CardTitle>Human Approvals Needed</CardTitle>
                <CardDescription>Financial and consequential actions awaiting confirmation</CardDescription>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                <div className="flex items-center justify-between p-3 rounded-md border border-slate-200 bg-slate-50/60">
                  <div className="space-y-0.5">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-bold text-brand-600">CD-1002</span>
                      <StatusPill status="waiting_on_approval" size="sm" />
                    </div>
                    <p className="text-xs text-slate-700 font-medium">Refund approval: $49.00 (Duplicate charge)</p>
                    <p className="text-3xs text-slate-400">Acme Corp · Triage by Billing Specialist</p>
                  </div>
                  <Link href="/tickets">
                    <Button variant="secondary" size="xs">Inspect</Button>
                  </Link>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div>
                <CardTitle>Deterministic Policy Escalations</CardTitle>
                <CardDescription>Hard rules requiring specialized engineering or legal handling</CardDescription>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                <div className="flex items-center justify-between p-3 rounded-md border border-slate-200 bg-slate-50/60">
                  <div className="space-y-0.5">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-bold text-purple-600">CD-1005</span>
                      <StatusPill status="escalated" size="sm" />
                    </div>
                    <p className="text-xs text-slate-700 font-medium">GDPR Article 17 Data Erasure Request</p>
                    <p className="text-3xs text-slate-400">Target Team: legal_and_compliance</p>
                  </div>
                  <Link href="/escalations">
                    <Button variant="secondary" size="xs">View Route</Button>
                  </Link>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </AppShell>
  );
}

