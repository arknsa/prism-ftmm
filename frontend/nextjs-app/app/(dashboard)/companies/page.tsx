"use client";

/**
 * P6.6 — Company Analytics page.
 *
 * Top employers by headcount of validated alumni in current roles.
 *
 * Permission: analytics:read
 */

import { ChartCard, RankedList, StatCard } from "@/components/charts";
import { PageShell } from "@/components/page-shell";
import { useAuth } from "@/lib/auth-context";
import { useDashboardEndpoint } from "@/lib/use-analytics";

interface CompanyAnalyticsResponse {
  total_employers: number;
  top_employers: Array<{
    company_id: number;
    canonical_name: string;
    headcount: number;
  }>;
}

export default function CompaniesAnalyticsPage() {
  const { user, isLoading } = useAuth();
  const { data, loading, error } = useDashboardEndpoint<CompanyAnalyticsResponse>(
    "/api/v1/analytics/companies",
  );

  return (
    <PageShell
      title="Company Analytics"
      description="Top employers of validated alumni based on current career records."
      loading={isLoading || loading}
      error={error}
      hasPermission={!!user && user.permissions.includes("analytics:read")}
    >
      {data && (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <StatCard label="Distinct Employers" value={data.total_employers} />
          </div>

          <ChartCard title="Top Employers (by headcount)">
            <RankedList
              items={data.top_employers.map((e, i) => ({
                rank: i + 1,
                label: e.canonical_name,
                value: e.headcount,
              }))}
              valueLabel="alumni"
            />
          </ChartCard>
        </>
      )}
    </PageShell>
  );
}
