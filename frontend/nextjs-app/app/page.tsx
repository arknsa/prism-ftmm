"use client";

import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { apiBaseUrl, getHealth, type HealthResponse } from "@/lib/api-client";

type HealthState =
  { kind: "loading" } | { kind: "ok"; data: HealthResponse } | { kind: "error"; message: string };

export default function Home() {
  const [state, setState] = useState<HealthState>({ kind: "loading" });

  const checkHealth = useCallback(async () => {
    setState({ kind: "loading" });
    try {
      const data = await getHealth();
      setState({ kind: "ok", data });
    } catch (error) {
      setState({
        kind: "error",
        message: error instanceof Error ? error.message : "Unknown error",
      });
    }
  }, []);

  useEffect(() => {
    let active = true;
    void getHealth()
      .then((data) => {
        if (active) setState({ kind: "ok", data });
      })
      .catch((error: unknown) => {
        if (active) {
          setState({
            kind: "error",
            message: error instanceof Error ? error.message : "Unknown error",
          });
        }
      });
    return () => {
      active = false;
    };
  }, []);

  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col justify-center gap-8 p-8">
      <header className="space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">FTMM Alumni Intelligence Dashboard</h1>
        <p className="text-muted-foreground">
          Phase 0 shell — analytics &amp; reporting platform for FTMM, Universitas Airlangga.
        </p>
      </header>

      <section className="bg-card text-card-foreground rounded-lg border p-6 shadow-sm">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Backend health</h2>
          <Button variant="outline" size="sm" onClick={() => void checkHealth()}>
            Re-check
          </Button>
        </div>
        <p className="text-muted-foreground mt-1 text-sm">
          Fetched through the typed API client from <code>{apiBaseUrl}/health</code>.
        </p>

        <div className="mt-4 text-sm">
          {state.kind === "loading" && <span className="text-muted-foreground">Checking…</span>}

          {state.kind === "error" && (
            <span className="text-destructive">Backend unreachable: {state.message}</span>
          )}

          {state.kind === "ok" && (
            <dl className="grid grid-cols-2 gap-2">
              <dt className="text-muted-foreground">Status</dt>
              <dd className="font-medium">{state.data.status}</dd>
              <dt className="text-muted-foreground">Environment</dt>
              <dd className="font-medium">{state.data.app_env}</dd>
              <dt className="text-muted-foreground">Database</dt>
              <dd className="font-medium">{state.data.database}</dd>
            </dl>
          )}
        </div>
      </section>
    </main>
  );
}
