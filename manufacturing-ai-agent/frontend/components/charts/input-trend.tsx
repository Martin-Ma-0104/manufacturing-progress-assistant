"use client";
import { useState } from "react";
import {
  CartesianGrid,
  LabelList,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  type LabelProps,
} from "recharts";
import {
  calendarWindow,
  changeoverLayout,
  dateTicks,
  inputPoints,
  recordCoverage,
  minimumCanvasWidth,
  plotBounds,
  pointLabel,
  shortDate,
  textBox,
  TREND,
  wholeDate,
  yScale,
  type ChangeEvent,
  type DailyInput,
  type InputPoint,
} from "@/lib/trend-layout";

import DataTable from "../data-table";

const ACTUAL = "var(--input-trend-actual)",
  PLAN = "var(--input-trend-plan)",
  CHANGE = "var(--input-trend-change)";
type DotProps = { cx?: number; cy?: number; index?: number };
type TooltipProps = {
  active?: boolean;
  payload?: readonly { payload?: InputPoint }[];
};
export default function InputTrend({
  daily,
  events,
  start,
  end,
  machine,
  shift,
}: {
  daily: readonly DailyInput[];
  events: readonly ChangeEvent[];
  start: string;
  end: string;
  machine: string;
  shift: string;
}) {
  const [measuredWidth, setWidth] = useState<number>(TREND.minWidth);
  const window = calendarWindow(start, end);
  if (!window)
    return (
      <section className="panel note">
        Select an ordered range of up to 30 calendar dates.
      </section>
    );
  const points = inputPoints(daily, window),
    scale = yScale(points);
  const minWidth = minimumCanvasWidth(points, window);
  const width = Math.max(measuredWidth, minWidth);
  const coverage = recordCoverage(points, window);
  const changes = changeoverLayout(machine ? events : [], window, width);
  const changed = new Set(changes.markers.map((marker) => marker.date));
  const bounds = plotBounds(width);
  function dot(props: DotProps, series: "actual" | "plan") {
    const { cx, cy, index } = props;
    if (typeof cx !== "number" || typeof cy !== "number" || index === undefined)
      return <g />;
    const point = points[index];
    if (
      !point ||
      (series === "actual" ? point.input_rolls : point.planned_rolls) === null
    )
      return <g />;
    return (
      <g>
        <circle
          cx={cx}
          cy={cy}
          r={
            series === "actual"
              ? 4.5
              : point.input_rolls === point.planned_rolls
                ? 6
                : 4
          }
          fill={series === "actual" ? ACTUAL : "var(--card)"}
          stroke={series === "actual" ? "var(--card)" : PLAN}
          strokeWidth={series === "actual" ? 1.5 : 2}
        />
        {series === "actual" && changed.has(point.production_date) && (
          <circle
            cx={cx}
            cy={cy}
            r={8.5}
            fill="none"
            stroke={CHANGE}
            strokeWidth={2}
          >
            <title>Confirmed changeover · {point.production_date}</title>
          </circle>
        )}
      </g>
    );
  }
  function label(props: LabelProps, series: "actual" | "plan") {
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
    if (!point) return <g />;
    const value = pointLabel(point, series, window!.days > 7);
    if (!value) return <g />;
    const position = textBox(box.x, value.text, width);
    return (
      <text
        className="input-trend-value"
        x={position.x}
        y={box.y + value.dy}
        textAnchor={position.anchor}
        style={{ fill: series === "actual" ? ACTUAL : PLAN }}
      >
        <title>{`${point.production_date} · ${series === "actual" ? "Actual input" : "Planned input"}: ${series === "actual" ? point.input_rolls : point.planned_rolls} mother rolls`}</title>
        {value.text}
      </text>
    );
  }
  function tooltip({ active, payload }: TooltipProps) {
    const point = payload?.find((item) => item.payload)?.payload;
    if (!active || !point) return null;
    const event = changes.markers.find((m) => m.date === point.production_date);
    return (
      <div className="input-trend-tooltip">
        <strong>{wholeDate(point.time)}</strong>
        <p style={{ color: ACTUAL }}>
          Actual input: {point.input_rolls ?? "Not available"} mother rolls
        </p>
        <p style={{ color: PLAN }}>
          Planned input: {point.planned_rolls ?? "Not available"} mother rolls
        </p>
        {event && <p style={{ color: CHANGE }}>{event.title}</p>}
      </div>
    );
  }
  return (
    <section
      className="panel input-trend-panel"
      aria-label="Planned and actual input trend"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2>Planned vs. actual input{machine ? ` · ${machine}` : ""}</h2>
          <p className="text-xs muted mt-1">
            Mother rolls · {machine || "All selected machines"} ·{" "}
            {shift === "All" ? "All recorded shifts" : shift + " shift"} ·{" "}
            {points.length} / {window.days} dates recorded
          </p>
        </div>
      </div>
      <div className="input-trend-legend">
        <span>
          <svg width="38" height="12" aria-hidden="true">
            <line
              x1="0"
              y1="6"
              x2="38"
              y2="6"
              stroke={ACTUAL}
              strokeWidth="3"
            />
            <circle cx="19" cy="6" r="4" fill={ACTUAL} />
          </svg>
          Actual input
        </span>
        <span>
          <svg width="38" height="12" aria-hidden="true">
            <line
              x1="0"
              y1="6"
              x2="38"
              y2="6"
              stroke={PLAN}
              strokeWidth="2.5"
              strokeDasharray="6 4"
            />
            <circle
              cx="19"
              cy="6"
              r="4"
              fill="var(--card)"
              stroke={PLAN}
              strokeWidth="2"
            />
          </svg>
          Planned input (reference)
        </span>
        {machine && changes.markers.length > 0 && (
          <span>
            <i className="input-trend-change-swatch" />
            Confirmed changeover
          </span>
        )}
      </div>
      {!points.length ? (
        <div className="note my-6">
          No input records in this scope. Missing observations are not zero.
        </div>
      ) : (
        <div className="input-trend-scroll">
          <div className="input-trend-canvas" style={{ minWidth }}>
            {changes.markers.length > 0 && (
              <div
                className="input-trend-event-band"
                style={{ height: changes.bandHeight }}
                aria-label="Confirmed changeover dates"
              >
                {changes.markers
                  .filter((marker) => marker.labelVisible)
                  .map((marker) => (
                    <span
                      key={marker.date}
                      className="input-trend-event"
                      title={marker.title}
                      style={{
                        left: marker.left,
                        top: marker.lane * 22,
                        width: marker.right - marker.left,
                      }}
                    >
                      {marker.label}
                    </span>
                  ))}
              </div>
            )}
            <ResponsiveContainer
              width="100%"
              height={TREND.height}
              onResize={(value) => {
                if (value >= TREND.minWidth) setWidth(value);
              }}
            >
              <LineChart
                data={points}
                margin={{
                  top: 20,
                  right: TREND.right,
                  bottom: 8,
                  left: TREND.left,
                }}
                accessibilityLayer
              >
                <CartesianGrid vertical={false} stroke="var(--border)" />
                <XAxis
                  dataKey="time"
                  type="number"
                  scale="time"
                  domain={window.domain}
                  allowDataOverflow
                  padding={{ left: TREND.xPadding, right: TREND.xPadding }}
                  ticks={dateTicks(window, width)}
                  tickFormatter={shortDate}
                  interval={0}
                  height={58}
                  tickMargin={26}
                  tickLine={false}
                  tick={{ fontSize: 12 }}
                  axisLine={{ stroke: "var(--input)" }}
                />
                <YAxis
                  width={TREND.yAxis}
                  domain={[0, scale.top]}
                  ticks={scale.ticks}
                  allowDecimals={false}
                  tick={{ fontSize: 12 }}
                  tickMargin={10}
                  tickLine={false}
                  axisLine={false}
                />
                <Tooltip
                  content={tooltip}
                  cursor={{ stroke: "var(--input)", strokeDasharray: "3 4" }}
                />
                {changes.markers.map((marker) => (
                  <ReferenceLine
                    key={marker.date}
                    x={marker.time}
                    stroke={CHANGE}
                    strokeDasharray="4 5"
                    strokeWidth={1.4}
                    label={false}
                    shape={(props) => (
                      <line
                        x1={props.x1}
                        x2={props.x2}
                        y1={props.y1}
                        y2={props.y2}
                        stroke={CHANGE}
                        strokeDasharray="4 5"
                        strokeWidth={1.4}
                      >
                        <title>{marker.title}</title>
                      </line>
                    )}
                  />
                ))}
                <Line
                  name="Planned input"
                  dataKey="planned_rolls"
                  stroke={PLAN}
                  strokeWidth={2.5}
                  strokeDasharray="7 5"
                  connectNulls
                  isAnimationActive={false}
                  dot={(props) => dot(props, "plan")}
                  activeDot={{
                    r: 5,
                    fill: "var(--card)",
                    stroke: PLAN,
                    strokeWidth: 2,
                  }}
                >
                  <LabelList content={(props) => label(props, "plan")} />
                </Line>
                <Line
                  name="Actual input"
                  dataKey="input_rolls"
                  stroke={ACTUAL}
                  strokeWidth={3}
                  connectNulls
                  isAnimationActive={false}
                  dot={(props) => dot(props, "actual")}
                  activeDot={{
                    r: 6,
                    fill: ACTUAL,
                    stroke: "var(--card)",
                    strokeWidth: 2,
                  }}
                >
                  <LabelList content={(props) => label(props, "actual")} />
                </Line>
              </LineChart>
            </ResponsiveContainer>
            <div
              className="input-trend-axis-note"
              style={{ paddingLeft: bounds.left }}
            >
              Production date · MM-DD
            </div>
          </div>
        </div>
      )}
      <p className="text-xs muted mt-3">
        Recorded dates are connected across gaps; missing dates have no points.
        Hover over a recorded date for both values.
        {!machine
          ? " Select one machine for confirmed changeover markers."
          : ""}
        {window.days > 7
          ? " Every recorded value is labeled; blue numbers are actual input and slate numbers are planned input. Scroll horizontally when needed."
          : ""}
      </p>
      <p className="text-xs muted mt-2">
        {coverage.first
          ? `Current filter: first record ${coverage.first} · last record ${coverage.last}.`
          : "Current filter: no recorded input values."}
        {` ${coverage.missingDates.length} / ${window.days} dates have no input records; missing records are not zero production.`}
      </p>
      <details className="input-trend-details">
        <summary>View all recorded values ({points.length} dates)</summary>
        <p className="text-xs muted my-3">
          Input quantities in mother rolls · current date, machine, shift and
          product filters.
        </p>
        <DataTable
          rows={points.map((point) => ({
            production_date: point.production_date,
            actual_input_rolls: point.input_rolls,
            planned_input_rolls: point.planned_rolls,
          }))}
        />
      </details>
      {coverage.missingDates.length > 0 && (
        <details className="input-trend-details">
          <summary>
            Dates without input records ({coverage.missingDates.length})
          </summary>
          <p className="text-xs muted mt-3">
            {coverage.missingDates.join(", ")}
          </p>
        </details>
      )}
    </section>
  );
}
