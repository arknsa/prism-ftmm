"use client";

/**
 * Global filter bar (P6.2).
 *
 * Renders dropdowns for all six filter dimensions (D-007).
 * Reads available options from FilterContext; writes selected values back.
 *
 * Permission: analytics:read (only rendered for users with that permission).
 */

import { Button } from "@/components/ui/button";
import { useFilters } from "@/lib/filter-context";

export function FilterBar() {
  const { filters, options, optionsLoading, setFilter, clearFilters } = useFilters();

  const hasAnyFilter = Object.values(filters).some((v) => v !== null);

  const selectClass =
    "border-input bg-background focus:ring-ring rounded-md border px-2 py-1.5 text-xs " +
    "outline-none focus:ring-2 min-w-[140px]";

  if (optionsLoading) {
    return (
      <div className="border-b px-6 py-2">
        <span className="text-muted-foreground text-xs">Loading filters…</span>
      </div>
    );
  }

  if (!options) return null;

  return (
    <div className="border-b bg-background px-6 py-2">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-3">
        <span className="text-muted-foreground text-xs font-medium">Filters:</span>

        {/* Snapshot Quarter */}
        {options.snapshots.length > 0 && (
          <div className="flex flex-col gap-0.5">
            <label className="text-muted-foreground text-[10px] uppercase tracking-wide">
              Quarter
            </label>
            <select
              className={selectClass}
              value={filters.snapshot_id ?? ""}
              onChange={(e) =>
                setFilter("snapshot_id", e.target.value ? Number(e.target.value) : null)
              }
            >
              <option value="">All quarters</option>
              {options.snapshots.map((s) => (
                <option key={s.snapshot_id} value={s.snapshot_id}>
                  {s.quarter_label}
                </option>
              ))}
            </select>
          </div>
        )}

        {/* Study Program */}
        {options.programs.length > 0 && (
          <div className="flex flex-col gap-0.5">
            <label className="text-muted-foreground text-[10px] uppercase tracking-wide">
              Program
            </label>
            <select
              className={selectClass}
              value={filters.study_program_id ?? ""}
              onChange={(e) =>
                setFilter("study_program_id", e.target.value ? Number(e.target.value) : null)
              }
            >
              <option value="">All programs</option>
              {options.programs.map((p) => (
                <option key={p.program_id} value={p.program_id}>
                  {p.program_name}
                </option>
              ))}
            </select>
          </div>
        )}

        {/* Graduation Year */}
        {options.graduation_years.length > 0 && (
          <div className="flex flex-col gap-0.5">
            <label className="text-muted-foreground text-[10px] uppercase tracking-wide">
              Cohort
            </label>
            <select
              className={selectClass}
              value={filters.graduation_year ?? ""}
              onChange={(e) =>
                setFilter("graduation_year", e.target.value ? Number(e.target.value) : null)
              }
            >
              <option value="">All years</option>
              {options.graduation_years.map((y) => (
                <option key={y} value={y}>
                  {y}
                </option>
              ))}
            </select>
          </div>
        )}

        {/* Industry */}
        {options.industries.length > 0 && (
          <div className="flex flex-col gap-0.5">
            <label className="text-muted-foreground text-[10px] uppercase tracking-wide">
              Industry
            </label>
            <select
              className={selectClass}
              value={filters.industry_id ?? ""}
              onChange={(e) =>
                setFilter("industry_id", e.target.value ? Number(e.target.value) : null)
              }
            >
              <option value="">All industries</option>
              {options.industries.map((i) => (
                <option key={i.industry_id} value={i.industry_id}>
                  {i.industry_name}
                </option>
              ))}
            </select>
          </div>
        )}

        {/* Country */}
        {options.countries.length > 0 && (
          <div className="flex flex-col gap-0.5">
            <label className="text-muted-foreground text-[10px] uppercase tracking-wide">
              Country
            </label>
            <select
              className={selectClass}
              value={filters.country ?? ""}
              onChange={(e) => setFilter("country", e.target.value || null)}
            >
              <option value="">All countries</option>
              {options.countries.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>
        )}

        {/* Clear */}
        {hasAnyFilter && (
          <Button variant="ghost" size="sm" className="mt-3 text-xs" onClick={clearFilters}>
            Clear
          </Button>
        )}
      </div>
    </div>
  );
}
