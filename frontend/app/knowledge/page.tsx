"use client";

import React, { useState, useEffect, useCallback } from "react";
import { AppShell } from "@/components/layout";
import { api, NetworkError } from "@/lib/api";
import { KnowledgeArticleSummary, KnowledgeEvidence } from "@/lib/types";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { SearchIcon, BookOpenIcon, RefreshCwIcon } from "@/components/layout/Icons";

const FALLBACK_ARTICLES: KnowledgeArticleSummary[] = [
  {
    id: "KB-001",
    slug: "saml-sso-configuration",
    title: "SAML 2.0 Single Sign-On Configuration Guide",
    category: "login_issue",
    tags: ["saml", "sso", "auth", "enterprise"],
    summary: "Step-by-step instructions for configuring Okta, Azure AD, and custom Identity Providers.",
    url: "/knowledge/saml-sso-configuration",
  },
  {
    id: "KB-002",
    slug: "subscription-refund-policy",
    title: "Subscription Billing Cycles and Refund Policy",
    category: "billing",
    tags: ["billing", "refunds", "invoices", "cancellations"],
    summary: "Standard 30-day refund guarantee guidelines, prorated credit rules, and policy thresholds.",
    url: "/knowledge/subscription-refund-policy",
  },
  {
    id: "KB-003",
    slug: "api-rate-limits-webhooks",
    title: "API Rate Limits, Webhook Retries and Status Codes",
    category: "api_failure",
    tags: ["api", "rate-limit", "webhooks", "status-codes"],
    summary: "Rate limit tiers per plan, exponential backoff headers, and HTTP 429 mitigation strategies.",
    url: "/knowledge/api-rate-limits-webhooks",
  },
  {
    id: "KB-004",
    slug: "gdpr-data-portability-erasure",
    title: "GDPR Compliance, Data Portability, and Right to Erasure",
    category: "security",
    tags: ["gdpr", "compliance", "erasure", "legal"],
    summary: "Mandatory compliance procedures for Article 17 deletion requests and specialist routing.",
    url: "/knowledge/gdpr-data-portability-erasure",
  },
];

