export const dynamic = "force-dynamic";

import { redirect } from "next/navigation";
import type { ReactNode } from "react";

import { FilterBar } from "@/components/filter-bar";
import { Nav } from "@/components/nav";
import { AuthProvider } from "@/lib/auth-context";
import { FilterProvider } from "@/lib/filter-context";
import { getSupabaseServerClient } from "@/lib/supabase/server";

export default async function DashboardLayout({ children }: { children: ReactNode }) {
  const supabase = await getSupabaseServerClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    redirect("/login");
  }

  return (
    <AuthProvider>
      <FilterProvider>
        <Nav />
        <FilterBar />
        <main className="flex-1">{children}</main>
      </FilterProvider>
    </AuthProvider>
  );
}
