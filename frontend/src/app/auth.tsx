import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ApiError, onUnauthorized, setLegacyToken } from "../api/client";
import { api } from "../api/endpoints";
import type { DashboardRole, FleetNode } from "../api/types";

export interface Identity {
  userId: string | null;
  username: string;
  role: DashboardRole;
  /** A personal account (not an admin-code or token session). */
  personal: boolean;
  fullStatistics: boolean;
}

export type AuthStatus = "checking" | "offline" | "anonymous" | "ready";

interface AuthValue {
  status: AuthStatus;
  identity: Identity | null;
  /** Re-reads the session; resolves to the new status. */
  refresh: () => Promise<AuthStatus>;
  logout: () => Promise<void>;
  signInWithToken: (token: string) => Promise<AuthStatus>;
  /** Set when a 401 ended a running session. */
  expired: boolean;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<AuthStatus>("checking");
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [expired, setExpired] = useState(false);
  const statusRef = useRef(status);
  statusRef.current = status;
  const epoch = useRef(0);

  const refresh = useCallback(async (): Promise<AuthStatus> => {
    const mine = ++epoch.current;
    try {
      // Both endpoints describe the session: access carries the role used by
      // require_*_access, me the name and whether it is a personal account.
      const [access, me] = await Promise.all([api.auth.access(), api.auth.me()]);
      if (mine !== epoch.current) return statusRef.current;
      setIdentity({
        userId: me.user_id,
        username: me.username,
        role: access.access_role,
        personal: me.user_id !== null,
        fullStatistics: me.full_statistics,
      });
      setExpired(false);
      setStatus("ready");
      return "ready";
    } catch (error) {
      if (mine !== epoch.current) return statusRef.current;
      const next: AuthStatus = error instanceof ApiError && error.offline ? "offline" : "anonymous";
      if (next === "anonymous") setIdentity(null);
      setStatus(next);
      return next;
    }
  }, []);

  useEffect(() => {
    onUnauthorized(() => {
      // Only a running session can expire; login screens never loop.
      if (statusRef.current !== "ready") return;
      epoch.current += 1;
      setLegacyToken(null);
      setIdentity(null);
      setExpired(true);
      setStatus("anonymous");
      queryClient.cancelQueries();
      queryClient.clear();
    });
    void refresh();
    return () => onUnauthorized(null);
  }, [queryClient, refresh]);

  const logout = useCallback(async () => {
    try {
      await api.auth.logout();
    } finally {
      epoch.current += 1;
      setLegacyToken(null);
      setIdentity(null);
      setExpired(false);
      setStatus("anonymous");
      queryClient.cancelQueries();
      queryClient.clear();
    }
  }, [queryClient]);

  const signInWithToken = useCallback(async (token: string) => {
    setLegacyToken(token);
    const result = await refresh();
    if (result !== "ready") setLegacyToken(null);
    return result;
  }, [refresh]);

  const value = useMemo(() => ({ status, identity, refresh, logout, signInWithToken, expired }), [status, identity, refresh, logout, signInWithToken, expired]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth outside AuthProvider");
  return value;
}

/**
 * What the current identity may do. Mirrors require_commander_access,
 * require_staff_access and access.manageable_node (see API-MATRIX.md).
 */
export interface Can {
  role: DashboardRole;
  commander: boolean;
  team: boolean;
  friend: boolean;
  beta: boolean;
  personal: boolean;
  manage: (node: Pick<FleetNode, "owner_user_id"> | null | undefined) => boolean;
}

export function useCan(): Can {
  const { identity } = useAuth();
  return useMemo(() => {
    const role = identity?.role ?? "friend";
    const commander = role === "commander";
    return {
      role,
      commander,
      team: role !== "friend",
      friend: role === "friend",
      beta: role === "beta_tester",
      personal: identity?.personal ?? false,
      manage: (node) => commander || (role === "friend" && !!identity?.userId && node?.owner_user_id === identity.userId),
    };
  }, [identity]);
}

export function roleLabel(role: DashboardRole): string {
  return { commander: "Commander", beta_tester: "Beta-Tester", friend: "Freund" }[role];
}
