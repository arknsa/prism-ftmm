"use client";

import { Unauthorized } from "@/components/unauthorized";
import { useAuth } from "@/lib/auth-context";

export default function AdminPage() {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <span className="text-muted-foreground text-sm">Loading…</span>
      </div>
    );
  }

  if (!user || !user.permissions.includes("user:manage")) {
    return <Unauthorized />;
  }

  return (
    <div className="mx-auto max-w-2xl p-8">
      <h1 className="text-2xl font-bold tracking-tight">Admin</h1>
      <p className="text-muted-foreground mt-2 text-sm">
        User management and system administration. Only users with the{" "}
        <code>user:manage</code> permission can access this page.
      </p>
    </div>
  );
}
