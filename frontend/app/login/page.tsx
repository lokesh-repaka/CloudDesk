"use client";

import React, { useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth, DEMO_USERS_MAP } from "@/lib/auth";
import { Role } from "@/lib/types";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
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
    <div className="min-h-screen bg-slate-50 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center">
        {/* Brand Logo & Name */}
        <div className="flex justify-center mb-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-brand-600 text-white shadow-sm font-bold">
            <BotIcon size={28} className="text-white" />
          </div>
        </div>
        <h2 className="text-2xl font-bold tracking-tight text-slate-900">
          Sign in to CloudDesk
        </h2>
        <p className="mt-1 text-xs text-slate-500">
          AI-orchestrated customer resolution platform with policy-gated automation
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md px-4 sm:px-0">
        <Card padding="lg">
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
              <span className="text-xs font-semibold text-slate-800 uppercase tracking-wider">
                Fast Demo Access
              </span>
              <Badge variant="neutral" size="sm">DEMO MODE</Badge>
            </div>
            <p className="text-2xs text-slate-500">
              Select a pre-configured role to immediately explore the console with mock offline workflows:
            </p>

            <div className="grid grid-cols-1 gap-2 pt-1">
              <button
                type="button"
                disabled={isBusy}
                onClick={() => handleDemoSignIn("admin")}
                className="flex items-center justify-between p-3 rounded-md border border-slate-200 bg-white hover:bg-slate-50 text-left transition-colors cursor-pointer disabled:opacity-50"
              >
                <div className="flex items-center gap-2.5">
                  <div className="p-1.5 rounded bg-purple-50 text-purple-700">
                    <ShieldIcon size={16} />
                  </div>
                  <div>
                    <div className="text-xs font-semibold text-slate-900">
                      Alice Admin
                    </div>
                    <div className="text-2xs text-slate-500 font-mono">
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
                className="flex items-center justify-between p-3 rounded-md border border-slate-200 bg-white hover:bg-slate-50 text-left transition-colors cursor-pointer disabled:opacity-50"
              >
                <div className="flex items-center gap-2.5">
                  <div className="p-1.5 rounded bg-brand-50 text-brand-700">
                    <BotIcon size={16} />
                  </div>
                  <div>
                    <div className="text-xs font-semibold text-slate-900">
                      Sam Agent
                    </div>
                    <div className="text-2xs text-slate-500 font-mono">
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
                className="flex items-center justify-between p-3 rounded-md border border-slate-200 bg-white hover:bg-slate-50 text-left transition-colors cursor-pointer disabled:opacity-50"
              >
                <div className="flex items-center gap-2.5">
                  <div className="p-1.5 rounded bg-slate-100 text-slate-700">
                    <UsersIcon size={16} />
                  </div>
                  <div>
                    <div className="text-xs font-semibold text-slate-900">
                      Vic Viewer
                    </div>
                    <div className="text-2xs text-slate-500 font-mono">
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
              <div className="w-full border-t border-slate-200" />
            </div>
            <div className="relative flex justify-center text-xs">
              <span className="bg-white px-2 text-slate-400 font-medium">Or sign in with email</span>
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
    <Suspense fallback={<div className="min-h-screen bg-slate-50" />}>
      <LoginForm />
    </Suspense>
  );
}
