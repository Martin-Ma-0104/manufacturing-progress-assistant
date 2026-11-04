"use client";
import Link from "next/link";
import {
  BarChart,
  Bar,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
  LineChart,
  Line,
  ComposedChart,
} from "recharts";
import { RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { fmt, query } from "@/lib/api";
import { useWorkspace } from "../workspace";
import DataTable from "../data-table";
import InputTrend from "../charts/input-trend";

function range(
  lower: number | null | undefined,
  upper: number | null | undefined,
  factor = 1,
  suffix = "",
) {
  if (lower == null || upper == null) return "Not available";
  if (Math.abs(lower - upper) < 1e-8) return fmt(lower * factor) + suffix;
  // Round outwards so display precision never narrows the assumed range.
  const a = fmt(Math.floor(lower * factor * 10 + 1e-8) / 10),
    b = fmt(Math.ceil(upper * factor * 10 - 1e-8) / 10);
  return `${a}–${b}${suffix}`;
}

export default function Dashboard() {
  const { data, scope, loading, refresh } = useWorkspace();
  if (loading)
    return (
      <div className="grid gap-5 md:grid-cols-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="panel h-32 animate-pulse" />
        ))}
      </div>
    );
  if (!data) return null;
  const s = data.summary;
  const runtime = data.runtime_estimate;
  const kpis = [
    [
      "Planned input",
      fmt(s.planned_rolls, "mother rolls"),
      "Input plan; not a finished-output target",
    ],
    [
      "Actual input",
      fmt(s.input_rolls, "mother rolls"),
      "Recorded input under selected filters",
    ],
    [
      "Input plan attainment",
      s.attainment,
      "Ratio of summed actual / planned input",
    ],
    [
      "Qualified output",
      fmt(s.qualified_output_m2, "m²"),
      "Area of qualified finished production",
    ],
    [
      "Estimated runtime (h)",
      range(
        runtime.runtime_lower_minutes,
        runtime.runtime_upper_minutes,
        1 / 60,
      ),
      "Machine-hours · 12 h shifts − 2 h flexible breaks",
    ],
    [
      "Abnormality records",
      fmt(data.abnormalities.reported_minutes, "min"),
      "Event-minute sum; not net downtime",
    ],
    [
      "Estimated utilization",
      range(runtime.utilization_lower, runtime.utilization_upper, 100, "%"),
      "Range reflects unknown break/stop overlap",
    ],
  ];
  const start = new Date(scope.start + "T12:00:00").getTime(),
    end = new Date(scope.end + "T12:00:00").getTime();
  const daily = [];
  for (let time = start; time <= end; time += 86400000) {
    const key = new Date(time).toISOString().slice(0, 10);
    const r = data.daily.find((d) => d.production_date === key);
    daily.push({
      time,
      planned_rolls: r?.planned_rolls ?? null,
      input_rolls: r?.input_rolls ?? null,
      qualified_output_m2: r?.qualified_output_m2 ?? null,
    });
  }
  const axis = (value: number) =>
    new Date(value).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
    });
  return (
    <div className="space-y-6">
      <div className="flex justify-end">
        <Link
          className="text-sm text-primary underline underline-offset-4"
          href={`/ai-expert?${query(scope)}#research-analysis`}
        >
          Research analysis →
        </Link>
      </div>
      <div className="flex items-center justify-end">
        <div className="flex flex-wrap gap-2">
          <a
            className="rounded-md border border-border px-3 py-2 text-xs"
            href={"/api/reports/selection.pdf?" + query(scope)}
            download
          >
            Download PDF
          </a>
          <a
            className="rounded-md border border-border px-3 py-2 text-xs"
            href={"/api/reports/selection.html?" + query(scope)}
            download
          >
            Download HTML
          </a>
          <Button variant="outline" size="sm" onClick={refresh}>
            <RefreshCw size={14} />
            Refresh
          </Button>
        </div>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {kpis.map(([label, value]) => (
          <Card key={label} className="gap-0 border-border py-0 shadow-none">
            <CardContent className="p-5">
              <div className="text-xs font-medium muted">{label}</div>
              <div className="my-3 break-words text-2xl font-semibold tracking-tight">
                {value}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
      <details className="note">
        <summary>
          Runtime estimate assumptions · {runtime.observed_shift_count}{" "}
          record-evidenced machine shifts
        </summary>
        <div className="mt-3 space-y-2 text-xs">
          {runtime.reason && <p>{runtime.reason}</p>}
          <p>
            Assumed availability:{" "}
            {fmt(
              runtime.available_minutes == null
                ? null
                : runtime.available_minutes / 60,
              "machine-hours",
            )}
            . {runtime.unrecorded_shift_count} unrecorded machine shifts
            excluded; these are not confirmed unscheduled shifts.
          </p>
          <p>
            Merged stop intervals before break overlap:{" "}
            {fmt(runtime.merged_stop_minutes, "min")}.{" "}
            {runtime.no_recorded_stop_shift_count} covered shifts have no
            positive recorded stop interval; unrecorded stops remain unknown.
          </p>
          {runtime.invalid_event_count > 0 && (
            <p>
              {runtime.invalid_event_count} incomplete or contradictory events
              block affected estimates.
            </p>
          )}
          {runtime.assumptions.map((item) => (
            <p key={item}>{item}</p>
          ))}
          <p>
            Reported abnormality totals retain source dates and shift labels.
            Estimates use clock-based shifts and can therefore differ. Product
            filters do not allocate machine time to products. Ranges describe
            assumptions, not measured runtime, OEE or demonstrated capacity.
          </p>
        </div>
      </details>
      <InputTrend
        daily={data.daily}
        events={data.changeovers}
        start={scope.start}
        end={scope.end}
        machine={scope.machine}
        shift={scope.shift}
      />
      <div className="grid gap-6 xl:grid-cols-2">
        <section className="panel">
          <h2>Qualified production trend (m²)</h2>

          <div className="chart">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={daily}>
                <CartesianGrid vertical={false} />
                <XAxis
                  dataKey="time"
                  type="number"
                  domain={[start, end]}
                  tickFormatter={axis}
                />
                <YAxis width={68} />
                <Tooltip labelFormatter={(v) => axis(Number(v))} />
                <Line
                  dataKey="qualified_output_m2"
                  name="Qualified area (m²)"
                  stroke="#328b8c"
                  strokeWidth={2.5}
                  connectNulls
                  dot={{ r: 3 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </section>
        <section className="panel">
          <h2>Machine output comparison (m²)</h2>

          <div className="chart">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.machines}>
                <CartesianGrid vertical={false} />
                <XAxis dataKey="machine_id" />
                <YAxis width={68} />
                <Tooltip />
                <Legend />
                <Bar
                  dataKey="actual_output_m2"
                  name="Actual m²"
                  fill="#a9bfce"
                  radius={[3, 3, 0, 0]}
                />
                <Bar
                  dataKey="qualified_output_m2"
                  name="Qualified m²"
                  fill="#346f9d"
                  radius={[3, 3, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>
        <section className="panel">
          <h2>Abnormality Pareto (event-minutes)</h2>

          {data.abnormalities.categories.length ? (
            <div className="chart">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={data.abnormalities.categories}>
                  <CartesianGrid vertical={false} />
                  <XAxis dataKey="label" tick={{ fontSize: 10 }} interval={0} />
                  <YAxis yAxisId="min" />
                  <YAxis
                    yAxisId="share"
                    orientation="right"
                    domain={[0, 1]}
                    tickFormatter={(v) => `${Math.round(v * 100)}%`}
                  />
                  <Tooltip />
                  <Bar
                    yAxisId="min"
                    dataKey="reported_minutes"
                    name="Event-minutes"
                    fill="#5b83a3"
                  />
                  <Line
                    yAxisId="share"
                    dataKey="cumulative_fraction"
                    name="Cumulative fraction"
                    stroke="#329198"
                  />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="note mt-8">
              No abnormality records in this scope. This does not imply zero
              downtime.
            </div>
          )}
        </section>
      </div>
      <details className="note">
        <summary>
          Confirmed changeover explanations · {data.changeovers.length} events
        </summary>
        <div className="mt-4">
          <DataTable rows={data.changeovers} />
        </div>
      </details>

      <details className="panel machine-records-details">
        <summary>Machine performance records</summary>
        <div className="mt-4">
          <DataTable
            rows={data.machines.map((m) => ({
              machine: m.machine_id,
              planned_input: m.planned_rolls,
              actual_input: m.input_rolls,
              attainment: m.attainment,
              qualified_m2: m.qualified_output_m2,
              area_qualification: m.qualification,
              event_minutes: m.abnormalities.reported_minutes,
              estimated_runtime_hours: range(
                m.runtime_estimate?.runtime_lower_minutes,
                m.runtime_estimate?.runtime_upper_minutes,
                1 / 60,
              ),
              estimated_utilization: range(
                m.runtime_estimate?.utilization_lower,
                m.runtime_estimate?.utilization_upper,
                100,
                "%",
              ),
            }))}
          />
        </div>
      </details>
      <details className="note">
        <summary>Definitions and coverage</summary>
        <p>
          {s.machine_count} recorded machines · {data.records.length} production
          records.
        </p>
        {kpis.map(([label, , detail]) => (
          <p key={label}>
            {label}: {detail}
          </p>
        ))}
        {data.warnings.map((w, i) => (
          <p key={i}>{w}</p>
        ))}
      </details>
    </div>
  );
}
