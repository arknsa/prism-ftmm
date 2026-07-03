"use client";

/**
 * P4.10 — Company-alias management screen.
 *
 * Lists companies with their aliases. Curator can:
 * - Assign industry_id and location_id to a company.
 * - Remap an alias to a different canonical company.
 *
 * Permission required: company:read (view), company:write (mutate)
 */

import { useCallback, useEffect, useState } from "react";

import { Unauthorized } from "@/components/unauthorized";
import { Button } from "@/components/ui/button";
import { apiFetchWithAuth } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface CompanyItem {
  company_id: number;
  canonical_name: string;
  industry_id: number | null;
  location_id: number | null;
  created_at: string;
}

interface CompanyListResponse {
  total: number;
  items: CompanyItem[];
}

interface AliasItem {
  alias_id: number;
  company_id: number;
  alias_name: string;
  source_id: number | null;
}

interface AliasListResponse {
  total: number;
  items: AliasItem[];
}

// ---------------------------------------------------------------------------
// Sub-component: AliasRow
// ---------------------------------------------------------------------------

function AliasRow({
  alias,
  hasWritePerm,
  onRemap,
}: {
  alias: AliasItem;
  hasWritePerm: boolean;
  onRemap: (aliasId: number, newCompanyId: number) => Promise<void>;
}) {
  const [newCompanyId, setNewCompanyId] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleRemap = async () => {
    const targetId = parseInt(newCompanyId, 10);
    if (!targetId) return;
    setLoading(true);
    setError(null);
    try {
      await onRemap(alias.alias_id, targetId);
      setDone(true);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <li className="text-muted-foreground flex items-center gap-2 px-4 py-1.5 text-xs">
      <span className="font-mono">{alias.alias_name}</span>
      {hasWritePerm && !done && (
        <>
          <input
            type="number"
            placeholder="remap to company ID"
            value={newCompanyId}
            onChange={(e) => setNewCompanyId(e.target.value)}
            className="border-input bg-background ml-auto w-32 rounded border px-2 py-0.5 text-xs"
          />
          <Button
            size="xs"
            variant="outline"
            disabled={loading || !newCompanyId}
            onClick={handleRemap}
          >
            {loading ? "…" : "Remap"}
          </Button>
        </>
      )}
      {done && <span className="ml-auto text-green-600">Remapped</span>}
      {error && <span className="text-destructive ml-auto">{error}</span>}
    </li>
  );
}

// ---------------------------------------------------------------------------
// Sub-component: CompanyRow
// ---------------------------------------------------------------------------

function CompanyRow({
  company,
  hasWritePerm,
  onUpdate,
  onRemap,
}: {
  company: CompanyItem;
  hasWritePerm: boolean;
  onUpdate: (
    companyId: number,
    industryId: number | null,
    locationId: number | null,
  ) => Promise<void>;
  onRemap: (aliasId: number, newCompanyId: number) => Promise<void>;
}) {
  const [expanded, setExpanded] = useState(false);
  const [aliases, setAliases] = useState<AliasItem[] | null>(null);
  const [industryId, setIndustryId] = useState<string>(
    company.industry_id?.toString() ?? "",
  );
  const [locationId, setLocationId] = useState<string>(
    company.location_id?.toString() ?? "",
  );
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const loadAliases = useCallback(async () => {
    if (aliases !== null) return;
    try {
      const data = await apiFetchWithAuth<AliasListResponse>(
        `/api/v1/companies/${company.company_id}/aliases`,
      );
      setAliases(data.items);
    } catch {
      setAliases([]);
    }
  }, [company.company_id, aliases]);

  const handleToggle = () => {
    if (!expanded) void loadAliases();
    setExpanded((prev) => !prev);
  };

  const handleSave = async () => {
    setSaving(true);
    setSaveError(null);
    setSaved(false);
    try {
      await onUpdate(
        company.company_id,
        industryId ? parseInt(industryId, 10) : null,
        locationId ? parseInt(locationId, 10) : null,
      );
      setSaved(true);
    } catch (err: unknown) {
      setSaveError(err instanceof Error ? err.message : "Save failed.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <li className="border-border overflow-hidden rounded-md border">
      <button
        className="hover:bg-muted flex w-full items-center justify-between px-4 py-3 text-left"
        onClick={handleToggle}
        type="button"
      >
        <div>
          <span className="font-medium">{company.canonical_name}</span>
          <span className="text-muted-foreground ml-2 text-xs">
            #{company.company_id}
          </span>
        </div>
        <span className="text-muted-foreground text-xs">
          {expanded ? "▲" : "▼"}
        </span>
      </button>

      {expanded && (
        <div className="border-border border-t">
          {hasWritePerm && (
            <div className="flex items-center gap-2 bg-muted/40 px-4 py-2">
              <label className="text-xs font-medium">Industry ID</label>
              <input
                type="number"
                value={industryId}
                onChange={(e) => setIndustryId(e.target.value)}
                placeholder="—"
                className="border-input bg-background w-20 rounded border px-2 py-0.5 text-xs"
              />
              <label className="text-xs font-medium">Location ID</label>
              <input
                type="number"
                value={locationId}
                onChange={(e) => setLocationId(e.target.value)}
                placeholder="—"
                className="border-input bg-background w-20 rounded border px-2 py-0.5 text-xs"
              />
              <Button size="xs" disabled={saving} onClick={handleSave}>
                {saving ? "…" : "Save"}
              </Button>
              {saved && <span className="text-xs text-green-600">Saved</span>}
              {saveError && (
                <span className="text-destructive text-xs">{saveError}</span>
              )}
            </div>
          )}

          {aliases === null ? (
            <p className="text-muted-foreground px-4 py-2 text-xs">
              Loading aliases…
            </p>
          ) : aliases.length === 0 ? (
            <p className="text-muted-foreground px-4 py-2 text-xs">
              No aliases.
            </p>
          ) : (
            <ul className="divide-border divide-y">
              {aliases.map((a) => (
                <AliasRow
                  key={a.alias_id}
                  alias={a}
                  hasWritePerm={hasWritePerm}
                  onRemap={onRemap}
                />
              ))}
            </ul>
          )}
        </div>
      )}
    </li>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function CompaniesPage() {
  const { user, isLoading } = useAuth();

  const [companies, setCompanies] = useState<CompanyItem[]>([]);
  const [fetching, setFetching] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);

  const hasWritePerm = user?.permissions.includes("company:write") ?? false;

  const load = useCallback(() => {
    setFetching(true);
    setFetchError(null);
    apiFetchWithAuth<CompanyListResponse>("/api/v1/companies")
      .then((data) => {
        setCompanies(data.items);
        setFetching(false);
      })
      .catch((err: unknown) => {
        setFetchError(err instanceof Error ? err.message : "Failed to load.");
        setFetching(false);
      });
  }, []);

  useEffect(() => {
    if (user && user.permissions.includes("company:read")) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      load();
    }
  }, [user, load]);

  const handleUpdate = useCallback(
    async (
      companyId: number,
      industryId: number | null,
      locationId: number | null,
    ) => {
      await apiFetchWithAuth<CompanyItem>(`/api/v1/companies/${companyId}`, {
        method: "PATCH",
        body: JSON.stringify({ industry_id: industryId, location_id: locationId }),
      });
    },
    [],
  );

  const handleRemap = useCallback(
    async (aliasId: number, newCompanyId: number) => {
      await apiFetchWithAuth(`/api/v1/aliases/${aliasId}/remap`, {
        method: "PATCH",
        body: JSON.stringify({ company_id: newCompanyId }),
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

  if (!user || !user.permissions.includes("company:read")) {
    return <Unauthorized />;
  }

  return (
    <div className="mx-auto max-w-3xl p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            Company Aliases
          </h1>
          <p className="text-muted-foreground mt-1 text-sm">
            Map raw employer aliases to canonical companies. Assign industry and
            location to companies for enriched analytics (D-017–D-019).
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

      {!fetching && companies.length === 0 && !fetchError && (
        <div className="text-muted-foreground mt-8 text-center text-sm">
          No companies yet. Import a dataset to create company records.
        </div>
      )}

      <ul className="mt-6 space-y-2">
        {companies.map((c) => (
          <CompanyRow
            key={c.company_id}
            company={c}
            hasWritePerm={hasWritePerm}
            onUpdate={handleUpdate}
            onRemap={handleRemap}
          />
        ))}
      </ul>
    </div>
  );
}
