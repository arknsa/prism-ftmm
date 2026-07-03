"use client";

/**
 * P6.7 — Industry Analytics page.
 *
 * Industry distribution (industry_name) + sector breakdown (sector_name) per D-042.
 *
 * Permission: analytics:read
 */

import { BarChart, ChartCard, PieChart } from "@/components/charts";
import { PageShell } from "@/components/page-shell";
import { useAuth } from "@/lib/auth-context";
import { useDashboardEndpoint } from "@/lib/use-analytics";

interface IndustryAnalyticsResponse {
  industry_distribution: Array<{
    industry_id: number;
    industry_name: string;
    sector_name: string;
    count: number;
  }>;
  sector_breakdown: Array<{
    sector_name: string;
    count: number;
  }>;
}

export default function IndustriesPage() {
  const { user, isLoading } = useAuth();
  const { data, loading, error } = useDashboardEndpoint<IndustryAnalyticsResponse>(
    "/api/v1/analytics/industries",
  );

  return (
    <PageShell
      title="Industry Analytics"
      description="Industry and sector distribution of validated alumni in current roles (D-042)."
      loading={isLoading || loading}
      error={error}
      hasPermission={!!user && user.permissions.includes("analytics:read")}
    >
      {data && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <ChartCard title="By Industry">
            <BarChart
              data={data.industry_distribution.slice(0, 20).map((r) => ({
                label: r.industry_name,
                value: r.count,
              }))}
              valueLabel="Alumni"
            />
          </ChartCard>

          <ChartCard title="By Sector">
            <PieChart
              data={data.sector_breakdown.map((r) => ({
                name: r.sector_name,
                value: r.count,
              }))}
            />
          </ChartCard>
        </div>
      )}
    </PageShell>
  );
}
