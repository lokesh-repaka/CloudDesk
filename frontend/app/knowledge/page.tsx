"use client";

import React, { useState } from "react";
import { AppShell } from "@/components/layout";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Badge } from "@/components/ui/Badge";
import { SearchIcon, BookOpenIcon, RefreshCwIcon } from "@/components/layout/Icons";

export default function KnowledgePage() {
  const [query, setQuery] = useState("");

  const articles = [
    {
      id: "KB-001",
      title: "SAML 2.0 Single Sign-On Configuration Guide",
      category: "login_issue",
      chunks: 8,
      updatedAt: "2 days ago",
    },
    {
      id: "KB-002",
      title: "Subscription Billing Cycles and Refund Policy",
      category: "billing",
      chunks: 6,
      updatedAt: "1 week ago",
    },
    {
      id: "KB-003",
      title: "API Rate Limits, Webhook Retries and Status Codes",
      category: "api_failure",
      chunks: 12,
      updatedAt: "3 days ago",
    },
    {
      id: "KB-004",
      title: "GDPR Compliance, Data Portability, and Right to Erasure",
      category: "security",
      chunks: 9,
      updatedAt: "Yesterday",
    },
  ];

  return (
    <AppShell pageTitle="Knowledge Base & RAG Index" userRole="viewer">
      <div className="space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="flex-1 max-w-md">
            <Input
              placeholder="Search knowledge articles, vectors, or keywords..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              leftIcon={<SearchIcon size={16} />}
            />
          </div>
          <div className="flex items-center gap-2">
            <Button variant="secondary" size="sm" leftIcon={<RefreshCwIcon size={14} />}>
              Vector Index Status: Synced
            </Button>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {articles.map((art) => (
            <Card key={art.id} padding="md" className="hover:border-slate-300 transition-colors">
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-2">
                  <div className="p-2 rounded bg-brand-50 text-brand-600">
                    <BookOpenIcon size={16} />
                  </div>
                  <div>
                    <span className="font-mono text-3xs text-slate-400">{art.id}</span>
                    <h4 className="text-sm font-semibold text-slate-900 leading-snug">
                      {art.title}
                    </h4>
                  </div>
                </div>
              </div>
              <div className="mt-4 flex items-center justify-between text-2xs text-slate-500 border-t border-slate-100 pt-3">
                <Badge variant="neutral" size="sm">
                  {art.category.replace(/_/g, " ")}
                </Badge>
                <span>{art.chunks} vector chunks indexed</span>
              </div>
            </Card>
          ))}
        </div>
      </div>
    </AppShell>
  );
}

