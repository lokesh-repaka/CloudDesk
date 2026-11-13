"use client";

import React, { useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth, DEMO_USERS_MAP } from "@/lib/auth";
import { Role } from "@/lib/types";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { BotIcon, ShieldIcon, UsersIcon, ArrowRightIcon } from "@/components/layout/Icons";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const reason = searchParams?.get("reason");

  const { login, loginWithDemo, isLoading: authLoading } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) {
      setError("Please enter a valid email address");
      return;
    }

    setError(null);
    setSubmitting(true);
    try {
      await login({ email, password: password || undefined });
      router.push("/dashboard");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to sign in. Please check credentials.";
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  const handleDemoSignIn = async (role: Role) => {
    setError(null);
    setSubmitting(true);
    try {
      await loginWithDemo(role);
      router.push("/dashboard");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to sign in with demo identity.";
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  const isBusy = submitting || authLoading;

  return (
    <div className="min-h-screen bg-[#070d10] flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center">
        {/* Brand Logo & Name */}
        <div className="flex justify-center mb-4">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[#00d2b4] text-[#070d10] shadow-glow font-bold">
            <BotIcon size={26} className="text-[#070d10]" />
          </div>
        </div>
        <h2 className="text-2xl font-bold tracking-tight text-white">
          Sign in to CloudDesk
        </h2>
        <p className="mt-1 text-xs text-[#7e9aa6]">
          AI-orchestrated customer resolution platform with policy-gated automation
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md px-4 sm:px-0">
        <Card padding="lg" className="rounded-2xl border-[#182c34] bg-[#0e181c] shadow-card">
          {/* Reason Notification Banner */}
          {reason === "expired" && (
            <div className="mb-4">
              <Alert variant="warning" title="Session Expired">
                Your authentication session has expired. Please sign in again to continue.
              </Alert>
            </div>
          )}

          {error && (
            <div className="mb-4">
              <Alert variant="danger" title="Sign In Error">
                {error}
              </Alert>
            </div>
          )}

          {/* Quick Demo Access Section */}
          <div className="mb-6 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-white uppercase tracking-wider">
                Fast Demo Access
              </span>
              <Badge variant="neutral" size="sm">DEMO MODE</Badge>
            </div>
            <p className="text-2xs text-[#7e9aa6]">
              Select a pre-configured role to immediately explore the console with mock offline workflows:
            </p>

            <div className="grid grid-cols-1 gap-2 pt-1">
              <button
                type="button"
                disabled={isBusy}
                onClick={() => handleDemoSignIn("admin")}
                className="flex items-center justify-between p-3.5 rounded-xl border border-[#162d36] bg-[#0c181d] hover:bg-[#122228] text-left transition-colors cursor-pointer disabled:opacity-50"
              >
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-[#2e1d42] text-[#c084fc] border border-[#48286a]">
                    <ShieldIcon size={16} />
                  </div>
                  <div>
                    <div className="text-xs font-semibold text-white">
                      Alice Admin
                    </div>
                    <div className="text-2xs text-[#7e9aa6] font-mono">
                      admin@clouddesk.demo
                    </div>
                  </div>
                </div>
                <Badge variant="warning" size="sm">ADMIN</Badge>
              </button>

              <button
                type="button"
                disabled={isBusy}
                onClick={() => handleDemoSignIn("agent")}
                className="flex items-center justify-between p-3.5 rounded-xl border border-[#162d36] bg-[#0c181d] hover:bg-[#122228] text-left transition-colors cursor-pointer disabled:opacity-50"
              >
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-[#102d33] text-[#00d2b4] border border-[#184650]">
                    <BotIcon size={16} />
                  </div>
                  <div>
                    <div className="text-xs font-semibold text-white">
                      Sam Agent
                    </div>
                    <div className="text-2xs text-[#7e9aa6] font-mono">
                      sam.agent@clouddesk.demo
                    </div>
                  </div>
                </div>
                <Badge variant="brand" size="sm">AGENT</Badge>
              </button>

              <button
                type="button"
                disabled={isBusy}
                onClick={() => handleDemoSignIn("viewer")}
                className="flex items-center justify-between p-3.5 rounded-xl border border-[#162d36] bg-[#0c181d] hover:bg-[#122228] text-left transition-colors cursor-pointer disabled:opacity-50"
              >
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-[#14232a] text-[#8ea8b4] border border-[#1d3540]">
                    <UsersIcon size={16} />
                  </div>
                  <div>
                    <div className="text-xs font-semibold text-white">
                      Vic Viewer
                    </div>
                    <div className="text-2xs text-[#7e9aa6] font-mono">
                      vic.viewer@clouddesk.demo
                    </div>
                  </div>
                </div>
                <Badge variant="neutral" size="sm">VIEWER</Badge>
              </button>
            </div>
          </div>

          <div className="relative my-6">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-[#182c34]" />
            </div>
            <div className="relative flex justify-center text-xs">
              <span className="bg-[#0e181c] px-3 text-[#52707e] font-medium">Or sign in with email</span>
            </div>
          </div>

          {/* Standard Login Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <Input
              label="Email address"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="name@company.com"
              required
              disabled={isBusy}
            />

            <Input
              label="Password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="•••••••• (optional in demo)"
              disabled={isBusy}
            />

            <Button
              type="submit"
              variant="primary"
              size="md"
              isLoading={isBusy}
              className="w-full mt-2"
              rightIcon={<ArrowRightIcon size={14} />}
            >
              Sign In
            </Button>
          </form>
        </Card>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-[#070d10]" />}>
      <LoginForm />
    </Suspense>
  );
}
