"use client";

import React from "react";
import { useAuth } from "@/lib/auth";
import { Role } from "@/lib/types";

export interface RoleGuardProps {
  minRole?: Role;
  allowedRoles?: Role[];
  fallback?: React.ReactNode;
  children: React.ReactNode;
}

const ROLE_RANK: Record<Role, number> = {
  viewer: 1,
  agent: 2,
  admin: 3,
};

/**
 * Role-Based Access Control wrapper for conditionally rendering UI components.
 */
export function RoleGuard({
  minRole,
  allowedRoles,
  fallback = null,
  children,
}: RoleGuardProps) {
  const { role, isLoading } = useAuth();

  if (isLoading) {
    return null;
  }

  // Check specific allowed roles list if provided
  if (allowedRoles && allowedRoles.length > 0) {
    if (!allowedRoles.includes(role)) {
      return <>{fallback}</>;
    }
    return <>{children}</>;
  }

  // Check minimum role rank
  if (minRole) {
    const userRank = ROLE_RANK[role] ?? 1;
    const requiredRank = ROLE_RANK[minRole] ?? 1;
    if (userRank < requiredRank) {
      return <>{fallback}</>;
    }
  }

  return <>{children}</>;
}