export default function KnowledgePage() {
  const [articles, setArticles] = useState<KnowledgeArticleSummary[]>([]);
  const [searchResults, setSearchResults] = useState<KnowledgeEvidence[] | null>(null);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);

  const fetchArticles = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.knowledge.listArticles();
      setArticles(res);
    } catch {
      setArticles(FALLBACK_ARTICLES);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchArticles();
  }, [fetchArticles]);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) {
      setSearchResults(null);
      return;
    }

    setSearching(true);
    try {
      const res = await api.knowledge.search({ query: query.trim(), mode: "hybrid", top_k: 5 });
      setSearchResults(res.evidence);
    } catch {
      // Fallback: client-side filter
      const filtered = articles.filter(
        (a) =>
          (a.title || "").toLowerCase().includes(query.toLowerCase()) ||
          (a.summary || "").toLowerCase().includes(query.toLowerCase())
      );
      setSearchResults(
        filtered.map((a) => ({
          id: a.id,
          title: a.title,
          source: a.slug,
          snippet: a.summary || "",
          score: 0.95,
          url: a.url || `/knowledge/${a.slug}`,
          article_id: a.id,
        }))
      );
    } finally {
      setSearching(false);
    }
  };

  const handleClear = () => {
    setQuery("");
    setSearchResults(null);
  };

  return (
    <AppShell pageTitle="Knowledge Base & RAG Index">
      <div className="space-y-6">
        {/* Search & Actions Bar */}
        <form onSubmit={handleSearch} className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-[#0c181d] p-4 rounded-2xl border border-[#162d36] shadow-card">
          <div className="flex-1 max-w-lg flex items-center gap-2">
            <Input
              placeholder="Search knowledge articles with semantic RAG..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              leftIcon={<SearchIcon size={16} />}
            />
            {query && (
              <Button variant="ghost" size="sm" onClick={handleClear}>
                Clear
              </Button>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Button
              type="submit"
              variant="primary"
              size="sm"
              isLoading={searching}
            >
              Search Docs
            </Button>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={fetchArticles}
              isLoading={loading}
              leftIcon={<RefreshCwIcon size={14} />}
            >
              Refresh
            </Button>
          </div>
        </form>

        {/* Semantic Search Results or Article Catalog */}
        {searching ? (
          <div className="py-16 flex flex-col items-center justify-center text-xs text-[#7e9aa6]">
            <span className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-[#00d2b4] border-t-transparent mb-3" />
            Performing hybrid vector search...
          </div>
        ) : searchResults !== null ? (
          <div>
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-xs font-semibold text-[#8ea8b4] uppercase tracking-wider">
                Hybrid Retrieval Results for &ldquo;{query}&rdquo; ({searchResults.length})
              </h3>
              <Button variant="ghost" size="xs" onClick={handleClear}>
                Show all articles
              </Button>
            </div>

            {searchResults.length === 0 ? (
              <EmptyState
                icon={<BookOpenIcon size={24} />}
                title="No matching knowledge articles"
                description={`No indexed chunks matched the semantic query "${query}".`}
                action={
                  <Button variant="secondary" size="sm" onClick={handleClear}>
                    View All Articles
                  </Button>
                }
              />
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {searchResults.map((item, idx) => (
                  <Card key={item.id || item.article_id || `search-${idx}`} padding="md" className="border-[#1b434e] bg-[#0c242b] shadow-glow">
                    <div className="flex items-start justify-between">
                      <div className="flex items-start gap-3">
                        <div className="p-2.5 rounded-xl bg-[#12363f] text-[#00d2b4] border border-[#1b505c] flex-shrink-0">
                          <BookOpenIcon size={18} />
                        </div>
                        <div>
                          <span className="inline-block font-mono text-3xs text-[#00d2b4] bg-[#07181d] px-2 py-0.5 rounded-full border border-[#164a54] mb-1">
                            Relevance: {((item.score ?? 0.9) * 100).toFixed(1)}%
                          </span>
                          <h4 className="text-sm font-semibold text-white leading-snug">{item.title || "Knowledge Document"}</h4>
                        </div>
                      </div>
                    </div>
                    <p className="mt-3 text-xs text-[#9bb3bf] line-clamp-3 leading-relaxed">
                      {item.snippet || (item as unknown as { content?: string }).content || "No snippet available."}
                    </p>
                  </Card>
                ))}
              </div>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {articles.map((art) => (
              <Card key={art.id} padding="md" className="hover:border-[#1e3c48] transition-colors">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-3">
                    <div className="p-2.5 rounded-xl bg-[#122830] text-[#00d2b4] border border-[#1b3d4a] flex-shrink-0">
                      <BookOpenIcon size={18} />
                    </div>
                    <div>
                      <span className="font-mono text-3xs text-[#7e9aa6]">{art.id} · {art.slug}</span>
                      <h4 className="text-sm font-semibold text-white leading-snug">
                        {art.title}
                      </h4>
                    </div>
                  </div>
                </div>

                <p className="mt-3 text-xs text-[#7e9aa6] line-clamp-2 leading-relaxed">
                  {art.summary || "No summary available."}
                </p>

                <div className="mt-4 flex items-center justify-between text-2xs text-[#52707e] border-t border-[#14232a] pt-3">
                  <Badge variant="brand" size="sm">
                    {(art.category || "general").replace(/_/g, " ")}
                  </Badge>
                  <div className="flex items-center gap-1.5">
                    {(art.tags || []).slice(0, 3).map((tag) => (
                      <span key={tag} className="text-3xs text-[#52707e] font-mono">
                        #{tag}
                      </span>
                    ))}
                  </div>
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}
