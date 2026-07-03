/**
 * Tests for FilterProvider / useFilters (lib/filter-context.tsx).
 *
 * Strategy: mock apiFetchWithAuth so FilterProvider doesn't hit the network,
 * then render the hook with FilterProvider as wrapper and exercise
 * setFilter() / clearFilters() / toQueryParams().
 *
 * Covers: initial state, setFilter, clearFilters, toQueryParams output.
 */

import { act, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { FilterProvider, useFilters } from "@/lib/filter-context";

// Mock apiFetchWithAuth so FilterProvider's useEffect doesn't hit the network.
vi.mock("@/lib/api-client", () => ({
  apiFetchWithAuth: vi.fn().mockResolvedValue({
    programs: [],
    graduation_years: [],
    industries: [],
    companies: [],
    countries: [],
    snapshots: [],
  }),
}));

function wrapper({ children }: { children: ReactNode }) {
  return <FilterProvider>{children}</FilterProvider>;
}

describe("useFilters", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("starts with all filters null", () => {
    const { result } = renderHook(() => useFilters(), { wrapper });
    const { filters } = result.current;
    expect(filters.study_program_id).toBeNull();
    expect(filters.graduation_year).toBeNull();
    expect(filters.industry_id).toBeNull();
    expect(filters.company_id).toBeNull();
    expect(filters.country).toBeNull();
    expect(filters.snapshot_id).toBeNull();
  });

  it("toQueryParams returns empty object when no filters are set", () => {
    const { result } = renderHook(() => useFilters(), { wrapper });
    expect(result.current.toQueryParams()).toEqual({});
  });

  it("setFilter updates the named filter dimension", () => {
    const { result } = renderHook(() => useFilters(), { wrapper });
    act(() => {
      result.current.setFilter("country", "Indonesia");
    });
    expect(result.current.filters.country).toBe("Indonesia");
  });

  it("toQueryParams serialises non-null dimensions to strings", () => {
    const { result } = renderHook(() => useFilters(), { wrapper });
    act(() => {
      result.current.setFilter("country", "Indonesia");
      result.current.setFilter("graduation_year", 2022);
    });
    expect(result.current.toQueryParams()).toEqual({
      country: "Indonesia",
      graduation_year: "2022",
    });
  });

  it("toQueryParams omits null dimensions", () => {
    const { result } = renderHook(() => useFilters(), { wrapper });
    act(() => {
      result.current.setFilter("study_program_id", 3);
    });
    const params = result.current.toQueryParams();
    expect(params).toHaveProperty("study_program_id", "3");
    expect(params).not.toHaveProperty("country");
    expect(params).not.toHaveProperty("graduation_year");
  });

  it("clearFilters resets all dimensions to null", () => {
    const { result } = renderHook(() => useFilters(), { wrapper });
    act(() => {
      result.current.setFilter("country", "Indonesia");
      result.current.setFilter("snapshot_id", 5);
    });
    act(() => {
      result.current.clearFilters();
    });
    expect(result.current.filters.country).toBeNull();
    expect(result.current.filters.snapshot_id).toBeNull();
    expect(result.current.toQueryParams()).toEqual({});
  });
});
