/**
 * Typed fetch wrapper for the FastAPI backend.
 *
 * This is the single place the frontend talks to the backend. The frontend never touches the
 * database directly (D-031) — all data access goes through FastAPI. The base URL comes from
 * `NEXT_PUBLIC_API_BASE_URL` (the Railway backend URL).
 */

const _rawApiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
if (!_rawApiBaseUrl && process.env.NODE_ENV === "production") {
  throw new Error(
    "NEXT_PUBLIC_API_BASE_URL is not set. This is required in production.",
  );
}
const API_BASE_URL = _rawApiBaseUrl ?? "http://localhost:8000";

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
 * Perform a typed request against the backend.
 *
 * Pass `accessToken` to include `Authorization: Bearer <token>` on the request.
 * If omitted the request is sent without an auth header (public endpoints pass through;
 * protected endpoints return 401 from FastAPI).
 *
 * Throws {@link ApiError} on non-2xx responses or network failures.
 */
export async function apiFetch<T>(
  path: string,
  init?: RequestInit,
  accessToken?: string,
): Promise<T> {
  const url = `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;

  const authHeaders: Record<string, string> = accessToken
    ? { Authorization: `Bearer ${accessToken}` }
    : {};

  let response: Response;
  try {
    response = await fetch(url, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...authHeaders,
        ...init?.headers,
      },
    });
  } catch (cause) {
    throw new ApiError(0, `Network error contacting backend: ${String(cause)}`);
  }

  if (!response.ok) {
    let detail = `Request to ${path} failed (${response.status}).`;
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      // ignore — keep generic message
    }
    throw new ApiError(response.status, detail);
  }

  return (await response.json()) as T;
}

/**
 * Perform a typed request with the current Supabase session token injected automatically.
 *
 * For use in Client Components only. Calling this from a Server Component or
 * Server Action will throw at runtime because it imports the browser Supabase client.
 * Use `apiFetch` directly with a server-obtained token for server-side calls.
 *
 * If no active session exists, the request proceeds without an auth header.
 */
export async function apiFetchWithAuth<T>(path: string, init?: RequestInit): Promise<T> {
  const { getSupabaseBrowserClient } = await import("@/lib/supabase/client");
  const supabase = getSupabaseBrowserClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  return apiFetch<T>(path, init, session?.access_token);
}

// ---------------------------------------------------------------------------
// Endpoint-specific typed helpers
// ---------------------------------------------------------------------------

export interface HealthResponse {
  status: string;
  app_env: string;
  database: "connected" | "unconfigured" | "error";
}

/** Fetch backend liveness/readiness from `GET /health`. No auth required. */
export function getHealth(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>("/health", { cache: "no-store" });
}

export interface MeResponse {
  user_id: number;
  supabase_uuid: string;
  role: string;
  permissions: string[];
}

/** Fetch the authenticated user's role and permissions from `GET /me`. Requires valid session. */
export function getMe(): Promise<MeResponse> {
  return apiFetchWithAuth<MeResponse>("/me", { cache: "no-store" });
}

export const apiBaseUrl = API_BASE_URL;
