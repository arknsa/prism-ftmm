"use client";

/**
 * P4.7 — Import screen.
 *
 * Allows a curator to upload a dataset (CSV or XLSX) and choose a source,
 * then view the batch result/errors.
 *
 * Permission required: import:run
 */

import { useCallback, useState } from "react";

import { Unauthorized } from "@/components/unauthorized";
import { Button } from "@/components/ui/button";
import { apiFetchWithAuth } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";

// ---------------------------------------------------------------------------
// Types matching backend schemas
// ---------------------------------------------------------------------------

interface ImportRowError {
  row_number: number;
  error: string;
}

interface ImportBatchResult {
  batch_id: number;
  source_id: number;
  filename: string;
  total_rows: number;
  parsed_rows: number;
  error_rows: number;
  status: string;
  errors: ImportRowError[];
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ImportPage() {
  const { user, isLoading } = useAuth();

  const [file, setFile] = useState<File | null>(null);
  const [sourceId, setSourceId] = useState<string>("");
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<ImportBatchResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!file || !sourceId) return;

      setUploading(true);
      setResult(null);
      setError(null);

      const formData = new FormData();
      formData.append("file", file);
      formData.append("source_id", sourceId);

      try {
        const data = await apiFetchWithAuth<ImportBatchResult>(
          "/api/v1/imports",
          {
            method: "POST",
            body: formData,
            headers: {},
          },
        );
        setResult(data);
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Upload failed.");
      } finally {
        setUploading(false);
      }
    },
    [file, sourceId],
  );

  if (isLoading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <span className="text-muted-foreground text-sm">Loading…</span>
      </div>
    );
  }

  if (!user || !user.permissions.includes("import:run")) {
    return <Unauthorized />;
  }

  return (
    <div className="mx-auto max-w-2xl p-8">
      <h1 className="text-2xl font-bold tracking-tight">Import Dataset</h1>
      <p className="text-muted-foreground mt-1 text-sm">
        Upload a CSV or XLSX file and choose a capture source to stage alumni
        records for curator review.
      </p>

      <form onSubmit={handleSubmit} className="mt-6 space-y-4">
        <div className="space-y-1">
          <label className="text-sm font-medium" htmlFor="source_id">
            Source ID
          </label>
          <input
            id="source_id"
            type="number"
            min={1}
            required
            value={sourceId}
            onChange={(e) => setSourceId(e.target.value)}
            placeholder="e.g. 1"
            className="border-input bg-background focus:ring-ring w-full rounded-md border px-3 py-2 text-sm outline-none focus:ring-2"
          />
          <p className="text-muted-foreground text-xs">
            The numeric ID of the CaptureSource this file belongs to.
          </p>
        </div>

        <div className="space-y-1">
          <label className="text-sm font-medium" htmlFor="file">
            Dataset file
          </label>
          <input
            id="file"
            type="file"
            accept=".csv,.xlsx"
            required
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="border-input bg-background focus:ring-ring w-full rounded-md border px-3 py-2 text-sm outline-none focus:ring-2"
          />
          <p className="text-muted-foreground text-xs">
            Accepts .csv or .xlsx files per the A1 import spec.
          </p>
        </div>

        <Button
          type="submit"
          disabled={uploading || !file || !sourceId}
          className="w-full"
        >
          {uploading ? "Uploading…" : "Upload and stage"}
        </Button>
      </form>

      {error && (
        <div className="bg-destructive/10 text-destructive mt-6 rounded-md p-4 text-sm">
          {error}
        </div>
      )}

      {result && (
        <div className="mt-6 space-y-3">
          <div className="bg-muted rounded-md p-4 text-sm">
            <div className="font-semibold">
              Batch #{result.batch_id} — {result.status}
            </div>
            <div className="text-muted-foreground mt-1 grid grid-cols-3 gap-2 text-xs">
              <span>Total: {result.total_rows}</span>
              <span className="text-green-600">Parsed: {result.parsed_rows}</span>
              <span className={result.error_rows > 0 ? "text-destructive" : ""}>
                Errors: {result.error_rows}
              </span>
            </div>
          </div>

          {result.errors.length > 0 && (
            <div className="space-y-1">
              <h2 className="text-sm font-semibold">Row errors</h2>
              <ul className="divide-border divide-y rounded-md border text-sm">
                {result.errors.map((e) => (
                  <li
                    key={e.row_number}
                    className="text-muted-foreground flex gap-3 px-3 py-2"
                  >
                    <span className="font-mono text-xs">Row {e.row_number}</span>
                    <span>{e.error}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
