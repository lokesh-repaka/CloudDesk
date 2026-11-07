"use client";

import React from "react";
import { AppShell } from "@/components/layout";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { StatusPill } from "@/components/ui/StatusPill";
import { BotIcon, CpuIcon } from "@/components/layout/Icons";

export default function AgentsPage() {
  const agents = [
    {
      name: "Triage Agent",
      role: "Intake & Classification",
      category: "10 Standard Categories",
      description: "Extracts customer intent, assesses initial severity, runs input sanitization guardrails.",
      status: "online",
    },
    {
      name: "Policy Agent",
      role: "Deterministic Governance",
      category: "Rules Engine",
      description: "Evaluates hard security, financial refund limits, and compliance escalation policies.",
      status: "online",
    },
    {
      name: "Customer Agent",
      role: "Context & Memory",
      category: "Dossier Retrieval",
      description: "Retrieves customer subscription tier, historical ticket precedents, and past issue memory.",
      status: "online",
    },
    {
      name: "Knowledge Agent",
      role: "Hybrid RAG Pipeline",
      category: "Vector & BM25 Search",
      description: "Performs dense semantic search and BM25 token retrieval with Reciprocal Rank Fusion.",
      status: "online",
    },
    {
      name: "Troubleshooting Agent",
      role: "Diagnostic Reasoning",
      category: "Root-Cause Analysis",
      description: "Synthesizes diagnostic hypotheses, analyzes error payloads, produces numbered reproduction steps.",
      status: "online",
    },
    {
      name: "Resolution Agent",
      role: "Action Planning",
      category: "Action Generation",
      description: "Proposes grounded customer communications, refund recommendations, and account updates.",
      status: "online",
    },
    {
      name: "Communication Agent",
      role: "Response Synthesis",
      category: "Customer Delivery",
      description: "Formats professional, empathetic responses with clear diagnostic steps and next actions.",
      status: "online",
    },
    {
      name: "Memory Agent",
      role: "Continuous Learning",
      category: "Customer Memory",
      description: "Persists structured resolution notes and key customer preferences to prevent repeated inquiries.",
      status: "online",
    },
  ];

  return (
    <AppShell pageTitle="Specialist Agents & Graph Topology" userRole="viewer">
      <div className="space-y-6">
        <div className="bg-white p-5 rounded-lg border border-slate-200">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-lg bg-brand-50 text-brand-600">
              <CpuIcon size={20} />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-900">
                Multi-Agent LangGraph Topology (CLAUDE.md §8)
              </h2>
              <p className="text-2xs text-slate-500 mt-0.5">
                8 specialized agents collaborate in an orchestrated stateful workflow graph with human-in-the-loop checkpoints.
              </p>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {agents.map((agent) => (
            <Card key={agent.name} padding="md" className="flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="p-1.5 rounded bg-slate-100 text-slate-600">
                    <BotIcon size={16} />
                  </div>
                  <StatusPill status={agent.status} size="sm" />
                </div>
                <h4 className="text-xs font-bold text-slate-900">{agent.name}</h4>
                <p className="text-2xs font-medium text-brand-600 mb-2">{agent.role}</p>
                <p className="text-2xs text-slate-600 leading-relaxed">{agent.description}</p>
              </div>
              <div className="mt-4 pt-3 border-t border-slate-100">
                <Badge variant="neutral" size="sm">
                  {agent.category}
                </Badge>
              </div>
            </Card>
          ))}
        </div>
      </div>
    </AppShell>
  );
}

