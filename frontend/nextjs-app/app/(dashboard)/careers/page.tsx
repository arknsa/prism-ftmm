"use client";

/**
 * P6.5 — Career Outcomes page.
 *
 * Employed vs Not Reported distribution (D-048), seniority distribution,
 * and top role titles.
 *
 * Permission: analytics:read
 */

import { BarChart, ChartCard, PieChart, RankedList, StatCard } from "@/components/charts";
import { PageShell } from "@/components/page-shell";
import { useAuth } from "@/lib/auth-context";
import { useDashboardEndpoint } from "@/lib/use-analytics";

interface CareerOutcomesResponse {
  total_validated: number;
  employed_count: number;
  not_reported_count: number;
  seniority_distribution: Array<{ seniority: string; count: number }>;
  top_roles: Array<{ role_title: string; count: number }>;
}

export default function CareersPage() {
  const { user, isLoading } = useAuth();
  const { data, loading, error } = useDashboardEndpoint<CareerOutcomesResponse>(
    "/api/v1/analytics/career-outcomes",
  );

  return (
    <PageShell
      title="Career Outcomes"
      description="Employment status and career data for validated alumni. 'Employed' means a current career record exists; 'Not Reported' means none is recorded — no unemployment rate is asserted."
      loading={isLoading || loading}
      error={error}
      hasPermission={!!user && user.permissions.includes("analytics:read")}
    >
      {data && (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <StatCard label="Total Validated Alumni" value={data.total_validated} />
            <StatCard label="Employed" value={data.employed_count} />
            <StatCard label="Not Reported" value={data.not_reported_count} />
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <ChartCard title="Employment Status">
              <PieChart
                data={[
                  { name: "Employed", value: data.employed_count },
                  { name: "Not Reported", value: data.not_reported_count },
                ].filter((d) => d.value > 0)}
              />
            </ChartCard>

            <ChartCard title="Seniority Distribution">
              <BarChart
                data={data.seniority_distribution.map((r) => ({
                  label: r.seniority,
                  value: r.count,
                }))}
                valueLabel="Alumni"
              />
            </ChartCard>
          </div>

          <ChartCard title="Top Role Titles">
            <RankedList
              items={data.top_roles.slice(0, 20).map((r, i) => ({
                rank: i + 1,
                label: r.role_title,
                value: r.count,
              }))}
              valueLabel="alumni"
            />
          </ChartCard>
        </>
      )}
    </PageShell>
  );
}
