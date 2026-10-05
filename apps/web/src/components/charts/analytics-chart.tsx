"use client";

import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { NLQQueryResponse, QueryCell, QueryRow } from "@/types/nlq";

type ChartDatum = {
  label: string;
  value: number;
};

const chartPalette = ["#176659", "#3f8a79", "#86b7a8", "#d1a663", "#7d9690", "#d9856a"];

function chartLabel(value: QueryCell): string {
  if (value === null) {
    return "Unknown";
  }
  if (typeof value === "boolean") {
    return value ? "Yes" : "No";
  }
  return String(value);
}

function numericValue(value: QueryCell): number | null {
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : null;
  }
  if (typeof value !== "string" || !value.trim()) {
    return null;
  }
  const parsed = Number(value.replaceAll(",", ""));
  return Number.isFinite(parsed) ? parsed : null;
}

function createChartData(rows: QueryRow[], xAxis: string, yAxis: string): ChartDatum[] {
  return rows.flatMap((row) => {
    const value = numericValue(row[yAxis] ?? null);
    return value === null ? [] : [{ label: chartLabel(row[xAxis] ?? null), value }];
  });
}

function prettyName(value: string): string {
  return value.replaceAll("_", " ");
}

function ChartEmptyState({ children }: Readonly<{ children: React.ReactNode }>) {
  return <div className="grid h-80 place-items-center rounded-xl border border-dashed bg-secondary/25 px-6 text-center text-sm leading-6 text-muted-foreground">{children}</div>;
}

export function AnalyticsChart({ result }: Readonly<{ result: NLQQueryResponse }>) {
  const { visualization } = result;
  if (visualization.type === "table") {
    return <ChartEmptyState>The query recommends a table for this result.</ChartEmptyState>;
  }
  if (!visualization.xAxis || !visualization.yAxis) {
    return <ChartEmptyState>This result does not contain the axes needed for a chart.</ChartEmptyState>;
  }

  const data = createChartData(result.rows, visualization.xAxis, visualization.yAxis);
  if (!data.length) {
    return <ChartEmptyState>The selected metric does not contain numeric values to chart.</ChartEmptyState>;
  }

  const commonAxes = (
    <>
      <CartesianGrid vertical={false} stroke="#e1e6de" />
      <XAxis dataKey="label" tickLine={false} axisLine={false} tick={{ fill: "#62716a", fontSize: 12 }} />
      <YAxis tickLine={false} axisLine={false} tick={{ fill: "#62716a", fontSize: 12 }} width={56} />
      <Tooltip cursor={{ fill: "#e6eee780" }} />
      <Legend />
    </>
  );

  const chartName = prettyName(visualization.yAxis);
  const chart = (() => {
    switch (visualization.type) {
      case "bar":
        return (
          <BarChart data={data} accessibilityLayer>
            {commonAxes}
            <Bar dataKey="value" name={chartName} fill="#176659" radius={[5, 5, 0, 0]} />
          </BarChart>
        );
      case "line":
        return (
          <LineChart data={data} accessibilityLayer>
            {commonAxes}
            <Line type="monotone" dataKey="value" name={chartName} stroke="#176659" strokeWidth={2.5} dot={{ r: 3 }} activeDot={{ r: 5 }} />
          </LineChart>
        );
      case "area":
        return (
          <AreaChart data={data} accessibilityLayer>
            {commonAxes}
            <Area type="monotone" dataKey="value" name={chartName} stroke="#176659" fill="#86b7a8" fillOpacity={0.55} strokeWidth={2.5} />
          </AreaChart>
        );
      case "pie":
        return (
          <PieChart accessibilityLayer>
            <Tooltip />
            <Legend />
            <Pie data={data} dataKey="value" nameKey="label" name={chartName} cx="50%" cy="50%" outerRadius="72%" paddingAngle={2}>
              {data.map((datum, index) => <Cell key={`${datum.label}-${index}`} fill={chartPalette[index % chartPalette.length] ?? chartPalette[0]} />)}
            </Pie>
          </PieChart>
        );
    }
  })();
  return (
    <figure aria-labelledby="chart-title">
      <figcaption id="chart-title" className="mb-4 text-sm text-muted-foreground">{prettyName(visualization.type)} chart · {prettyName(visualization.yAxis)} by {prettyName(visualization.xAxis)}</figcaption>
      <div className="h-80 rounded-xl border bg-background p-4 sm:p-5">
        <ResponsiveContainer width="100%" height="100%">{chart}</ResponsiveContainer>
      </div>
    </figure>
  );
}
