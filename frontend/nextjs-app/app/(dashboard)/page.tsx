"use client";

/**
 * P6.4 — Executive Overview page.
 *
 * KPIs (total alumni, companies, industries, countries) + alumni-by-program
 * bar chart + alumni-by-graduation-year bar chart.
 *
 * Permission: analytics:read
 */

import { BarChart, ChartCard, StatCard } from "@/components/charts";
import { PageShell } from "@/components/page-shell";
import { useAuth } from "@/lib/auth-context";
import { useDashboardEndpoint } from "@/lib/use-analytics";

interface OverviewResponse {
  total_alumni: number;
  total_companies: number;
  total_industries: number;
  total_countries: number;
  alumni_by_program: Array<{ program_name: string; count: number }>;
  alumni_by_graduation_year: Array<{ graduation_year: number; count: number }>;
}

export default function OverviewPage() {
  const { user, isLoading } = useAuth();
  const { data, loading, error } = useDashboardEndpoint<OverviewResponse>(
    "/api/v1/analytics/overview",
  );

  return (
    <PageShell
      title="Executive Overview"
      description="High-level alumni and career statistics for validated records only."
      loading={isLoading || loading}
      error={error}
      hasPermission={!!user && user.permissions.includes("analytics:read")}
    >
      {data && (
        <>
          {/* KPI row */}
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <StatCard label="Validated Alumni" value={data.total_alumni} />
            <StatCard label="Employers" value={data.total_companies} />
            <StatCard label="Industries" value={data.total_industries} />
            <StatCard label="Countries" value={data.total_countries} />
          </div>

          {/* Charts */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <ChartCard title="Alumni by Program">
              <BarChart
                data={data.alumni_by_program.map((r) => ({
                  label: r.program_name,
                  value: r.count,
                }))}
                valueLabel="Alumni"
              />
            </ChartCard>

            <ChartCard title="Alumni by Graduation Year">
              <BarChart
                data={data.alumni_by_graduation_year.map((r) => ({
                  label: String(r.graduation_year),
                  value: r.count,
                }))}
                valueLabel="Alumni"
                horizontal={false}
              />
            </ChartCard>
          </div>
        </>
      )}
    </PageShell>
  );
}
