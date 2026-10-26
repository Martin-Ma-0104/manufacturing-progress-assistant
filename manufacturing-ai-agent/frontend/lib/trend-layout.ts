/** Calendar and pixel layout only. Production values are never recalculated here. */
export const DAY = 86_400_000;
export const TREND = {
  minWidth: 800,
  height: 380,
  left: 16,
  right: 28,
  yAxis: 60,
  xPadding: 48,
  labelFont: 12,
} as const;
export type DailyInput = {
  production_date: string;
  input_rolls: number | null;
  planned_rolls: number | null;
};
export type InputPoint = DailyInput & { time: number };
export type Window = {
  start: number;
  end: number;
  days: number;
  domain: [number, number];
};
export type Box = {
  left: number;
  right: number;
  x: number;
  anchor: "start" | "middle" | "end";
};
export type ChangeEvent = {
  production_date?: string;
  machine_id?: string;
  shift?: string;
  from_product?: string;
  to_product?: string;
};

export function dayTime(value: string): number {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return NaN;
  const time = Date.parse(value + "T12:00:00Z");
  return Number.isFinite(time) &&
    new Date(time).toISOString().slice(0, 10) === value
    ? time
    : NaN;
}
export function calendarWindow(start: string, end: string): Window | null {
  const a = dayTime(start),
    b = dayTime(end);
  if (
    !Number.isFinite(a) ||
    !Number.isFinite(b) ||
    b < a ||
    (b - a) / DAY >= 30
  )
    return null;
  return {
    start: a,
    end: b,
    days: (b - a) / DAY + 1,
    domain: a === b ? [a - DAY / 2, b + DAY / 2] : [a, b],
  };
}
export const shortDate = (time: number) =>
  new Date(time).toISOString().slice(5, 10);
export const wholeDate = (time: number) =>
  new Date(time).toISOString().slice(0, 10);
