"use client";

/**
 * P6.10 — Alumnus detail view.
 *
 * Shows profile fields + full career history (snapshot-aware, newest first).
 * Only validated alumni are reachable (backend returns 404 otherwise — D-047).
 *
 * Permission: analytics:read
 */

import Link from "next/link";
import { use, useEffect, useState } from "react";

import { PageShell } from "@/components/page-shell";
import { Button } from "@/components/ui/button";
import { apiFetchWithAuth } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface CareerEntry {
  career_record_id: number;
  company_name: string;
  role_title: string;
  seniority: string | null;
  is_current: boolean;
  snapshot_label: string | null;
  captured_on: string | null;
}

interface AlumnusDetailResponse {
  alumni_id: number;
  public_id: string;
  full_name: string;
  university: string;
  program_name: string;
  graduation_year: number;
  linkedin_url: string | null;
  validation_status: string;
  career_history: CareerEntry[];
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function AlumnusDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const { user, isLoading: authLoading } = useAuth();

  const [detail, setDetail] = useState<AlumnusDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user || !user.permissions.includes("analytics:read")) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    apiFetchWithAuth<AlumnusDetailResponse>(`/api/v1/analytics/alumni/${id}`)
      .then((data) => {
        setDetail(data);
        setLoading(false);
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Failed to load.");
        setLoading(false);
      });
  }, [user, id]);

  return (
    <PageShell
      title={detail?.full_name ?? "Alumnus"}
      description={
        detail
          ? `${detail.program_name} · Class of ${detail.graduation_year}`
          : undefined
      }
      loading={authLoading || loading}
      error={error}
      hasPermission={!!user && user.permissions.includes("analytics:read")}
      actions={
        <Button asChild variant="outline" size="sm">
          <Link href="/directory">← Directory</Link>
        </Button>
      }
    >
      {detail && (
        <div className="space-y-8">
          {/* Profile card */}
          <div className="rounded-lg border p-6">
            <h2 className="mb-4 text-lg font-semibold">Profile</h2>
            <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div>
                <dt className="text-muted-foreground text-xs font-medium uppercase tracking-wide">
                  Full Name
                </dt>
                <dd className="mt-1 text-sm">{detail.full_name}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground text-xs font-medium uppercase tracking-wide">
                  University
                </dt>
                <dd className="mt-1 text-sm">{detail.university}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground text-xs font-medium uppercase tracking-wide">
                  Program
                </dt>
                <dd className="mt-1 text-sm">{detail.program_name}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground text-xs font-medium uppercase tracking-wide">
                  Graduation Year
                </dt>
                <dd className="mt-1 tabular-nums text-sm">{detail.graduation_year}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground text-xs font-medium uppercase tracking-wide">
                  Status
                </dt>
                <dd className="mt-1 text-sm capitalize">{detail.validation_status}</dd>
              </div>
              {detail.linkedin_url && (
                <div>
                  <dt className="text-muted-foreground text-xs font-medium uppercase tracking-wide">
                    LinkedIn
                  </dt>
                  <dd className="mt-1 text-sm">
                    <a
                      href={detail.linkedin_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-primary hover:underline"
                    >
                      View profile
                    </a>
                  </dd>
                </div>
              )}
            </dl>
          </div>

          {/* Career history */}
          <div>
            <h2 className="mb-4 text-lg font-semibold">Career History</h2>
            {detail.career_history.length === 0 ? (
              <p className="text-muted-foreground text-sm">
                No career records on file.
              </p>
            ) : (
              <div className="space-y-3">
                {detail.career_history.map((entry) => (
                  <div
                    key={entry.career_record_id}
                    className={`rounded-lg border p-4 ${entry.is_current ? "border-primary/40 bg-primary/5" : ""}`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <p className="font-medium">{entry.role_title}</p>
                        <p className="text-muted-foreground text-sm">{entry.company_name}</p>
                      </div>
                      <div className="flex shrink-0 flex-col items-end gap-1">
                        {entry.is_current && (
                          <span className="bg-primary/10 text-primary rounded px-2 py-0.5 text-xs font-medium">
                            Current
                          </span>
                        )}
                        {entry.snapshot_label && (
                          <span className="text-muted-foreground text-xs">
                            {entry.snapshot_label}
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="text-muted-foreground mt-2 flex gap-4 text-xs">
                      {entry.seniority && <span>{entry.seniority}</span>}
                      {entry.captured_on && <span>Captured {entry.captured_on}</span>}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </PageShell>
  );
}
