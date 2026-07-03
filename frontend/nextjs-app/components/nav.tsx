"use client";

import Link from "next/link";

import { signOut } from "@/app/(auth)/login/actions";
import { useAuth } from "@/lib/auth-context";

export function Nav() {
  const { user, isLoading } = useAuth();

  if (isLoading || !user) {
    return null;
  }

  return (
    <nav className="border-b bg-background px-6 py-3">
      <div className="mx-auto flex max-w-5xl items-center justify-between">
        <div className="flex items-center gap-6">
          <Link href="/" className="text-sm font-semibold tracking-tight">
            FTMM Dashboard
          </Link>

          {user.permissions.includes("analytics:read") && (
            <>
              <Link href="/" className="text-muted-foreground hover:text-foreground text-sm">
                Overview
              </Link>
              <Link
                href="/careers"
                className="text-muted-foreground hover:text-foreground text-sm"
              >
                Careers
              </Link>
              <Link
                href="/companies"
                className="text-muted-foreground hover:text-foreground text-sm"
              >
                Companies
              </Link>
              <Link
                href="/industries"
                className="text-muted-foreground hover:text-foreground text-sm"
              >
                Industries
              </Link>
              <Link
                href="/geography"
                className="text-muted-foreground hover:text-foreground text-sm"
              >
                Geography
              </Link>
              <Link
                href="/directory"
                className="text-muted-foreground hover:text-foreground text-sm"
              >
                Directory
              </Link>
            </>
          )}

          {user.permissions.includes("user:manage") && (
            <Link href="/admin" className="text-muted-foreground hover:text-foreground text-sm">
              Admin
            </Link>
          )}

          {user.permissions.includes("import:run") && (
            <Link
              href="/curator/import"
              className="text-muted-foreground hover:text-foreground text-sm"
            >
              Import
            </Link>
          )}

          {user.permissions.includes("alumni:validate") && (
            <Link
              href="/curator/validation"
              className="text-muted-foreground hover:text-foreground text-sm"
            >
              Validate
            </Link>
          )}

          {user.permissions.includes("dedup:review") && (
            <Link
              href="/curator/dedup"
              className="text-muted-foreground hover:text-foreground text-sm"
            >
              Dedup
            </Link>
          )}

          {user.permissions.includes("company:read") && (
            <Link
              href="/curator/companies"
              className="text-muted-foreground hover:text-foreground text-sm"
            >
              Employers
            </Link>
          )}

          {user.permissions.includes("snapshot:manage") && (
            <Link
              href="/curator/snapshots"
              className="text-muted-foreground hover:text-foreground text-sm"
            >
              Snapshots
            </Link>
          )}
        </div>

        <div className="flex items-center gap-4">
          <span className="text-muted-foreground text-xs">{user.role}</span>
          <form action={signOut}>
            <button type="submit" className="text-muted-foreground hover:text-foreground text-sm">
              Sign out
            </button>
          </form>
        </div>
      </div>
    </nav>
  );
}
