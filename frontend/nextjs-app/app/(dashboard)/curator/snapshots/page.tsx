"use client";

/**
 * P4.11 — Snapshot control screen.
 *
 * Allows the curator to:
 * - View existing quarterly snapshots.
 * - Open a new quarter snapshot.
 * - Trigger a batch commit under a selected snapshot (finalize commit).
 *
 * Permission required: snapshot:manage (view/open), import:run (commit)
 */

import { useCallback, useEffect, useState } from "react";

import { Unauthorized } from "@/components/unauthorized";
import { Button } from "@/components/ui/button";
import { apiFetchWithAuth } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Snapshot {
  snapshot_id: number;
  quarter_label: string;
  refresh_date: string;
  notes: string | null;
  created_at: string;
}

interface SnapshotListResponse {
  total: number;
  items: Snapshot[];
}

interface CommitBatchResult {
  batch_id: number;
  snapshot_id: number;
  total: number;
  created: number;
  linked: number;
  pending_dedup: number;
  skipped_error: number;
  skipped_no_employer: number;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function SnapshotsPage() {
  const { user, isLoading } = useAuth();

  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [fetching, setFetching] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);

  // Open new snapshot
  const [newLabel, setNewLabel] = useState<string>("");
  const [newNotes, setNewNotes] = useState<string>("");
  const [opening, setOpening] = useState(false);
  const [openError, setOpenError] = useState<string | null>(null);

  // Commit a batch
  const [batchId, setBatchId] = useState<string>("");
  const [selectedSnapshot, setSelectedSnapshot] = useState<string>("");
  const [committing, setCommitting] = useState(false);
  const [commitResult, setCommitResult] = useState<CommitBatchResult | null>(null);
  const [commitError, setCommitError] = useState<string | null>(null);

  const canManage = user?.permissions.includes("snapshot:manage") ?? false;
  const canCommit = user?.permissions.includes("import:run") ?? false;

  const load = useCallback(() => {
    setFetching(true);
    setFetchError(null);
    apiFetchWithAuth<SnapshotListResponse>("/api/v1/snapshots")
      .then((data) => {
        setSnapshots(data.items);
        setFetching(false);
      })
      .catch((err: unknown) => {
        setFetchError(err instanceof Error ? err.message : "Failed to load.");
        setFetching(false);
      });
  }, []);

