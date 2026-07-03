"use client";

/**
 * P6.8 — Geographic Analytics page.
 *
 * Country distribution bar chart + top cities ranked list.
 *
 * Permission: analytics:read
 */

import { BarChart, ChartCard, RankedList } from "@/components/charts";
import { PageShell } from "@/components/page-shell";
import { useAuth } from "@/lib/auth-context";
import { useDashboardEndpoint } from "@/lib/use-analytics";

interface GeographyResponse {
  country_distribution: Array<{ country: string; count: number }>;
  city_distribution: Array<{ country: string; city: string; count: number }>;
}

export default function GeographyPage() {
  const { user, isLoading } = useAuth();
  const { data, loading, error } = useDashboardEndpoint<GeographyResponse>(
    "/api/v1/analytics/geography",
  );

  return (
    <PageShell
      title="Geographic Analytics"
      description="Country and city distribution of validated alumni based on company location."
      loading={isLoading || loading}
      error={error}
      hasPermission={!!user && user.permissions.includes("analytics:read")}
    >
      {data && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <ChartCard title="By Country">
            <BarChart
              data={data.country_distribution.map((r) => ({
                label: r.country,
                value: r.count,
              }))}
              valueLabel="Alumni"
            />
          </ChartCard>

          <ChartCard title="Top Cities">
            <RankedList
              items={data.city_distribution.slice(0, 20).map((r, i) => ({
                rank: i + 1,
                label: r.city,
                sublabel: r.country,
                value: r.count,
              }))}
              valueLabel="alumni"
            />
          </ChartCard>
        </div>
      )}
    </PageShell>
  );
}
