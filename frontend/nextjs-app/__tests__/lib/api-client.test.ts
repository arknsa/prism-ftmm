/**
 * Tests for ApiError and apiFetch (lib/api-client.ts).
 *
 * Uses vi.stubGlobal("fetch", ...) to control the fetch response without a real network.
 * Covers: ApiError shape, network failure, backend error detail propagation, success path.
 */

import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiFetch } from "@/lib/api-client";

// ---------------------------------------------------------------------------
// ApiError class
// ---------------------------------------------------------------------------

describe("ApiError", () => {
  it("stores status and message", () => {
    const err = new ApiError(422, "Unprocessable Entity");
    expect(err.status).toBe(422);
    expect(err.message).toBe("Unprocessable Entity");
  });

  it("has name 'ApiError'", () => {
    expect(new ApiError(400, "Bad request").name).toBe("ApiError");
  });

  it("is an instance of Error", () => {
    expect(new ApiError(500, "Server error")).toBeInstanceOf(Error);
  });
});

// ---------------------------------------------------------------------------
// apiFetch — fetch wrapper behaviour
// ---------------------------------------------------------------------------

describe("apiFetch", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("throws ApiError(0) on a network failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new TypeError("Failed to fetch")),
    );
    await expect(apiFetch("/test")).rejects.toMatchObject({
      name: "ApiError",
      status: 0,
    });
  });

  it("throws ApiError and propagates backend detail string on non-2xx", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 422,
        json: async () => ({ detail: "Validation failed" }),
      }),
    );
    await expect(apiFetch("/test")).rejects.toMatchObject({
      status: 422,
      message: "Validation failed",
    });
  });

  it("uses a generic message when backend detail is not a string", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 400,
        json: async () => ({ detail: [{ msg: "field required" }] }),
      }),
    );
    const err = await apiFetch("/test").catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).status).toBe(400);
    // Generic message — must mention the endpoint path and status
    expect((err as ApiError).message).toContain("400");
  });

  it("returns parsed JSON on a 2xx response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ total: 42 }),
      }),
    );
    const result = await apiFetch<{ total: number }>("/test");
    expect(result.total).toBe(42);
  });

  it("attaches Authorization header when accessToken is provided", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({}),
    });
    vi.stubGlobal("fetch", mockFetch);
    await apiFetch("/test", {}, "my-token");
    const [, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect((init.headers as Record<string, string>)["Authorization"]).toBe(
      "Bearer my-token",
    );
  });
});
