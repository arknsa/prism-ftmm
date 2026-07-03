"use client";

/**
 * Shared analytics data-fetch hook.
 *
 * useDashboardEndpoint<T>(path, filters) fetches from a single analytics endpoint,
 * re-fetching whenever the filter state changes.
 *
 * Returns { data, loading, error, reload }.
 */

import { useCallback, useEffect, useState } from "react";

import { apiFetchWithAuth } from "@/lib/api-client";
import { buildQueryString, useFilters } from "@/lib/filter-context";

interface FetchState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

export function useDashboardEndpoint<T>(path: string): FetchState<T> & { reload: () => void } {
  const { toQueryParams } = useFilters();
  const [state, setState] = useState<FetchState<T>>({
    data: null,
    loading: true,
    error: null,
  });

  const fetch = useCallback(() => {
    const qs = buildQueryString(toQueryParams());
    setState((prev) => ({ ...prev, loading: true, error: null }));
    apiFetchWithAuth<T>(`${path}${qs}`)
      .then((data) => setState({ data, loading: false, error: null }))
      .catch((err: unknown) => {
        setState({
          data: null,
          loading: false,
          error: err instanceof Error ? err.message : "Failed to load.",
        });
      });
  }, [path, toQueryParams]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetch();
  }, [fetch]);

  return { ...state, reload: fetch };
}