export function inputPoints(
  rows: readonly DailyInput[],
  window: Window,
): InputPoint[] {
  return rows
    .map((row) => ({ ...row, time: dayTime(row.production_date) }))
    .filter(
      (row) =>
        row.time >= window.start &&
        row.time <= window.end &&
        (row.input_rolls !== null || row.planned_rolls !== null),
    )
    .sort((a, b) => a.time - b.time);
}
export function plotBounds(width: number) {
  return {
    left: TREND.left + TREND.yAxis + TREND.xPadding,
    right: width - TREND.right - TREND.xPadding,
  };
}
export function pixelX(time: number, window: Window, width: number): number {
  const bounds = plotBounds(width);
  return (
    bounds.left +
    ((time - window.domain[0]) / (window.domain[1] - window.domain[0])) *
      (bounds.right - bounds.left)
  );
}
export function dateTicks(window: Window, width: number): number[] {
  if (window.days === 1) return [window.start];
  const bounds = plotBounds(width);
  const step =
    window.days <= 7
      ? 1
      : Math.max(
          1,
          Math.ceil(
            (window.days - 1) /
              Math.max(1, Math.floor((bounds.right - bounds.left) / 84)),
          ),
        );
  const ticks: number[] = [];
  for (let time = window.start; time <= window.end; time += step * DAY)
    ticks.push(time);
  if (ticks.at(-1) !== window.end) {
    if (
      ticks.length > 1 &&
      pixelX(window.end, window, width) - pixelX(ticks.at(-1)!, window, width) <
        64
    )
      ticks.pop();
    ticks.push(window.end);
  }
  return ticks;
}
export function yScale(points: readonly InputPoint[]) {
  const maximum = Math.max(
    0,
    ...points.flatMap((p) => [p.input_rolls ?? 0, p.planned_rolls ?? 0]),
  );
  const target = Math.max(5, maximum * 1.2),
    rawStep = target / 5;
  const magnitude = 10 ** Math.floor(Math.log10(rawStep));
  const step = Math.max(
    1,
    [1, 2, 5, 10].map((n) => n * magnitude).find((n) => n >= rawStep)!,
  );
  const top = Math.ceil(target / step) * step;
  return {
    top,
    ticks: Array.from(
      { length: Math.round(top / step) + 1 },
      (_, i) => i * step,
    ),
  };
}
export function textBox(x: number, text: string, width: number): Box {
  const size = text.length * TREND.labelFont * 0.66;
  const safeLeft = TREND.left + TREND.yAxis + 6,
    safeRight = width - TREND.right - 6;
  const center = Math.min(
    Math.max(x, safeLeft + size / 2),
    safeRight - size / 2,
  );
  return {
    x: center,
    left: center - size / 2,
    right: center + size / 2,
    anchor: "middle",
  };
}
export function minimumCanvasWidth(
  points: readonly InputPoint[],
  window: Window,
): number {
  const sizes = points.map(
    (point) =>
      Math.max(
        pointLabel(point, "actual", window.days > 7)?.text.length ?? 0,
        pointLabel(point, "plan", window.days > 7)?.text.length ?? 0,
      ) *
      TREND.labelFont *
      0.66,
  );
  const gutters = TREND.left + TREND.yAxis + TREND.right + 2 * TREND.xPadding;
  let plotWidth = TREND.minWidth - gutters;
  // Reserve space for every value, using true time gaps rather than hiding labels.
  for (let index = 1; index < points.length; index++) {
    const gap = points[index].time - points[index - 1].time;
    if (gap <= 0) continue;
    const first = sizes[index - 1],
      last = sizes[index];
    const edgeShift =
      Math.max(0, first / 2 - (TREND.xPadding - 6)) +
      Math.max(0, last / 2 - (TREND.xPadding - 6));
    const needed = first / 2 + last / 2 + 20 + edgeShift;
    plotWidth = Math.max(
      plotWidth,
      (needed * (window.domain[1] - window.domain[0])) / gap,
    );
  }
  return Math.ceil(gutters + plotWidth);
}
export function recordCoverage(points: readonly InputPoint[], window: Window) {
  const dates = new Set(points.map((point) => point.production_date));
  const missingDates: string[] = [];
  for (let time = window.start; time <= window.end; time += DAY) {
    const date = wholeDate(time);
    if (!dates.has(date)) missingDates.push(date);
  }
  return {
    first: points[0]?.production_date ?? null,
    last: points.at(-1)?.production_date ?? null,
    missingDates,
  };
}
export function pointLabel(
  point: InputPoint,
  series: "actual" | "plan",
  compact = false,
) {
  const actual = point.input_rolls,
    plan = point.planned_rolls;
  const value = series === "actual" ? actual : plan;
  if (value === null) return null;
  const above =
    series === "actual"
      ? plan === null || (actual !== null && actual > plan)
      : actual === null || (plan !== null && plan >= actual);
  return {
    text: compact
      ? String(value)
      : `${series === "actual" ? "Actual" : "Plan"} ${value}`,
    dy: above ? -16 : 22,
  };
}
export function changeoverLayout(
  events: readonly ChangeEvent[],
  window: Window,
  width: number,
) {
  const groups = new Map<string, ChangeEvent[]>();
  for (const event of events) {
    if (!event.production_date) continue;
    const time = dayTime(event.production_date);
    if (time < window.start || time > window.end || !Number.isFinite(time))
      continue;
    groups.set(event.production_date, [
      ...(groups.get(event.production_date) ?? []),
      event,
    ]);
  }
  const lanes = [-Infinity, -Infinity, -Infinity];
  const bounds = plotBounds(width);
  const markers = [...groups]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, items]) => {
      const x = pixelX(dayTime(date), window, width);
      const title = `${date} · ${items.map((e) => `${e.machine_id ?? ""} ${e.shift ?? ""}: ${e.from_product ?? ""} → ${e.to_product ?? ""}`).join("; ")}`;
      let label =
        items.length > 1 ? `Changeover ×${items.length}` : "Changeover";
      let size = label.length * 7.2 + 8;
      let left = Math.min(
        Math.max(x - size / 2, bounds.left),
        bounds.right - size,
      );
      let lane = lanes.findIndex((right) => left >= right + 8);
      if (lane < 0) {
        label = "CO";
        size = 28;
        left = Math.min(
          Math.max(x - size / 2, bounds.left),
          bounds.right - size,
        );
        lane = lanes.findIndex((right) => left >= right + 8);
      }
      if (lane >= 0) lanes[lane] = left + size;
      return {
        date,
        time: dayTime(date),
        x,
        title,
        label,
        left,
        right: left + size,
        lane,
        labelVisible: lane >= 0,
        count: items.length,
      };
    });
  const used =
    Math.max(-1, ...markers.filter((m) => m.labelVisible).map((m) => m.lane)) +
    1;
  return {
    markers,
    bandHeight: markers.length ? Math.max(1, used) * 22 + 10 : 0,
  };
}
