"use client";

import React from "react";
import { AppShell } from "@/components/layout";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Badge } from "@/components/ui/Badge";
import { RefreshCwIcon, ShieldIcon } from "@/components/layout/Icons";

export default function SettingsPage() {
  return (
    <AppShell pageTitle="System Settings & Administration" userRole="admin">
      <div className="space-y-6">
        <div className="flex items-center justify-between p-4 rounded-lg border border-amber-200 bg-amber-50/60">
          <div className="flex items-center gap-2">
            <ShieldIcon size={18} className="text-amber-700" />
            <div>
              <h3 className="text-xs font-semibold text-amber-900">Administrator Controls</h3>
              <p className="text-2xs text-amber-800">
                You are authenticated with role <span className="font-bold">admin</span>. All settings are configurable.
              </p>
            </div>
          </div>
          <Badge variant="warning" size="sm">ADMIN ONLY</Badge>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card>
            <CardHeader>
              <div>
                <CardTitle>Vector Store & Knowledge Base</CardTitle>
                <CardDescription>Manage embedding index, chunking, and search parameters</CardDescription>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <Input
                  label="Collection Name"
                  defaultValue="clouddesk_knowledge"
                  disabled
                  helperText="Qdrant / Memory collection name"
                />
                <Input
                  label="Embedding Model"
                  defaultValue="text-embedding-3-small (1536 dim)"
                  disabled
                />
                <div className="pt-2">
                  <Button variant="secondary" size="sm" leftIcon={<RefreshCwIcon size={14} />}>
                    Trigger Knowledge Reindexing
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div>
                <CardTitle>LLM Provider & Safety Thresholds</CardTitle>
                <CardDescription>Operational model runtime parameters</CardDescription>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <Input
                  label="Active Provider"
                  defaultValue="fake (Demo Offline Mode)"
                  disabled
                  helperText="Configured via LLM_PROVIDER in .env"
                />
                <Input
                  label="Max Refund Threshold"
                  defaultValue="$0.00 (All refunds require approval)"
                  disabled
                  helperText="APPROVAL_REQUIRED_FOR_REFUNDS=true"
                />
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </AppShell>
  );
}