  useEffect(() => {
    if (user && canManage) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      load();
    }
  }, [user, canManage, load]);

  const handleOpenSnapshot = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!newLabel) return;
      setOpening(true);
      setOpenError(null);
      try {
        const snap = await apiFetchWithAuth<Snapshot>("/api/v1/snapshots", {
          method: "POST",
          body: JSON.stringify({ quarter_label: newLabel, notes: newNotes || null }),
        });
        setSnapshots((prev) => [...prev, snap]);
        setNewLabel("");
        setNewNotes("");
      } catch (err: unknown) {
        setOpenError(err instanceof Error ? err.message : "Failed to open snapshot.");
      } finally {
        setOpening(false);
      }
    },
    [newLabel, newNotes],
  );

  const handleCommit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!batchId || !selectedSnapshot) return;
      setCommitting(true);
      setCommitResult(null);
      setCommitError(null);
      try {
        const result = await apiFetchWithAuth<CommitBatchResult>(
          "/api/v1/commit",
          {
            method: "POST",
            body: JSON.stringify({
              batch_id: parseInt(batchId, 10),
              snapshot_id: parseInt(selectedSnapshot, 10),
            }),
          },
        );
        setCommitResult(result);
      } catch (err: unknown) {
        setCommitError(
          err instanceof Error ? err.message : "Commit failed.",
        );
      } finally {
        setCommitting(false);
      }
    },
    [batchId, selectedSnapshot],
  );

  if (isLoading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <span className="text-muted-foreground text-sm">Loading…</span>
      </div>
    );
  }

  if (!user || !canManage) {
    return <Unauthorized />;
  }

  return (
    <div className="mx-auto max-w-3xl space-y-10 p-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            Snapshot Control
          </h1>
          <p className="text-muted-foreground mt-1 text-sm">
            Open quarterly snapshots and finalize the commit of staged alumni
            records (D-021). Each snapshot captures the state of all validated
            alumni and career records for that quarter.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={load} disabled={fetching}>
          {fetching ? "Refreshing…" : "Refresh"}
        </Button>
      </div>

      {fetchError && (
        <div className="bg-destructive/10 text-destructive rounded-md p-3 text-sm">
          {fetchError}
        </div>
      )}

      {/* Snapshot list */}
      <section>
        <h2 className="mb-2 text-sm font-semibold">Existing Snapshots</h2>
        {snapshots.length === 0 ? (
          <p className="text-muted-foreground text-sm">No snapshots yet.</p>
        ) : (
          <ul className="divide-border divide-y rounded-md border">
            {snapshots.map((s) => (
              <li key={s.snapshot_id} className="flex items-center gap-4 px-4 py-3 text-sm">
                <span className="font-mono font-medium">{s.quarter_label}</span>
                <span className="text-muted-foreground text-xs">
                  #{s.snapshot_id}
                </span>
                <span className="text-muted-foreground ml-auto text-xs">
                  Refreshed: {s.refresh_date}
                </span>
                {s.notes && (
                  <span className="text-muted-foreground text-xs italic">
                    {s.notes}
                  </span>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Open new snapshot */}
      <section>
        <h2 className="mb-2 text-sm font-semibold">Open New Quarter</h2>
        <form onSubmit={handleOpenSnapshot} className="space-y-3">
          <div className="flex gap-2">
            <input
              type="text"
              placeholder="Quarter label (e.g. 2025-Q3)"
              value={newLabel}
              onChange={(e) => setNewLabel(e.target.value)}
              pattern="\d{4}-Q[1-4]"
              required
              className="border-input bg-background focus:ring-ring flex-1 rounded-md border px-3 py-2 text-sm outline-none focus:ring-2"
            />
            <input
              type="text"
              placeholder="Notes (optional)"
              value={newNotes}
              onChange={(e) => setNewNotes(e.target.value)}
              className="border-input bg-background focus:ring-ring flex-1 rounded-md border px-3 py-2 text-sm outline-none focus:ring-2"
            />
          </div>
          <Button type="submit" disabled={opening || !newLabel}>
            {opening ? "Opening…" : "Open Snapshot"}
          </Button>
          {openError && (
            <p className="text-destructive text-sm">{openError}</p>
          )}
        </form>
      </section>

      {/* Finalize commit */}
      {canCommit && (
        <section>
          <h2 className="mb-2 text-sm font-semibold">Finalize Commit</h2>
          <p className="text-muted-foreground mb-3 text-xs">
            Commits all pending rows in a staged import batch to Alumni +
            CareerRecord tables under the selected snapshot.
          </p>
          <form onSubmit={handleCommit} className="flex gap-2">
            <input
              type="number"
              placeholder="Batch ID"
              value={batchId}
              onChange={(e) => setBatchId(e.target.value)}
              min={1}
              required
              className="border-input bg-background focus:ring-ring w-28 rounded-md border px-3 py-2 text-sm outline-none focus:ring-2"
            />
            <select
              value={selectedSnapshot}
              onChange={(e) => setSelectedSnapshot(e.target.value)}
              required
              className="border-input bg-background focus:ring-ring flex-1 rounded-md border px-3 py-2 text-sm outline-none focus:ring-2"
            >
              <option value="">Select snapshot…</option>
              {snapshots.map((s) => (
                <option key={s.snapshot_id} value={s.snapshot_id}>
                  {s.quarter_label} (#{s.snapshot_id})
                </option>
              ))}
            </select>
            <Button type="submit" disabled={committing || !batchId || !selectedSnapshot}>
              {committing ? "Committing…" : "Commit Batch"}
            </Button>
          </form>

          {commitError && (
            <div className="bg-destructive/10 text-destructive mt-3 rounded-md p-3 text-sm">
              {commitError}
            </div>
          )}

          {commitResult && (
            <div className="bg-muted mt-3 rounded-md p-4 text-sm">
              <div className="font-semibold">
                Commit complete — Snapshot #{commitResult.snapshot_id}
              </div>
              <div className="text-muted-foreground mt-1 grid grid-cols-3 gap-2 text-xs">
                <span>Total: {commitResult.total}</span>
                <span className="text-green-600">
                  Created: {commitResult.created}
                </span>
                <span>Linked: {commitResult.linked}</span>
                <span className="text-amber-600">
                  Pending dedup: {commitResult.pending_dedup}
                </span>
                <span>Skipped (error): {commitResult.skipped_error}</span>
                <span>
                  Skipped (no employer): {commitResult.skipped_no_employer}
                </span>
              </div>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
