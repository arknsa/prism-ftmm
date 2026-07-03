"use client";

/**
 * PageShell — consistent loading, error, and permission states for dashboard pages (P6.1).
 */

import type { ReactNode } from "react";

import { Unauthorized } from "@/components/unauthorized";

interface PageShellProps {
  title: string;
  description?: string;
  loading: boolean;
  error: string | null;
  hasPermission: boolean;
  children: ReactNode;
  actions?: ReactNode;
}

export function PageShell({
  title,
  description,
  loading,
  error,
  hasPermission,
  children,
  actions,
}: PageShellProps) {
  if (!hasPermission) {
    return <Unauthorized />;
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
          {description && (
            <p className="text-muted-foreground mt-1 text-sm">{description}</p>
          )}
        </div>
        {actions && <div className="flex gap-2">{actions}</div>}
      </div>

      {error && (
        <div className="bg-destructive/10 text-destructive rounded-md p-4 text-sm">
          {error}
        </div>
      )}

      {loading ? (
        <div className="flex min-h-[40vh] items-center justify-center">
          <span className="text-muted-foreground text-sm">Loading…</span>
        </div>
      ) : (
        children
      )}
    </div>
  );
}
