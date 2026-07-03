/**
 * Tests for AuthProvider (lib/auth-context.tsx).
 *
 * Strategy: mock getMe, getSupabaseBrowserClient, and useRouter so we can
 * exercise the client-side auth state machine without a real Supabase/Next.js
 * server. Covers the three terminal states: authenticated, 401→redirect, error.
 *
 * This is the highest-risk frontend flow: an unauthenticated user must be
 * redirected to /login and their session cleared.
 *
 * vi.hoisted() is required so mock refs are initialised before the vi.mock()
 * factory runs (vitest hoists vi.mock calls above all imports).
 *
 * console.error is suppressed at module scope (not restored between tests) so
 * auth-context's error path log does not race with happy-dom's async teardown.
 */

import { render, waitFor } from "@testing-library/react";
import { useEffect } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api-client";
import { AuthProvider, useAuth } from "@/lib/auth-context";

// ---------------------------------------------------------------------------
// Suppress console.error for the whole file.
// auth-context logs on non-401 failures; happy-dom intercepts console calls
// via async RPC, which races with environment teardown if not suppressed here.
// ---------------------------------------------------------------------------
vi.spyOn(console, "error").mockImplementation(() => {});

// ---------------------------------------------------------------------------
// Hoisted mock refs — must be created before vi.mock() factory executes
// ---------------------------------------------------------------------------

const mockReplace = vi.hoisted(() => vi.fn());
const mockSignOut = vi.hoisted(() => vi.fn().mockResolvedValue({}));
const mockGetMe = vi.hoisted(() => vi.fn());

// ---------------------------------------------------------------------------
// Module mocks
// ---------------------------------------------------------------------------

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mockReplace }),
}));

vi.mock("@/lib/supabase/client", () => ({
  getSupabaseBrowserClient: () => ({ auth: { signOut: mockSignOut } }),
}));

// Partial mock: keep the real ApiError, override only getMe.
vi.mock("@/lib/api-client", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/lib/api-client")>();
  return { ...actual, getMe: mockGetMe };
});

// ---------------------------------------------------------------------------
// Helper: a component that exposes auth state for assertions
// ---------------------------------------------------------------------------

let capturedUser: ReturnType<typeof useAuth>["user"] = null;
let capturedLoading = true;

function Probe() {
  const { user, isLoading } = useAuth();
  // useEffect is the correct place for side effects (external variable mutation).
  // ESLint's react-hooks/globals forbids mutations during render; effects are fine.
  useEffect(() => {
    capturedUser = user;
    capturedLoading = isLoading;
  }, [user, isLoading]);
  return null;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("AuthProvider", () => {
  beforeEach(() => {
    capturedUser = null;
    capturedLoading = true;
    // clearAllMocks() resets call counts but preserves implementations.
    vi.clearAllMocks();
    mockSignOut.mockResolvedValue({});
  });

  it("redirects to /login and signs out when getMe returns 401", async () => {
    mockGetMe.mockRejectedValue(new ApiError(401, "Unauthorized"));

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(mockSignOut).toHaveBeenCalled();
    });
    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith("/login");
    });
  });

  it("sets authenticated user when getMe succeeds", async () => {
    const fakeUser = {
      user_id: 1,
      supabase_uuid: "abc",
      role: "Data Curator",
      permissions: ["analytics:read", "import:run"],
    };
    mockGetMe.mockResolvedValue(fakeUser);

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(capturedLoading).toBe(false);
    });
    expect(capturedUser).toEqual(fakeUser);
    expect(mockReplace).not.toHaveBeenCalled();
  });

  it("does not redirect when getMe fails with a non-401 error", async () => {
    mockGetMe.mockRejectedValue(new ApiError(500, "Internal Server Error"));

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(capturedLoading).toBe(false);
    });
    expect(mockReplace).not.toHaveBeenCalled();
    expect(mockSignOut).not.toHaveBeenCalled();
    expect(capturedUser).toBeNull();
  });
});
