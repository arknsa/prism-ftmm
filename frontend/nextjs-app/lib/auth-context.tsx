"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { useRouter } from "next/navigation";

import { getMe, type MeResponse, ApiError } from "@/lib/api-client";
import { getSupabaseBrowserClient } from "@/lib/supabase/client";

export type AuthenticatedUser = MeResponse;

type AuthState =
  | { status: "loading" }
  | { status: "authenticated"; user: AuthenticatedUser }
  | { status: "error" };

type AuthContextValue = {
  user: AuthenticatedUser | null;
  isLoading: boolean;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [state, setState] = useState<AuthState>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;

    getMe()
      .then((user) => {
        if (!cancelled) setState({ status: "authenticated", user });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) {
          const supabase = getSupabaseBrowserClient();
          void supabase.auth.signOut().then(() => {
            if (!cancelled) router.replace("/login");
          });
        } else {
          console.error(
            "[AuthContext] Failed to load user session:",
            err instanceof Error ? err.message : err,
          );
          setState({ status: "error" });
        }
      });

    return () => {
      cancelled = true;
    };
  }, [router]);

  const value: AuthContextValue = {
    user: state.status === "authenticated" ? state.user : null,
    isLoading: state.status === "loading",
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (ctx === null) {
    throw new Error("useAuth must be used inside <AuthProvider>.");
  }
  return ctx;
}
