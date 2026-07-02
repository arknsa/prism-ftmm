/**
 * Typed fetch wrapper for the FastAPI backend.
 *
 * This is the single place the frontend talks to the backend. The frontend never touches the
 * database directly (D-031) — all data access flows through FastAPI. The base URL comes from
 * `NEXT_PUBLIC_API_BASE_URL` (the Railway backend URL).
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/**
 * Perform a typed GET/POST/... request against the backend.
 * Throws {@link ApiError} on non-2xx responses or network failures.
 */
export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;

  let response: Response;
  try {
    response = await fetch(url, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...init?.headers,
      },
    });
  } catch (cause) {
    throw new ApiError(0, `Network error contacting backend: ${String(cause)}`);
  }

  if (!response.ok) {
    throw new ApiError(response.status, `Request to ${path} failed (${response.status}).`);
  }

  return (await response.json()) as T;
}

// ---------------------------------------------------------------------------
// Endpoint-specific typed helpers
// ---------------------------------------------------------------------------

export interface HealthResponse {
  status: string;
  app_env: string;
  database: "connected" | "unconfigured" | "error";
}

/** Fetch backend liveness/readiness from `GET /health`. */
export function getHealth(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>("/health", { cache: "no-store" });
}

export const apiBaseUrl = API_BASE_URL;
