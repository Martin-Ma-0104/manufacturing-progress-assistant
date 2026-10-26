"use client";
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
  ReferenceLine,
} from "recharts";
import { RefreshCw, Clock3 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { fmt, query } from "@/lib/api";
import { useWorkspace } from "../workspace";
import DataTable from "../data-table";
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
      "Average cycle time",
      "Not available",
      "Measured cycle records are not connected",
    ],
    [
      "Abnormality records",
      fmt(data.abnormalities.reported_minutes, "min"),
      "Event-minute sum; not net downtime",
    ],
    [
      "Machine utilization",
      "Not available",
      "Runtime and available time are required",
    ],
    [
      "Estimated capacity",
      "Scenario tool",
      "Use explicit assumptions in Planning",
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
  const changeDates = [
    ...new Set(data.changeovers.map((c) => c.production_date)),
  ].filter(Boolean);
  const changeMarkers = changeDates.map((date) => (
    <ReferenceLine
      key={date}
      x={new Date(date + "T12:00:00").getTime()}
      stroke="#8655ba"
      strokeDasharray="4 5"
      label={{
        value: "Changeover",
        position: "insideTopRight",
        fontSize: 10,
        fill: "#8655ba",
      }}
    />
  ));
  const axis = (value: number) =>
    new Date(value).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
    });
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <span className="text-xs muted">
          {s.machine_count} recorded machines · {data.records.length} production
          records · area qualification {s.qualification}
        </span>
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
        {kpis.map(([label, value, detail]) => (
          <Card key={label} className="gap-0 border-border py-0 shadow-none">
            <CardContent className="p-5">
              <div className="text-xs font-medium muted">{label}</div>
              <div className="my-3 break-words text-2xl font-semibold tracking-tight">
                {value}
              </div>
              <p className="text-[11px] muted">{detail}</p>
            </CardContent>
          </Card>
        ))}
      </div>
      <div className="grid gap-6 xl:grid-cols-2">
        <section className="panel">
          <div className="flex justify-between">
            <div>
              <h2>Planned vs. actual input</h2>
              <p className="text-xs muted">
                Mother rolls · dashed plan reference · select one machine for
                changeover markers
              </p>
            </div>
            <Badge variant="outline">Historical</Badge>
          </div>
          <div className="chart">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={daily}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis
                  dataKey="time"
                  type="number"
                  domain={[start, end]}
                  tickFormatter={axis}
                />
                <YAxis />
                <Tooltip labelFormatter={(v) => axis(Number(v))} />
                <Legend />
                {scope.machine && changeMarkers}
                <Line
                  name="Actual input"
                  dataKey="input_rolls"
                  stroke="#2d6b9c"
                  strokeWidth={2.5}
                  connectNulls
                  dot={{ r: 3 }}
                />
                <Line
                  name="Planned input"
                  dataKey="planned_rolls"
                  stroke="#8192a8"
                  strokeDasharray="6 5"
                  connectNulls
                  dot={{ r: 3 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </section>
        <section className="panel">
          <h2>Qualified production trend</h2>
          <p className="text-xs muted">
            m² · missing dates have no inferred observations
          </p>
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
          <h2>Machine output comparison</h2>
          <p className="text-xs muted">
            Actual and qualified area · no performance ranking
          </p>
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
          <h2>Abnormality Pareto</h2>
          <p className="text-xs muted">
            Recorded event-minutes by category · cumulative share of known
            minutes
          </p>
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
      <section className="panel">
        <h2>Cycle time trend</h2>
        <div className="mt-4 flex items-center gap-3 rounded-lg bg-secondary p-5 text-sm muted">
          <Clock3 size={20} />
          Measured per-cycle timestamps and runtime are not connected. Use the
          Planning scenario calculator; no artificial CT series is shown as real
          data.
        </div>
      </section>
      <section className="panel">
        <h2 className="mb-4">Machine performance records</h2>
        <DataTable
          rows={data.machines.map((m) => ({
            machine: m.machine_id,
            source_status: m.status,
            planned_input: m.planned_rolls,
            actual_input: m.input_rolls,
            attainment: m.attainment,
            qualified_m2: m.qualified_output_m2,
            area_qualification: m.qualification,
            event_minutes: m.abnormalities.reported_minutes,
            cycle_minutes: m.cycle_minutes,
          }))}
        />
      </section>
      <details className="note">
        <summary>Coverage and calculation notes</summary>
        {data.warnings.map((w, i) => (
          <p key={i}>{w}</p>
        ))}
      </details>
    </div>
  );
}
