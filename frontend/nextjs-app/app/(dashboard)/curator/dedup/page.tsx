"use client";

/**
 * P4.9 — Dedup review screen.
 *
 * Shows pending Tier-2 dedup candidate pairs. The curator confirms whether
 * to merge (same person) or keep-separate (distinct people).
 *
 * Permission required: dedup:review
 */

import { useCallback, useEffect, useState } from "react";

import { Unauthorized } from "@/components/unauthorized";
import { Button } from "@/components/ui/button";
import { apiFetchWithAuth } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface DedupCandidate {
  dedup_candidate_id: number;
  staging_row_id: number;
  matched_alumni_id: number;
  resolution: string;
  resolved_by: number | null;
  resolved_at: string | null;
  created_at: string;
}

interface DedupListResponse {
  total: number;
  items: DedupCandidate[];
}

interface ResolveResponse {
  dedup_candidate_id: number;
  resolution: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function DedupPage() {
  const { user, isLoading } = useAuth();

  const [candidates, setCandidates] = useState<DedupCandidate[]>([]);
  const [fetching, setFetching] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [actionState, setActionState] = useState<
    Record<number, "idle" | "loading" | "done" | "error">
  >({});

  const load = useCallback(() => {
    setFetching(true);
    setFetchError(null);
    apiFetchWithAuth<DedupListResponse>("/api/v1/dedup/candidates")
      .then((data) => {
        setCandidates(data.items);
        setFetching(false);
      })
      .catch((err: unknown) => {
        setFetchError(err instanceof Error ? err.message : "Failed to load.");
        setFetching(false);
      });
  }, []);

  useEffect(() => {
    if (user && user.permissions.includes("dedup:review")) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      load();
    }
  }, [user, load]);

  const handleResolve = useCallback(
    (candidateId: number, resolution: "merge" | "keep_separate") => {
      setActionState((prev) => ({ ...prev, [candidateId]: "loading" }));
      apiFetchWithAuth<ResolveResponse>(
        `/api/v1/dedup/candidates/${candidateId}/resolve`,
        {
          method: "POST",
          body: JSON.stringify({ resolution }),
        },
      )
        .then(() => {
          setActionState((prev) => ({ ...prev, [candidateId]: "done" }));
          setCandidates((prev) =>
            prev.filter((c) => c.dedup_candidate_id !== candidateId),
          );
        })
        .catch((err: unknown) => {
          console.error(err);
          setActionState((prev) => ({ ...prev, [candidateId]: "error" }));
        });
    },
    [],
  );

  if (isLoading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <span className="text-muted-foreground text-sm">Loading…</span>
      </div>
    );
  }

  if (!user || !user.permissions.includes("dedup:review")) {
    return <Unauthorized />;
  }

  return (
    <div className="mx-auto max-w-3xl p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Dedup Review</h1>
          <p className="text-muted-foreground mt-1 text-sm">
            Review Tier-2 candidate matches (name+program+year). Confirm if two
            records refer to the same person (merge) or are distinct
            (keep-separate). No auto-merge occurs without your decision (D-045).
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={load} disabled={fetching}>
          {fetching ? "Refreshing…" : "Refresh"}
        </Button>
      </div>

      {fetchError && (
        <div className="bg-destructive/10 text-destructive mt-4 rounded-md p-3 text-sm">
          {fetchError}
        </div>
      )}

      {!fetching && candidates.length === 0 && !fetchError && (
        <div className="text-muted-foreground mt-8 text-center text-sm">
          No pending dedup candidates.
        </div>
      )}

      <ul className="divide-border mt-6 divide-y rounded-md border">
        {candidates.map((c) => {
          const state = actionState[c.dedup_candidate_id] ?? "idle";
          return (
            <li key={c.dedup_candidate_id} className="space-y-2 px-4 py-3">
              <div className="text-sm">
                <span className="text-muted-foreground">Candidate #</span>
                <span className="font-medium">{c.dedup_candidate_id}</span>
                <span className="text-muted-foreground ml-4">
                  Staged row: #{c.staging_row_id}
                </span>
                <span className="text-muted-foreground ml-4">
                  Existing alumni: #{c.matched_alumni_id}
                </span>
              </div>
              <div className="text-muted-foreground text-xs">
                Created: {new Date(c.created_at).toLocaleString()}
              </div>

              <div className="flex gap-2">
                <Button
                  size="sm"
                  disabled={state === "loading" || state === "done"}
                  onClick={() => handleResolve(c.dedup_candidate_id, "merge")}
                >
                  Same person (merge)
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={state === "loading" || state === "done"}
                  onClick={() =>
                    handleResolve(c.dedup_candidate_id, "keep_separate")
                  }
                >
                  Different person
                </Button>
              </div>

              {state === "error" && (
                <p className="text-destructive text-xs">Action failed.</p>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
