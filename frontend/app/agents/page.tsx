"use client";

import React, { useState, useEffect, useCallback } from "react";
import { AppShell } from "@/components/layout";
import { api } from "@/lib/api";
import { AgentTopologyResponse, SpecialistAgentResponse } from "@/lib/types";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { StatusPill } from "@/components/ui/StatusPill";
import { BotIcon, CpuIcon, RefreshCwIcon } from "@/components/layout/Icons";

const FALLBACK_SPECIALISTS: SpecialistAgentResponse[] = [
  {
    name: "SupervisorAgent",
    description: "Triage, category understanding, deterministic severity classification, and ticket summary wrap-up.",
    nodes: ["understand_ticket", "classify_severity", "ticket_summary"],
    tools: [],
    rules: ["RULE_SEV_FLOOR_ENTERPRISE", "RULE_SEV_FLOOR_CRITICAL_WORDS"],
  },
  {
    name: "CustomerAgent",
    description: "Retrieves customer 360 profile, active subscription limits, ticket history, and past issue memory.",
    nodes: ["customer_context"],
    tools: ["get_customer_dossier"],
    rules: ["RULE_CUSTOMER_ARR_PRIORITY"],
  },
  {
    name: "KnowledgeAgent",
    description: "Hybrid dense semantic vector retrieval and BM25 token search with Reciprocal Rank Fusion.",
    nodes: ["knowledge_retrieval"],
    tools: ["search_docs"],
    rules: ["RULE_HYBRID_RRF_MERGE"],
  },
  {
    name: "TroubleshootingAgent",
    description: "Platform health diagnostics, active incident correlation, and numbered step-by-step reproduction.",
    nodes: ["troubleshooting"],
    tools: ["check_service_status"],
    rules: ["RULE_CATEGORY_PLAYBOOK_BINDING"],
  },
  {
    name: "ResolutionAgent",
    description: "Deterministic action generation, grounded customer reply formulation, and human approval gating.",
    nodes: ["resolution_planning", "risk_check", "human_approval", "execute_resolution", "memory_update"],
    tools: ["update_ticket", "create_refund_request", "reset_demo_setting"],
    rules: ["RULE_REFUND_ALWAYS_GATED", "RULE_QUARANTINE_UNSAFE_DRAFTS"],
  },
  {
    name: "EscalationAgent",
    description: "Deterministic policy routing to specialized human engineering, security, and compliance teams.",
    nodes: ["escalation"],
    tools: ["create_escalation_record"],
    rules: ["ESC-001_GDPR_ERASURE", "ESC-002_CREDENTIAL_STUFFING", "ESC-003_OUTAGE_P1"],
  },
];

export default function AgentsPage() {
  const [topology, setTopology] = useState<AgentTopologyResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchTopology = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.agents.getTopology();
      setTopology(res);
    } catch {
      setTopology({
        nodes: [
          "understand_ticket",
          "classify_severity",
          "customer_context",
          "knowledge_retrieval",
          "troubleshooting",
          "resolution_planning",
          "risk_check",
          "human_approval",
          "execute_resolution",
          "escalation",
          "ticket_summary",
          "memory_update",
        ],
        edges: [
          ["understand_ticket", "classify_severity"],
          ["classify_severity", "customer_context"],
          ["customer_context", "knowledge_retrieval"],
          ["knowledge_retrieval", "troubleshooting"],
          ["troubleshooting", "resolution_planning"],
          ["resolution_planning", "risk_check"],
        ],
        specialists: FALLBACK_SPECIALISTS,
      });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTopology();
  }, [fetchTopology]);

  const specialists = topology?.specialists || FALLBACK_SPECIALISTS;
  const nodes = topology?.nodes || [];

  return (
    <AppShell pageTitle="Specialist Agents & Graph Topology">
      <div className="space-y-6">
        {/* Header Summary */}
        <div className="bg-white p-5 rounded-lg border border-slate-200 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-lg bg-brand-50 text-brand-600">
              <CpuIcon size={22} />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-900">
                Multi-Agent LangGraph Topology (CLAUDE.md §8)
              </h2>
              <p className="text-2xs text-slate-500 mt-0.5">
                {specialists.length} specialized agents coordinating across {nodes.length} stateful graph nodes.
              </p>
            </div>
          </div>

          <Button
            variant="secondary"
            size="sm"
            onClick={fetchTopology}
            isLoading={loading}
            leftIcon={<RefreshCwIcon size={14} />}
          >
            Refresh Topology
          </Button>
        </div>

        {/* Nodes Chip Row */}
        {nodes.length > 0 && (
          <Card padding="sm">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-3xs font-semibold uppercase tracking-wider text-slate-500">
                StateGraph Execution Pipeline:
              </span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {nodes.map((node, i) => (
                <span
                  key={node}
                  className="inline-flex items-center px-2 py-0.5 rounded text-2xs font-mono bg-slate-100 text-slate-700 border border-slate-200"
                >
                  <span className="text-slate-400 mr-1">{i + 1}.</span> {node}
                </span>
              ))}
            </div>
          </Card>
        )}

        {/* Specialists Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {specialists.map((agent) => (
            <Card key={agent.name} padding="md" className="flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="p-1.5 rounded bg-brand-50 text-brand-600">
                    <BotIcon size={16} />
                  </div>
                  <StatusPill status="online" size="sm" />
                </div>
                <h4 className="text-xs font-bold text-slate-900">{agent.name}</h4>
                <p className="text-2xs text-slate-600 leading-relaxed mt-1">
                  {agent.description}
                </p>

                {/* Nodes Managed */}
                <div className="mt-3">
                  <div className="text-3xs font-semibold text-slate-400 uppercase tracking-wider mb-1">
                    Managed Nodes:
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {agent.nodes.map((node) => (
                      <span
                        key={node}
                        className="px-1.5 py-0.2 rounded text-3xs font-mono bg-slate-100 text-slate-600 border border-slate-200"
                      >
                        {node}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              {/* Tools & Rules Footer */}
              <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-3xs">
                <span className="text-slate-500">
                  {agent.tools.length} Tools · {agent.rules.length} Rules
                </span>
                <Badge variant="neutral" size="sm">
                  Active
                </Badge>
              </div>
            </Card>
          ))}
        </div>
      </div>
    </AppShell>
  );
}
