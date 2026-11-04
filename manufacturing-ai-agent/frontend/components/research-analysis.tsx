"use client";
import { useEffect, useState } from "react";
import { api, query, type ResearchAnalysis as Analysis } from "@/lib/api";
import { useWorkspace } from "./workspace";
import DataTable from "./data-table";
import { Button } from "./ui/button";

const fmt = (value: number | null) =>
  value === null
    ? "Not available"
    : value.toLocaleString("en-US", { maximumFractionDigits: 6 });

function PairBars({ rows }: { rows: Analysis["comparison"]["by_machine"] }) {
  const maximum = Math.max(
    1,
    ...rows.flatMap((r) => [r.planned_inputs ?? 0, r.actual_inputs ?? 0]),
  );
  return (
    <div
      className="research-bars"
      aria-label="Planned and actual input mother rolls by machine"
    >
      {rows.map((row) => (
        <div key={row.machine_id}>
          <h4>{row.machine_id}</h4>
          {(
            [
              ["Planned input", row.planned_inputs, "plan"],
              ["Actual input", row.actual_inputs, "actual"],
            ] as const
          ).map(([label, value, color]) => (
            <div className="research-bar-row" key={label}>
              <span>{label}</span>
              <div className="research-bar-track" aria-hidden="true">
                <div
                  className={color}
                  style={{
                    width: `${value === null ? 0 : (100 * value) / maximum}%`,
                  }}
                />
              </div>
              <strong>{fmt(value)}</strong>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
function RankedBars({ rows }: { rows: Analysis["abnormalities"]["rankings"] }) {
  const maximum = Math.max(1, ...rows.map((r) => r.reported_minutes ?? 0));
  return (
    <ol
      className="research-bars"
      aria-label="Machines ranked by known recorded abnormality event-minutes"
    >
      {rows.map((row) => (
        <li key={row.machine_id}>
          <div className="flex flex-wrap justify-between gap-2 text-sm">
            <span>
              Rank {row.rank} · {row.machine_id}
              {row.partial ? " · Partial subtotal" : ""}
            </span>
            <strong>{fmt(row.reported_minutes)} min</strong>
          </div>
          <div className="research-bar-track mt-2" aria-hidden="true">
            <div
              className="actual"
              style={{
                width: `${(100 * (row.reported_minutes ?? 0)) / maximum}%`,
              }}
            />
          </div>
        </li>
      ))}
    </ol>
  );
}
export default function ResearchAnalysis() {
  const { scope, setScope, refreshVersion } = useWorkspace();
  const [task, setTask] = useState<"inputs" | "abnormalities">("inputs");
  const [result, setResult] = useState<{ key: string; value: Analysis }>();
  const [failure, setFailure] = useState<{ key: string; message: string }>();
  const search = query(scope),
    key = `${search}#${refreshVersion}`;
  const supported = !!scope.start && !!scope.end && !scope.product;
  const value = result?.key === key ? result.value : undefined;
  const error = failure?.key === key ? failure.message : undefined;
  useEffect(() => {
    if (!supported) return;
    let active = true;
    api<Analysis>(`/research/analysis?${search}`)
      .then((value) => {
        if (active) setResult({ key, value });
      })
      .catch((e: Error) => {
        if (active) setFailure({ key, message: e.message });
      });
    return () => {
      active = false;
    };
  }, [search, key, supported]);
  const input = value?.comparison,
    events = value?.abnormalities;
  return (
    <section
      className="panel research-analysis"
      id="research-analysis"
      aria-labelledby="research-title"
    >
      <h2 id="research-title">Verified production analysis</h2>
      <div
        className="flex flex-wrap gap-2 mt-4"
        role="group"
        aria-label="Research analysis type"
      >
        <Button
          variant={task === "inputs" ? "default" : "outline"}
          aria-pressed={task === "inputs"}
          onClick={() => setTask("inputs")}
        >
          Input comparison (mother rolls)
        </Button>
        <Button
          variant={task === "abnormalities" ? "default" : "outline"}
          aria-pressed={task === "abnormalities"}
          onClick={() => setTask("abnormalities")}
        >
          Abnormality duration
        </Button>
      </div>
      {scope.product ? (
        <div className="note mt-4">
          <p>
            This analysis uses dates, machine and shift. Clear the product
            filter to use these tools.
          </p>
          <Button
            variant="outline"
            className="mt-3"
            onClick={() => setScope({ ...scope, product: "" })}
          >
            Clear product filter
          </Button>
        </div>
      ) : !supported ? (
        <p className="note mt-4">Select both dates to begin.</p>
      ) : error ? (
        <p role="alert" className="note mt-4">
          {error}
        </p>
      ) : !value ? (
        <p role="status" className="muted text-sm mt-4">
          Reading the selected records…
        </p>
      ) : task === "inputs" && input ? (
        <div className="mt-5 space-y-5">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {(
              [
                ["Planned input", input.planned_inputs],
                ["Actual input", input.actual_inputs],
                ["Difference: actual − plan", input.difference],
                ["Record-level shortfall", input.shortfall],
              ] as const
            ).map(([label, number]) => (
              <div key={label} className="research-metric">
                <p className="text-xs muted">{label}</p>
                <strong>
                  {number === null ? fmt(number) : `${fmt(number)} rolls`}
                </strong>
              </div>
            ))}
          </div>

          {input.by_machine.length ? (
            <>
              <h3>Input by machine · mother rolls</h3>
              <PairBars rows={input.by_machine} />
              <DataTable
                rows={input.by_machine.map((r) => ({
                  machine: r.machine_id,
                  planned_input: r.planned_inputs,
                  actual_input: r.actual_inputs,
                  difference: r.difference,
                  record_shortfall: r.shortfall,
                  net_shortfall: r.net_shortfall,
                  excess: r.excess,
                  records: r.record_count,
                }))}
              />
            </>
          ) : (
            <p className="note">
              No production records in this scope. Values are unavailable.
            </p>
          )}

          {!!input.missing_dates.length && (
            <details className="note">
              <summary>Missing production dates</summary>
              <p className="mt-2">{input.missing_dates.join(", ")}</p>
            </details>
          )}
          <details className="note">
            <summary>Input definitions and coverage</summary>
            <p className="mt-2">
              {input.recorded_dates.length} recorded dates;{" "}
              {input.missing_dates.length} dates without records.
            </p>
            <ul className="mt-2 space-y-2">
              {input.warnings.map((text) => (
                <li key={text}>{text}</li>
              ))}
            </ul>
          </details>
        </div>
      ) : events ? (
        <div className="mt-5 space-y-5">
          {events.rankings.length ? (
            <>
              <h3>Known abnormality duration · recorded event-minutes</h3>
              <RankedBars rows={events.rankings} />
              <DataTable
                rows={events.rankings.map((r) => ({
                  rank: r.rank,
                  machine: r.machine_id,
                  recorded_event_minutes: r.reported_minutes,
                  events: r.event_count,
                  missing_minutes: r.missing_minutes_count,
                  open_events: r.open_count,
                  overlap_events: r.overlap_event_count,
                  coverage: r.partial
                    ? "Partial known subtotal"
                    : "Known subtotal",
                }))}
              />
            </>
          ) : (
            <p className="note">
              No machines have known recorded minutes in this scope. No numeric
              ranking is available.
            </p>
          )}
          {!!events.unranked.length && (
            <details className="note">
              <summary>Unranked machines ({events.unranked.length})</summary>
              <DataTable
                rows={events.unranked.map((r) => ({
                  machine: r.machine_id,
                  reason:
                    r.reason === "missing_duration"
                      ? "Recorded duration unknown"
                      : "No event records",
                  events: r.event_count,
                }))}
              />
            </details>
          )}
          <details className="note">
            <summary>Event definitions and coverage</summary>
            <p className="mt-2">
              Incomplete timestamps: {events.incomplete_time_count} · Unknown
              shifts: {events.unknown_shift_count} · Duration mismatches:{" "}
              {events.mismatch_count} · Unknown status:{" "}
              {events.unknown_status_count}
            </p>
            <ul className="mt-2 space-y-2">
              {events.warnings.map((text) => (
                <li key={text}>{text}</li>
              ))}
            </ul>
          </details>
        </div>
      ) : null}
    </section>
  );
}
