import Link from "next/link";

export function Unauthorized() {
  return (
    <div className="flex min-h-[40vh] flex-col items-center justify-center gap-4 text-center">
      <h2 className="text-2xl font-bold tracking-tight">Access Denied</h2>
      <p className="text-muted-foreground max-w-sm text-sm">
        You do not have permission to view this page. Contact your administrator if you believe
        this is an error.
      </p>
      <Link
        href="/"
        className="text-primary text-sm font-medium underline-offset-4 hover:underline"
      >
        Back to dashboard
      </Link>
    </div>
  );
}
