"use client";

/**
 * CloudDesk Support Platform — Authentication Context & Role Gating (CLAUDE.md §9, §11)
 *
 * Provides application-wide authentication state, demo identities,
 * session token storage, and hierarchical role-based permissions (canAct, canAdmin).
 */

import React, {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  useMemo,
} from "react";
import { useRouter } from "next/navigation";
import { api, getToken, setToken, clearToken } from "./api";
import {
  LoginRequest,
  Role,
  TokenResponse,
  UserProfileResponse,
} from "./types";

export interface AuthContextType {
  user: UserProfileResponse | null;
  token: string | null;
  role: Role;
  isLoading: boolean;
  isAuthenticated: boolean;
  canAct: boolean;
  canAdmin: boolean;
  login: (credentials: LoginRequest) => Promise<TokenResponse>;
  loginWithDemo: (role: Role) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Canonical demo identities
export const DEMO_USERS_MAP: Record<
  Role,
  { email: string; name: string; role: Role }
> = {
  admin: {
    email: "admin@clouddesk.demo",
    name: "Alice Admin",
    role: "admin",
  },
  agent: {
    email: "sam.agent@clouddesk.demo",
    name: "Sam Agent",
    role: "agent",
  },
  viewer: {
    email: "vic.viewer@clouddesk.demo",
    name: "Vic Viewer",
    role: "viewer",
  },
};

const ROLE_RANK: Record<Role, number> = {
  viewer: 1,
  agent: 2,
  admin: 3,
};

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setTokenState] = useState<string | null>(null);
  const [user, setUser] = useState<UserProfileResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const router = useRouter();

  // On mount: restore session from localStorage and verify profile
  useEffect(() => {
    let isMounted = true;

    async function initSession() {
      const storedToken = getToken();
      if (!storedToken) {
        if (isMounted) {
          setIsLoading(false);
        }
        return;
      }

      setTokenState(storedToken);

      try {
        const profile = await api.auth.getMe();
        if (isMounted) {
          setUser(profile);
        }
      } catch (err) {
        // If token is invalid or expired, clear session
        clearToken();
        if (isMounted) {
          setTokenState(null);
          setUser(null);
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    initSession();

    return () => {
      isMounted = false;
    };
  }, []);

  const login = useCallback(async (credentials: LoginRequest): Promise<TokenResponse> => {
    setIsLoading(true);
    try {
      const response = await api.auth.login(credentials);
      setToken(response.access_token);
      setTokenState(response.access_token);
      setUser(response.user);
      return response;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const loginWithDemo = useCallback(async (selectedRole: Role): Promise<void> => {
    setIsLoading(true);
    try {
      // First attempt to fetch live demo tokens
      const demoTokens = await api.auth.getDemoTokens();
      const target = demoTokens[selectedRole];
      if (target) {
        setToken(target.token);
        setTokenState(target.token);
        setUser({
          id: target.id,
          email: target.email,
          full_name: target.full_name,
          role: selectedRole,
        });
        return;
      }
    } catch {
      // Fallback: regular login with demo credentials
      const demoUser = DEMO_USERS_MAP[selectedRole];
      const res = await api.auth.login({ email: demoUser.email });
      setToken(res.access_token);
      setTokenState(res.access_token);
      setUser(res.user);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const logout = useCallback(() => {
    clearToken();
    setTokenState(null);
    setUser(null);
    if (typeof window !== "undefined") {
      router.push("/login");
    }
  }, [router]);

  const activeRole: Role = user?.role || "viewer";

  // Role gating logic: viewer cannot act per CLAUDE.md §11 & AC-054
  const canAct = useMemo(() => {
    return activeRole !== "viewer" && ROLE_RANK[activeRole] >= ROLE_RANK.agent;
  }, [activeRole]);

  const canAdmin = useMemo(() => {
    return activeRole === "admin";
  }, [activeRole]);

  const value = useMemo<AuthContextType>(
    () => ({
      user,
      token,
      role: activeRole,
      isLoading,
      isAuthenticated: Boolean(token && user),
      canAct,
      canAdmin,
      login,
      loginWithDemo,
      logout,
    }),
    [user, token, activeRole, isLoading, canAct, canAdmin, login, loginWithDemo, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}

