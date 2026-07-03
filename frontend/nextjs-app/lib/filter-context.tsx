"use client";

/**
 * Global filter context (P6.2).
 *
 * Provides a shared filter state consumed by all dashboard pages.
 * Filter dimensions match the backend AnalyticsFilters contract (P5.1, D-007):
 *   study_program_id, graduation_year, industry_id, company_id, country, snapshot_id
 *
 * FilterProvider wraps the dashboard layout; pages read/write via useFilters().
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

import { apiFetchWithAuth } from "@/lib/api-client";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface FilterState {
  study_program_id: number | null;
  graduation_year: number | null;
  industry_id: number | null;
  company_id: number | null;
  country: string | null;
  snapshot_id: number | null;
}

export interface FilterOptions {
  programs: Array<{ program_id: number; program_name: string }>;
  graduation_years: number[];
  industries: Array<{ industry_id: number; industry_name: string }>;
  companies: Array<{ company_id: number; canonical_name: string }>;
  countries: string[];
  snapshots: Array<{ snapshot_id: number; quarter_label: string }>;
}

export type FilterKey = keyof FilterState;

interface FilterContextValue {
  filters: FilterState;
  options: FilterOptions | null;
  optionsLoading: boolean;
  setFilter: (key: FilterKey, value: FilterState[FilterKey]) => void;
  clearFilters: () => void;
  toQueryParams: () => Record<string, string>;
}

// ---------------------------------------------------------------------------
// Defaults
// ---------------------------------------------------------------------------

const DEFAULT_FILTERS: FilterState = {
  study_program_id: null,
  graduation_year: null,
  industry_id: null,
  company_id: null,
  country: null,
  snapshot_id: null,
};

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

const FilterContext = createContext<FilterContextValue | null>(null);

export function FilterProvider({ children }: { children: ReactNode }) {
  const [filters, setFilters] = useState<FilterState>(DEFAULT_FILTERS);
  const [options, setOptions] = useState<FilterOptions | null>(null);
  const [optionsLoading, setOptionsLoading] = useState(false);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setOptionsLoading(true);
    apiFetchWithAuth<FilterOptions>("/api/v1/analytics/filter-options")
      .then((data) => {
        setOptions(data);
        setOptionsLoading(false);
      })
      .catch(() => {
        setOptionsLoading(false);
      });
  }, []);

  const setFilter = useCallback(
    (key: FilterKey, value: FilterState[FilterKey]) => {
      setFilters((prev) => ({ ...prev, [key]: value }));
    },
    [],
  );

  const clearFilters = useCallback(() => {
    setFilters(DEFAULT_FILTERS);
  }, []);

  const toQueryParams = useCallback((): Record<string, string> => {
    const params: Record<string, string> = {};
    if (filters.study_program_id !== null) {
      params.study_program_id = String(filters.study_program_id);
    }
    if (filters.graduation_year !== null) {
      params.graduation_year = String(filters.graduation_year);
    }
    if (filters.industry_id !== null) {
      params.industry_id = String(filters.industry_id);
    }
    if (filters.company_id !== null) {
      params.company_id = String(filters.company_id);
    }
    if (filters.country !== null) {
      params.country = filters.country;
    }
    if (filters.snapshot_id !== null) {
      params.snapshot_id = String(filters.snapshot_id);
    }
    return params;
  }, [filters]);

  return (
    <FilterContext.Provider
      value={{ filters, options, optionsLoading, setFilter, clearFilters, toQueryParams }}
    >
      {children}
    </FilterContext.Provider>
  );
}

export function useFilters(): FilterContextValue {
  const ctx = useContext(FilterContext);
  if (ctx === null) {
    throw new Error("useFilters must be used inside <FilterProvider>.");
  }
  return ctx;
}

/** Build a query string from a filter state (for appending to fetch URLs). */
export function buildQueryString(params: Record<string, string>): string {
  const entries = Object.entries(params).filter(([, v]) => v !== "");
  if (entries.length === 0) return "";
  return "?" + new URLSearchParams(entries).toString();
}
