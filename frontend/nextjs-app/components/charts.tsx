"use client";

/**
 * Reusable ECharts wrappers (P6.3).
 *
 * All chart components are thin wrappers over echarts-for-react with
 * consistent theming (responsive width, neutral palette, tooltip).
 *
 * Charts:
 *   BarChart     — horizontal or vertical bar (ranked list / distribution)
 *   PieChart     — donut chart (category distribution)
 *   RankedList   — plain ranked table list (no canvas) for long data sets
 *
 * Usage: import { BarChart, PieChart, RankedList } from "@/components/charts";
 */

import type { ReactNode } from "react";

import ReactECharts from "echarts-for-react";

// ---------------------------------------------------------------------------
// Colour palette — neutral, accessible
// ---------------------------------------------------------------------------

const PALETTE = [
  "#3b82f6", // blue-500
  "#10b981", // emerald-500
  "#f59e0b", // amber-500
  "#8b5cf6", // violet-500
  "#ef4444", // red-500
  "#06b6d4", // cyan-500
  "#ec4899", // pink-500
  "#14b8a6", // teal-500
  "#f97316", // orange-500
  "#6366f1", // indigo-500
];

// ---------------------------------------------------------------------------
// BarChart
// ---------------------------------------------------------------------------

export interface BarChartItem {
  label: string;
  value: number;
}

interface BarChartProps {
  data: BarChartItem[];
  title?: string;
  valueLabel?: string;
  horizontal?: boolean;
  height?: number;
}

export function BarChart({
  data,
  title,
  valueLabel = "Count",
  horizontal = true,
  height = 320,
}: BarChartProps) {
  if (data.length === 0) {
    return <EmptyState />;
  }

  const labels = data.map((d) => d.label);
  const values = data.map((d) => d.value);

  const option = horizontal
    ? {
        tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
        grid: { left: "3%", right: "8%", bottom: "3%", containLabel: true },
        xAxis: { type: "value", name: valueLabel },
        yAxis: { type: "category", data: labels, inverse: true },
        series: [
          {
            type: "bar",
            data: values,
            itemStyle: { color: PALETTE[0] },
            label: { show: true, position: "right", fontSize: 11 },
          },
        ],
        ...(title ? { title: { text: title, textStyle: { fontSize: 13 } } } : {}),
      }
    : {
        tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
        grid: { left: "3%", right: "4%", bottom: "3%", containLabel: true },
        xAxis: { type: "category", data: labels, axisLabel: { rotate: 30 } },
        yAxis: { type: "value", name: valueLabel },
        series: [
          {
            type: "bar",
            data: values,
            itemStyle: { color: PALETTE[0] },
            label: { show: true, position: "top", fontSize: 11 },
          },
        ],
        ...(title ? { title: { text: title, textStyle: { fontSize: 13 } } } : {}),
      };

  return (
    <ReactECharts
      option={option}
      style={{ height, width: "100%" }}
      opts={{ renderer: "svg" }}
    />
  );
}

// ---------------------------------------------------------------------------
// PieChart (donut)
// ---------------------------------------------------------------------------

export interface PieChartItem {
  name: string;
  value: number;
}

interface PieChartProps {
  data: PieChartItem[];
  title?: string;
  height?: number;
}

export function PieChart({ data, title, height = 300 }: PieChartProps) {
  if (data.length === 0) {
    return <EmptyState />;
  }

  const option = {
    tooltip: { trigger: "item", formatter: "{b}: {c} ({d}%)" },
    legend: { orient: "vertical", left: "left", top: "middle", type: "scroll" },
    series: [
      {
        type: "pie",
        radius: ["40%", "70%"],
        center: ["60%", "50%"],
        data: data.map((d, i) => ({
          name: d.name,
          value: d.value,
          itemStyle: { color: PALETTE[i % PALETTE.length] },
        })),
        label: { show: false },
        emphasis: { label: { show: true, fontSize: 13, fontWeight: "bold" } },
      },
    ],
    ...(title ? { title: { text: title, textStyle: { fontSize: 13 } } } : {}),
  };

  return (
    <ReactECharts
      option={option}
      style={{ height, width: "100%" }}
      opts={{ renderer: "svg" }}
    />
  );
}

// ---------------------------------------------------------------------------
// RankedList — plain table for large ranked datasets
// ---------------------------------------------------------------------------

export interface RankedListItem {
  rank: number;
  label: string;
  value: number;
  sublabel?: string;
}

interface RankedListProps {
  items: RankedListItem[];
  valueLabel?: string;
}

export function RankedList({ items, valueLabel = "Count" }: RankedListProps) {
  if (items.length === 0) {
    return <EmptyState />;
  }
  const max = Math.max(...items.map((i) => i.value));

  return (
    <ul className="divide-border divide-y text-sm">
      {items.map((item) => (
        <li key={item.rank} className="flex items-center gap-3 py-2">
          <span className="text-muted-foreground w-6 text-right font-mono text-xs">
            {item.rank}
          </span>
          <div className="min-w-0 flex-1">
            <div className="truncate font-medium">{item.label}</div>
            {item.sublabel && (
              <div className="text-muted-foreground truncate text-xs">{item.sublabel}</div>
            )}
            <div
              className="mt-1 h-1.5 rounded-full bg-blue-500/20"
              style={{ width: "100%" }}
            >
              <div
                className="h-1.5 rounded-full bg-blue-500"
                style={{ width: `${(item.value / max) * 100}%` }}
              />
            </div>
          </div>
          <span className="text-muted-foreground tabular-nums">
            {item.value.toLocaleString()} <span className="text-xs">{valueLabel}</span>
          </span>
        </li>
      ))}
    </ul>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function EmptyState() {
  return (
    <div className="text-muted-foreground flex h-32 items-center justify-center text-sm">
      No data available for the selected filters.
    </div>
  );
}

export function ChartCard({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="bg-card text-card-foreground rounded-lg border p-4 shadow-sm">
      <h3 className="mb-3 text-sm font-semibold">{title}</h3>
      {children}
    </div>
  );
}

export function StatCard({
  label,
  value,
}: {
  label: string;
  value: number | string;
}) {
  return (
    <div className="bg-card text-card-foreground rounded-lg border p-4 shadow-sm">
      <div className="text-muted-foreground text-xs">{label}</div>
      <div className="mt-1 text-2xl font-bold tabular-nums">
        {typeof value === "number" ? value.toLocaleString() : value}
      </div>
    </div>
  );
}
