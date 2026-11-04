"use client";
import { useEffect, useState } from "react";
import {
  CartesianGrid,
  LabelList,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  type LabelProps,
} from "recharts";
import {
  api,
  query,
  type QualityGroup,
  type QualityRecords,
  type QualitySummary,
} from "@/lib/api";
import { calendarWindow, dateTicks, shortDate } from "@/lib/trend-layout";
import { useWorkspace } from "./workspace";
import DataTable from "./data-table";
import { Button } from "./ui/button";

const areaFormat = new Intl.NumberFormat("en-US", { maximumFractionDigits: 6 });
export function areaDisplay(value: string | null) {
  return value === null ? "Not available" : areaFormat.format(Number(value));
}

function AreaBars({
  title,
  groups,
}: {
  title: string;
  groups: QualityGroup[];
}) {
  const maximum = Math.max(...groups.map((g) => Number(g.rejected_area_m2)), 0);
  return (
    <section className="panel">
      <h3>{title}</h3>
      <p className="text-xs muted mt-1">Recorded rejected area (m²)</p>
      <ul className="quality-bars" aria-label={title}>
        {groups.map((g) => (
          <li key={g.label}>
            <div className="quality-bar-label">
              <span>{g.label}</span>
              <strong>{areaDisplay(g.rejected_area_m2)} m²</strong>
            </div>
            <div
              className="quality-bar-track"
              role="img"
              aria-label={`${g.label}: ${g.rejected_area_m2} m²; ${g.detail_count} detail records`}
            >
              <div
                style={{
                  width: `${maximum ? (100 * Number(g.rejected_area_m2)) / maximum : 0}%`,
                }}
              />
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

type TrendPoint = {
  time: number;
  date: string;
  amount: number | null;
  exact: string | null;
};
function QualityTrend({ value }: { value: QualitySummary }) {
  const window = calendarWindow(value.scope.start, value.scope.end);
  if (!window) return null;
  const start = Date.parse(value.scope.start + "T12:00:00Z");
  const points: TrendPoint[] = Array.from(
    { length: window.days },
    (_, index) => {
      const time = start + index * 86400000,
        date = new Date(time).toISOString().slice(0, 10);
      const record = value.daily.find((g) => g.label === date);
      return {
        time,
        date,
        amount: record ? Number(record.rejected_area_m2) : null,
        exact: record?.rejected_area_m2 ?? null,
      };
    },
  );
  function label(props: LabelProps) {
    const box = props.viewBox;
    if (
      props.index === undefined ||
      !box ||
      !("x" in box) ||
      !("y" in box) ||
      typeof box.x !== "number" ||
      typeof box.y !== "number"
    )
      return <g />;
    const point = points[props.index];
    if (!point || point.exact === null) return <g />;
    return (
      <text
        x={box.x}
        y={box.y - 13}
        textAnchor="middle"
        className="quality-point-label"
      >
        {areaDisplay(point.exact)}
      </text>
    );
  }
  function tooltip({
    active,
    payload,
  }: {
    active?: boolean;
    payload?: readonly { payload?: TrendPoint }[];
  }) {
    const point = payload?.[0]?.payload;
    return active && point && point.exact !== null ? (
      <div className="input-trend-tooltip">
        <strong>{point.date}</strong>
        <p>Recorded rejected area: {areaDisplay(point.exact)} m²</p>
      </div>
    ) : null;
  }
  return (
    <section className="panel">
      <h3>Recorded rejected-area trend</h3>
      <p className="text-xs muted mt-1">
        {value.recorded_dates.length} / {window.days} dates have quality records
        · m²
      </p>
      <div
        className="quality-trend-scroll"
        tabIndex={0}
        role="region"
        aria-label="Rejected-area trend, scroll horizontally for all dates"
      >
        <div
          style={{
            minWidth: Math.max(720, window.days * 100 + 140),
            height: 300,
          }}
        >
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              data={points}
              margin={{ top: 40, right: 65, bottom: 15, left: 28 }}
            >
              <CartesianGrid vertical={false} stroke="var(--border)" />
              <XAxis
                dataKey="time"
                type="number"
                scale="time"
                domain={window.domain}
                ticks={dateTicks(
                  window,
                  Math.max(720, window.days * 100 + 140),
                )}
                tickFormatter={shortDate}
                tick={{ fontSize: 12 }}
              />
              <YAxis
                domain={[0, (max: number) => Math.max(1, max * 1.2)]}
                width={78}
                tick={{ fontSize: 12 }}
              />
              <Tooltip content={tooltip} />
              <Line
                dataKey="amount"
                name="Recorded rejected area (m²)"
                stroke="var(--primary)"
                strokeWidth={2.5}
                dot={{ r: 4 }}
                connectNulls
                isAnimationActive={false}
              >
                <LabelList dataKey="amount" content={label} />
              </Line>
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
      <p className="text-xs muted">
        Production date · MM-DD. Recorded dates are connected across gaps;
        missing dates have no points.
      </p>
      <details className="input-trend-details">
        <summary>View recorded daily values</summary>
        <div className="mt-3">
          <DataTable
            rows={value.daily.map((g) => ({
              production_date: g.label,
              rejected_area_m2: g.rejected_area_m2,
              detail_records: g.detail_count,
            }))}
          />
        </div>
      </details>
    </section>
  );
}

export function QualityView({ value }: { value: QualitySummary }) {
  if (!value.detail_count)
    return (
      <div className="note">
        {value.status === "not_imported"
          ? "Quality records have not been imported."
          : "No quality records under these filters. This does not establish zero rejected area."}
      </div>
    );
  const kpis = [
    ["Recorded rejected area", `${areaDisplay(value.rejected_area_m2)} m²`],
    ["Detail records", String(value.detail_count)],
    ["Recorded machines", String(value.machine_count)],
  ];
  return (
    <>
      <div className="grid gap-4 sm:grid-cols-3">
        {kpis.map(([title, number]) => (
          <section className="panel" key={title}>
            <p className="text-xs muted">{title}</p>
            <p className="mt-2 text-2xl font-semibold break-words">{number}</p>
          </section>
        ))}
      </div>
      <p className="text-xs muted">
        {value.scope.start} – {value.scope.end} ·{" "}
        {value.scope.shift === "All"
          ? "All shifts"
          : `${value.scope.shift} shift`}{" "}
        · {value.scope.machine || "All machines"} ·{" "}
        {value.scope.product || "All products"}.{" "}
        {value.recorded_shifts.join(" / ")} recorded;{" "}
        {value.recorded_dates.length} dates with entries. Coverage may be
        incomplete.
      </p>
      <div className="grid gap-6 xl:grid-cols-2">
        <AreaBars title="Rejected area by machine" groups={value.by_machine} />
        <AreaBars
          title="Rejected area by recorded defect"
          groups={value.by_reason}
        />
      </div>
      <QualityTrend value={value} />
      <details className="note">
        <summary>Quality definitions and coverage</summary>
        <div className="mt-3 space-y-2">
          <p>
            Amounts are recorded nonconforming-film area in m². Detail records
            are not a roll count. Original quantities are retained, including
            values that differ from nominal roll area.
          </p>
          <p>
            Each record contributes its area once. Identical CCD and appearance
            labels are counted once; different labels form a combined category.
            Original labels, including suffixes, are retained.
          </p>
          <p>
            These records do not establish complete rejection coverage, a
            rejection rate, or the cause of a defect. Coating identifiers
            support tracing only. Existing area qualification and runtime
            estimates use their original inputs.
          </p>
          <p>
            {value.matched_production_group_count} date/shift/machine/product
            groups match production; {value.unmatched_production_group_count}{" "}
            have no matching production record. Quality entries are retained
            without inventing production quantities.
          </p>
          <p>
            Dates without quality entries:{" "}
            {value.missing_dates.join(", ") || "None in this selection"}.
            Missing entries do not mean zero defects.
          </p>
        </div>
      </details>
    </>
  );
}

export default function QualityAnalysis() {
  const { scope, refreshVersion, refresh } = useWorkspace();
  const [result, setResult] = useState<{
    key: string;
    value: QualitySummary;
  }>();
  const [error, setError] = useState<{ key: string; message: string }>();
  const [expanded, setExpanded] = useState(false);
  const [page, setPage] = useState({ key: "", offset: 0 });
  const [details, setDetails] = useState<{
    key: string;
    offset: number;
    value: QualityRecords;
  }>();
  const [detailError, setDetailError] = useState<{
    key: string;
    offset: number;
    message: string;
  }>();
  const scopeQuery = query(scope),
    key = scopeQuery + "&refresh=" + refreshVersion;
  const offset = page.key === key ? page.offset : 0;
  const value = result?.key === key ? result.value : undefined;
  const detail =
    details?.key === key && details.offset === offset
      ? details.value
      : undefined;
  useEffect(() => {
    if (!scope.start || !scope.end) return;
    let active = true;
    api<QualitySummary>("/production/quality?" + scopeQuery)
      .then((value) => {
        if (active) {
          setError(undefined);
          setResult({ key, value });
        }
      })
      .catch((e) => {
        if (active) setError({ key, message: String(e.message) });
      });
    return () => {
      active = false;
    };
  }, [scopeQuery, key, scope.start, scope.end]);
  useEffect(() => {
    if (!expanded || !value?.detail_count) return;
    let active = true;
    api<QualityRecords>(
      "/production/quality/records?" +
        scopeQuery +
        `&offset=${offset}&limit=100`,
    )
      .then((value) => {
        if (active) {
          setDetailError(undefined);
          setDetails({ key, offset, value });
        }
      })
      .catch((e) => {
        if (active) setDetailError({ key, offset, message: String(e.message) });
      });
    return () => {
      active = false;
    };
  }, [expanded, key, offset, scopeQuery, value?.detail_count]);
  return (
    <section
      className="space-y-5 quality-analysis"
      aria-labelledby="quality-title"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="quality-title">Quality analysis</h2>
        <Button variant="outline" size="sm" onClick={refresh}>
          Refresh
        </Button>
      </div>
      {error?.key === key ? (
        <p className="note" role="alert">
          Quality records could not be loaded. {error.message}
        </p>
      ) : !value ? (
        <p className="note" role="status">
          Loading quality records…
        </p>
      ) : (
        <QualityView value={value} />
      )}
      {value && value.detail_count > 0 && (
        <details
          className="panel machine-records-details"
          onToggle={(event) => setExpanded(event.currentTarget.open)}
        >
          <summary>View quality details · {value.detail_count} records</summary>
          <div className="mt-4 space-y-3">
            {detailError?.key === key && detailError.offset === offset ? (
              <p role="alert">
                Quality details could not be loaded. {detailError.message}
              </p>
            ) : !detail ? (
              <p role="status">Loading details…</p>
            ) : (
              <>
                <div className="flex flex-wrap items-center gap-3 text-xs">
                  <span>
                    {detail.total ? offset + 1 : 0}–
                    {Math.min(offset + detail.records.length, detail.total)} of{" "}
                    {detail.total} · area in m²
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={offset === 0}
                    onClick={() =>
                      setPage({ key, offset: Math.max(0, offset - 100) })
                    }
                  >
                    Previous
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={offset + 100 >= detail.total}
                    onClick={() => setPage({ key, offset: offset + 100 })}
                  >
                    Next
                  </Button>
                </div>
                <DataTable rows={detail.records} />
              </>
            )}
          </div>
        </details>
      )}
    </section>
  );
}
