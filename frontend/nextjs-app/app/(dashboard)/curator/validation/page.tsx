"use client";

/**
 * P4.8 — Validation screen.
 *
 * Shows a list of alumni with validation_status="pending".
 * Curator can validate or reject each entry with an optional reason.
 *
 * Permission required: alumni:validate
 */

import { useCallback, useEffect, useState } from "react";

import { Unauthorized } from "@/components/unauthorized";
import { Button } from "@/components/ui/button";
import { apiFetchWithAuth } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface AlumniItem {
  alumni_id: number;
  full_name: string;
  study_program_id: number;
  graduation_year: number;
  validation_status: string;
}

interface AlumniListResponse {
  total: number;
  items: AlumniItem[];
}

interface ValidateResult {
  alumni_id: number;
  validation_status: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ValidationPage() {
  const { user, isLoading } = useAuth();

  const [alumni, setAlumni] = useState<AlumniItem[]>([]);
  const [fetching, setFetching] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [actionState, setActionState] = useState<
    Record<number, "idle" | "loading" | "done" | "error">
  >({});
  const [reasons, setReasons] = useState<Record<number, string>>({});

  const load = useCallback(() => {
    setFetching(true);
    setFetchError(null);
    apiFetchWithAuth<AlumniListResponse>("/api/v1/alumni?validation_status=pending")
      .then((data) => {
        setAlumni(data.items);
        setFetching(false);
      })
      .catch((err: unknown) => {
        setFetchError(err instanceof Error ? err.message : "Failed to load.");
        setFetching(false);
      });
  }, []);

  useEffect(() => {
    if (user && user.permissions.includes("alumni:validate")) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      load();
    }
  }, [user, load]);

  const handleAction = useCallback(
    (alumniId: number, action: "validate" | "reject") => {
      setActionState((prev) => ({ ...prev, [alumniId]: "loading" }));
      apiFetchWithAuth<ValidateResult>(`/api/v1/alumni/${alumniId}/validate`, {
        method: "POST",
        body: JSON.stringify({ action, reason: reasons[alumniId] ?? null }),
      })
        .then(() => {
          setActionState((prev) => ({ ...prev, [alumniId]: "done" }));
          setAlumni((prev) => prev.filter((a) => a.alumni_id !== alumniId));
        })
        .catch((err: unknown) => {
          console.error(err);
          setActionState((prev) => ({ ...prev, [alumniId]: "error" }));
        });
    },
    [reasons],
  );

  if (isLoading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <span className="text-muted-foreground text-sm">Loading…</span>
      </div>
    );
  }

  if (!user || !user.permissions.includes("alumni:validate")) {
    return <Unauthorized />;
  }

  return (
    <div className="mx-auto max-w-3xl p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            Pending Validation
          </h1>
          <p className="text-muted-foreground mt-1 text-sm">
            Review each alumni record and validate or reject it (D-024 curator
            gate). Only validated records appear in analytics.
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

      {!fetching && alumni.length === 0 && !fetchError && (
        <div className="text-muted-foreground mt-8 text-center text-sm">
          No pending alumni records.
        </div>
      )}

      <ul className="divide-border mt-6 divide-y rounded-md border">
        {alumni.map((a) => {
          const state = actionState[a.alumni_id] ?? "idle";
          return (
            <li key={a.alumni_id} className="space-y-2 px-4 py-3">
              <div className="flex items-center justify-between">
                <div>
                  <span className="font-medium">{a.full_name}</span>
                  <span className="text-muted-foreground ml-2 text-xs">
                    #{a.alumni_id} · Program {a.study_program_id} · Class of{" "}
                    {a.graduation_year}
                  </span>
                </div>
                <span className="text-muted-foreground text-xs capitalize">
                  {a.validation_status}
                </span>
              </div>

              <div className="flex items-center gap-2">
                <input
                  type="text"
                  placeholder="Reason (optional for validate, useful for reject)"
                  value={reasons[a.alumni_id] ?? ""}
                  onChange={(e) =>
                    setReasons((prev) => ({
                      ...prev,
                      [a.alumni_id]: e.target.value,
                    }))
                  }
                  className="border-input bg-background focus:ring-ring flex-1 rounded-md border px-2 py-1 text-xs outline-none focus:ring-2"
                />
                <Button
                  size="sm"
                  disabled={state === "loading" || state === "done"}
                  onClick={() => handleAction(a.alumni_id, "validate")}
                >
                  {state === "loading" ? "…" : "Validate"}
                </Button>
                <Button
                  variant="destructive"
                  size="sm"
                  disabled={state === "loading" || state === "done"}
                  onClick={() => handleAction(a.alumni_id, "reject")}
                >
                  Reject
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
