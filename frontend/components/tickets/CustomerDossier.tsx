"use client";

import React from "react";
import Link from "next/link";
import { CustomerDetail } from "@/lib/types";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { StatusPill } from "@/components/ui/StatusPill";

interface CustomerDossierProps {
  customer: CustomerDetail | null;
  isLoading?: boolean;
}

export function CustomerDossier({ customer, isLoading = false }: CustomerDossierProps) {
  if (isLoading) {
    return (
      <Card padding="none" className="p-5 space-y-4">
        <div className="h-5 bg-[#14262f] rounded animate-pulse w-1/3 mb-4" />
        <div className="space-y-3">
          <div className="h-4 bg-[#112027] rounded animate-pulse w-3/4" />
          <div className="h-4 bg-[#112027] rounded animate-pulse w-1/2" />
          <div className="h-20 bg-[#0e1b21] rounded border border-[#162d36] animate-pulse" />
        </div>
      </Card>
    );
  }

  if (!customer) {
    return (
      <Card padding="md">
        <div className="text-center py-6 text-[#7e9aa6] text-sm">
          No customer dossier available for this ticket.
        </div>
      </Card>
    );
  }

  const activeSub = customer.active_subscription;
  const workspaces = customer.workspaces || [];
  const memoryNotes = customer.memory_notes || [];
  const recentTickets = customer.recent_tickets || [];

  return (
    <Card padding="none" className="flex flex-col h-full overflow-hidden">
      <CardHeader className="px-5 py-4 border-b border-[#162d36] mb-0 bg-[#0c181d]">
        <div className="flex items-center justify-between w-full">
          <CardTitle className="text-sm font-extrabold text-white flex items-center gap-2">
            <span>Customer Dossier</span>
            <Badge variant="brand">{customer.plan.toUpperCase()}</Badge>
          </CardTitle>
          <Link
            href={`/customers`}
            className="text-3xs font-bold text-[#00d2b4] hover:underline"
          >
            Directory →
          </Link>
        </div>
      </CardHeader>

      <div className="p-4 sm:p-5 space-y-6 overflow-y-auto flex-1 bg-[#0c181d]">
        {/* Customer Profile Summary */}
        <div className="bg-[#0f2127] rounded-xl p-4 border border-[#183642]">
          <div className="flex items-start justify-between">
            <div>
              <h3 className="font-bold text-white text-sm">{customer.name}</h3>
              <p className="text-xs text-[#00d2b4] font-mono mt-0.5">{customer.email}</p>
            </div>
            <span className="text-3xs font-mono text-[#5a7683]">ID: {customer.id}</span>
          </div>
          <div className="mt-3 pt-3 border-t border-[#183642] flex items-center justify-between text-2xs text-[#7e9aa6]">
            <span>Customer since:</span>
            <span className="font-medium text-slate-200">
              {new Date(customer.created_at).toLocaleDateString(undefined, {
                year: "numeric",
                month: "short",
                day: "numeric",
              })}
            </span>
          </div>
        </div>

        {/* Active Subscription */}
        <div>
          <h4 className="text-3xs font-bold text-[#6e8a96] uppercase tracking-wider mb-2.5">
            Active Subscription
          </h4>
          {activeSub ? (
            <div className="bg-[#0f2127] border border-[#183642] rounded-xl p-3.5 space-y-2 text-xs">
              <div className="flex items-center justify-between">
                <span className="text-[#8fa7b3]">Plan Tier:</span>
                <Badge variant="brand">{activeSub.plan}</Badge>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-[#8fa7b3]">Status:</span>
                <Badge variant={activeSub.status === "active" ? "success" : "warning"}>
                  {activeSub.status}
                </Badge>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-[#8fa7b3]">Seats Allocated:</span>
                <span className="font-semibold text-white">{activeSub.seats} seats</span>
              </div>
              {activeSub.current_period_end && (
                <div className="flex items-center justify-between pt-1 border-t border-[#183642]">
                  <span className="text-[#8fa7b3]">Renewal Date:</span>
                  <span className="font-medium text-slate-200">
                    {new Date(activeSub.current_period_end).toLocaleDateString()}
                  </span>
                </div>
              )}
            </div>
          ) : (
            <div className="text-xs text-[#7e9aa6] bg-[#0f2127] p-3 rounded-xl border border-[#183642]">
              No active subscription found.
            </div>
          )}
        </div>

        {/* Workspaces */}
        <div>
          <div className="flex items-center justify-between mb-2.5">
            <h4 className="text-3xs font-bold text-[#6e8a96] uppercase tracking-wider">
              Workspaces ({workspaces.length})
            </h4>
          </div>
          {workspaces.length === 0 ? (
            <div className="text-xs text-[#7e9aa6] bg-[#0f2127] p-3 rounded-xl border border-[#183642]">
              No registered workspaces.
            </div>
          ) : (
            <div className="space-y-2">
              {workspaces.map((ws) => {
                const usedMB = (ws.storage_used_bytes / (1024 * 1024)).toFixed(1);
                const limitMB = (ws.storage_limit_bytes / (1024 * 1024)).toFixed(0);
                const percent = Math.min(
                  100,
                  Math.round((ws.storage_used_bytes / (ws.storage_limit_bytes || 1)) * 100)
                );

                return (
                  <div key={ws.id} className="border border-[#183642] bg-[#0f2127] rounded-xl p-3 text-xs">
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="font-bold text-white">{ws.name}</span>
                      <span className="font-mono text-3xs text-[#7e9aa6]">{ws.slug}</span>
                    </div>
                    <div className="flex items-center justify-between text-3xs text-[#7e9aa6] mb-1">
                      <span>Storage: {usedMB} MB / {limitMB} MB</span>
                      <span className="text-[#00d2b4] font-bold">{percent}%</span>
                    </div>
                    <div className="w-full bg-[#081216] rounded-full h-1.5 overflow-hidden">
                      <div
                        className={`h-full ${
                          percent > 90
                            ? "bg-rose-500"
                            : percent > 75
                            ? "bg-amber-400"
                            : "bg-[#00d2b4]"
                        }`}
                        style={{ width: `${percent}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Memory & Relationship Notes */}
        <div>
          <h4 className="text-3xs font-bold text-[#6e8a96] uppercase tracking-wider mb-2.5">
            Memory Notes ({memoryNotes.length})
          </h4>
          {memoryNotes.length === 0 ? (
            <div className="text-xs text-[#7e9aa6] bg-[#0f2127] p-3 rounded-xl border border-[#183642]">
              No historical memory notes stored for this account.
            </div>
          ) : (
            <div className="space-y-2">
              {memoryNotes.map((mem) => (
                <div
                  key={mem.id}
                  className="bg-[#1a1b0e] border border-[#373919] rounded-xl p-3 text-xs space-y-1"
                >
                  <div className="flex items-center justify-between">
                    <Badge variant="warning" size="sm">
                      {mem.memory_type}
                    </Badge>
                    <time className="text-3xs text-[#7e9aa6] font-mono">
                      {new Date(mem.created_at).toLocaleDateString()}
                    </time>
                  </div>
                  <p className="text-slate-200 leading-relaxed font-sans">{mem.content}</p>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Recent Tickets */}
        <div>
          <h4 className="text-3xs font-bold text-[#6e8a96] uppercase tracking-wider mb-2.5">
            Recent Tickets ({recentTickets.length})
          </h4>
          {recentTickets.length === 0 ? (
            <div className="text-xs text-[#7e9aa6] bg-[#0f2127] p-3 rounded-xl border border-[#183642]">
              No prior tickets for this customer.
            </div>
          ) : (
            <div className="space-y-2">
              {recentTickets.slice(0, 5).map((t) => (
                <Link
                  key={t.id}
                  href={`/tickets/${t.id}`}
                  className="block p-2.5 rounded-xl border border-[#183642] bg-[#0f2127] hover:border-[#00d2b4]/40 hover:bg-[#12272e] transition-all text-xs"
                >
                  <div className="flex items-center justify-between gap-1 mb-1">
                    <span className="font-mono text-2xs font-bold text-[#00d2b4]">
                      #{t.id}
                    </span>
                    <StatusPill status={t.status} size="sm" />
                  </div>
                  <p className="text-white font-medium truncate">{t.subject}</p>
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>
    </Card>
  );
}
