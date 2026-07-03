"use client";

/**
 * P6.9 — Alumni Directory page.
 *
 * Paginated, searchable, filterable table of validated alumni.
 * Shows current company, role, and seniority.
 *
 * Permission: analytics:read
 */

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { PageShell } from "@/components/page-shell";
import { Button } from "@/components/ui/button";
import { apiFetchWithAuth } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { buildQueryString, useFilters } from "@/lib/filter-context";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface AlumniItem {
  alumni_id: number;
  public_id: string;
  full_name: string;
  study_program_id: number;
  program_name: string;
  graduation_year: number;
  validation_status: string;
  current_company: string | null;
  current_role: string | null;
  current_seniority: string | null;
}

interface DirectoryResponse {
  total: number;
  page: number;
  page_size: number;
  items: AlumniItem[];
}

const PAGE_SIZE = 50;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function DirectoryPage() {
  const { user, isLoading: authLoading } = useAuth();
  const { toQueryParams } = useFilters();

  const [items, setItems] = useState<AlumniItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [pendingSearch, setPendingSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    (p: number, s: string) => {
      setLoading(true);
      setError(null);
      const filterParams = toQueryParams();
      if (s) filterParams.search = s;
      filterParams.page = String(p);
      filterParams.page_size = String(PAGE_SIZE);
      const qs = buildQueryString(filterParams);
      apiFetchWithAuth<DirectoryResponse>(`/api/v1/analytics/directory${qs}`)
        .then((data) => {
          setItems(data.items);
          setTotal(data.total);
          setLoading(false);
        })
        .catch((err: unknown) => {
          setError(err instanceof Error ? err.message : "Failed to load.");
          setLoading(false);
        });
    },
    [toQueryParams],
  );

  // Re-fetch when filter state or page changes
  useEffect(() => {
    if (user && user.permissions.includes("analytics:read")) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      load(page, search);
    }
  }, [user, page, search, load]);

  const handleSearch = useCallback(() => {
    setSearch(pendingSearch);
    setPage(1);
  }, [pendingSearch]);

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <PageShell
      title="Alumni Directory"
      description="All validated alumni with current career information."
      loading={authLoading}
      error={error}
      hasPermission={!!user && user.permissions.includes("analytics:read")}
    >
      {/* Search bar */}
      <div className="flex gap-2">
        <input
          type="text"
          placeholder="Search by name…"
          value={pendingSearch}
          onChange={(e) => setPendingSearch(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleSearch();
          }}
          className="border-input bg-background focus:ring-ring flex-1 rounded-md border px-3 py-2 text-sm outline-none focus:ring-2"
        />
        <Button onClick={handleSearch} variant="outline" size="sm">
          Search
        </Button>
        {search && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setPendingSearch("");
              setSearch("");
              setPage(1);
            }}
          >
            Clear
          </Button>
        )}
      </div>

      {/* Summary */}
      {!loading && (
        <p className="text-muted-foreground text-xs">
          {total.toLocaleString()} alumni
          {search ? ` matching "${search}"` : ""}
        </p>
      )}

      {/* Table */}
      <div className="overflow-x-auto rounded-md border">
        <table className="w-full text-sm">
          <thead className="bg-muted/50">
            <tr>
              <th className="px-4 py-2 text-left font-medium">Name</th>
              <th className="px-4 py-2 text-left font-medium">Program</th>
              <th className="px-4 py-2 text-left font-medium">Year</th>
              <th className="px-4 py-2 text-left font-medium">Current Role</th>
              <th className="px-4 py-2 text-left font-medium">Company</th>
              <th className="px-4 py-2 text-left font-medium">Seniority</th>
            </tr>
          </thead>
          <tbody className="divide-border divide-y">
            {loading ? (
              <tr>
                <td colSpan={6} className="text-muted-foreground py-8 text-center text-xs">
                  Loading…
                </td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={6} className="text-muted-foreground py-8 text-center text-xs">
                  No alumni found.
                </td>
              </tr>
            ) : (
              items.map((a) => (
                <tr key={a.alumni_id} className="hover:bg-muted/30">
                  <td className="px-4 py-2 font-medium">
                    <Link
                      href={`/directory/${a.alumni_id}`}
                      className="hover:underline"
                    >
                      {a.full_name}
                    </Link>
                  </td>
                  <td className="text-muted-foreground px-4 py-2">{a.program_name}</td>
                  <td className="text-muted-foreground px-4 py-2 tabular-nums">
                    {a.graduation_year}
                  </td>
                  <td className="text-muted-foreground px-4 py-2">
                    {a.current_role ?? <span className="italic">—</span>}
                  </td>
                  <td className="text-muted-foreground px-4 py-2">
                    {a.current_company ?? <span className="italic">—</span>}
                  </td>
                  <td className="text-muted-foreground px-4 py-2">
                    {a.current_seniority ?? <span className="italic">—</span>}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
          >
            Previous
          </Button>
          <span className="text-muted-foreground text-xs">
            Page {page} of {totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= totalPages}
            onClick={() => setPage((p) => p + 1)}
          >
            Next
          </Button>
        </div>
      )}
    </PageShell>
  );
}
