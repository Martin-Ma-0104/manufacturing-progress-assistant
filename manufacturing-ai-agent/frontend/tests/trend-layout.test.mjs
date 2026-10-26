import test from "node:test";
import assert from "node:assert/strict";
import {
  DAY,
  TREND,
  calendarWindow,
  changeoverLayout,
  dateTicks,
  dayTime,
  inputPoints,
  recordCoverage,
  minimumCanvasWidth,
  pixelX,
  plotBounds,
  pointLabel,
  shortDate,
  textBox,
  yScale,
} from "../lib/trend-layout.ts";
const p = (date, actual = 10, plan = 16) => ({
  production_date: date,
  input_rolls: actual,
  planned_rolls: plan,
  time: dayTime(date),
});

test("calendar dates remain evenly spaced across daylight-saving changes", () => {
  const window = calendarWindow("2026-10-26", "2026-11-24");
  assert.equal(window.days, 30);
  assert.equal(dayTime("2026-11-02") - dayTime("2026-11-01"), DAY);
  assert.equal(calendarWindow("2026-02-30", "2026-03-01"), null);
  assert.equal(calendarWindow("2026-10-25", "2026-10-12"), null);
  assert.equal(calendarWindow("2026-09-26", "2026-10-26"), null);
});
test("seven dates are explicit, horizontal-ready ticks within exact selected bounds", () => {
  const window = calendarWindow("2026-10-12", "2026-10-18");
  const ticks = dateTicks(window, 760);
  assert.equal(ticks.length, 7);
  assert.equal(shortDate(ticks[0]), "10-12");
  assert.equal(ticks.at(-1), window.end);
  assert(ticks.every((t) => t >= window.start && t <= window.end));
});
test("long tick ranges retain both boundaries and sufficient date-label spacing", () => {
  const window = calendarWindow("2026-09-26", "2026-10-25");
  for (const width of [760, 1000, 1400]) {
    const ticks = dateTicks(window, width);
    assert.equal(ticks[0], window.start);
    assert.equal(ticks.at(-1), window.end);
    for (let i = 1; i < ticks.length; i++)
      assert(
        pixelX(ticks[i], window, width) - pixelX(ticks[i - 1], window, width) >=
          64,
      );
  }
});
test("missing dates do not create points or zeros; explicit zero remains", () => {
  const rows = [
    p("2026-10-14", 11),
    p("2026-10-15", 6),
    p("2026-10-17", 8),
    p("2026-10-18", 0, 0),
  ];
  const before = structuredClone(rows);
  const points = inputPoints(rows, calendarWindow("2026-10-12", "2026-10-18"));
  assert.equal(points.length, 4);
  assert(!points.some((p) => p.production_date === "2026-10-16"));
  assert.equal(points.at(-1).input_rolls, 0);
  assert.deepEqual(rows, before);
  assert.deepEqual(
    inputPoints([], calendarWindow("2026-10-12", "2026-10-18")),
    [],
  );
});
test("a single date has a non-zero domain and one centred tick", () => {
  const window = calendarWindow("2026-10-25", "2026-10-25");
  assert(window.domain[1] > window.domain[0]);
  assert.deepEqual(dateTicks(window, 760), [window.start]);
  const bounds = plotBounds(760);
  assert.equal(
    pixelX(window.start, window, 760),
    (bounds.left + bounds.right) / 2,
  );
});
test("value positions follow their own series for below, equal and above plan", () => {
  assert.deepEqual(pointLabel(p("2026-10-16", 19, 16), "actual"), {
    text: "Actual 19",
    dy: -16,
  });
  assert.deepEqual(pointLabel(p("2026-10-16", 19, 16), "plan"), {
    text: "Plan 16",
    dy: 22,
  });
  assert.equal(pointLabel(p("2026-10-16", 16, 16), "actual").dy, 22);
  assert.equal(pointLabel(p("2026-10-16", 16, 16), "plan").dy, -16);
  assert.equal(pointLabel(p("2026-10-16", 5, 16), "actual").dy, 22);
  assert.equal(pointLabel(p("2026-10-16", 5, 16), "plan").dy, -16);
  assert.equal(pointLabel(p("2026-10-16", 0, 0), "actual").text, "Actual 0");
  assert.equal(pointLabel(p("2026-10-16", null, 16), "actual"), null);
});
test("Y headroom and integer ticks hold for small, zero and large counts", () => {
  for (const value of [0, 1, 16, 19, 32, 144, 1000]) {
    const { top, ticks } = yScale([p("2026-10-16", value, value)]);
    assert(top >= Math.max(5, value * 1.2));
    assert.equal(ticks[0], 0);
    assert.equal(ticks.at(-1), top);
    assert(ticks.every(Number.isInteger));
    // Top labels remain below chart top; zero labels stay before date tick area.
    const plotHeight = TREND.height - 20 - 8 - 58;
    const y = 20 + plotHeight * (1 - value / top);
    assert(y - 16 >= 4);
    assert(20 + plotHeight + 22 < TREND.height - 8);
  }
});
test("edge anchors keep labels inside the plotted calendar range", () => {
  const bounds = plotBounds(760);
  const first = textBox(bounds.left, "Actual 144", 760),
    last = textBox(bounds.right, "Plan 144", 760);
  assert.equal(first.anchor, "middle");
  assert.equal(last.anchor, "middle");
  assert(first.left >= TREND.left + TREND.yAxis + 6);
  assert(last.right <= 760 - TREND.right - 6);
});
test("all 30 dates keep both labels with enough space, including zero and large counts", () => {
  const window = calendarWindow("2026-09-26", "2026-10-25");
  for (const count of [16, 144, 1000, 1000000]) {
    const points = Array.from({ length: 30 }, (_, i) =>
      p(
        new Date(window.start + i * DAY).toISOString().slice(0, 10),
        i % 6 ? count : 0,
        count,
      ),
    );
    const width = minimumCanvasWidth(points, window);
    assert(width >= TREND.minWidth);
    assert.equal(
      points
        .flatMap((point) => [
          pointLabel(point, "actual", true),
          pointLabel(point, "plan", true),
        ])
        .filter(Boolean).length,
      60,
    );
    for (const series of ["actual", "plan"]) {
      const boxes = points.map((point) =>
        textBox(
          pixelX(point.time, window, width),
          pointLabel(point, series, true).text,
          width,
        ),
      );
      for (let i = 1; i < boxes.length; i++)
        assert(boxes[i].left - boxes[i - 1].right >= 19, count + " " + series);
    }
    assert.equal(pointLabel(points[0], "actual", true).text, "0");
    assert.equal(recordCoverage(points, window).missingDates.length, 0);
  }
});
test("coverage describes only observations in the current scope without zero filling", () => {
  const window = calendarWindow("2026-10-12", "2026-10-18");
  const points = inputPoints(
    [
      p("2026-10-14", 0, 16),
      p("2026-10-17", null, 16),
      p("2026-10-18", null, null),
    ],
    window,
  );
  const before = structuredClone(points);
  assert.deepEqual(recordCoverage(points, window), {
    first: "2026-10-14",
    last: "2026-10-17",
    missingDates: [
      "2026-10-12",
      "2026-10-13",
      "2026-10-15",
      "2026-10-16",
      "2026-10-18",
    ],
  });
  assert.equal(pointLabel(points[1], "actual", true), null);
  assert.equal(pointLabel(points[1], "plan", true).text, "16");
  assert.deepEqual(points, before);
  const empty = recordCoverage([], window);
  assert.equal(empty.first, null);
  assert.equal(empty.last, null);
  assert.equal(empty.missingDates.length, 7);
  assert.equal(minimumCanvasWidth([], window), TREND.minWidth);
  const single = calendarWindow("2026-10-14", "2026-10-14");
  assert.deepEqual(recordCoverage([points[0]], single).missingDates, []);
});
test("sparse month labels keep calendar distances and all non-null values", () => {
  const window = calendarWindow("2026-09-27", "2026-10-26");
  const points = [
    p("2026-10-12", 4, 12),
    p("2026-10-13", 15, 14),
    p("2026-10-16", 19, 16),
    p("2026-10-22", null, 16),
  ];
  const width = minimumCanvasWidth(points, window);
  const x = points.map((point) => pixelX(point.time, window, width));
  assert(Math.abs((x[2] - x[1]) / (x[1] - x[0]) - 3) < 1e-9);
  assert.equal(
    points
      .flatMap((point) => [
        pointLabel(point, "actual", true),
        pointLabel(point, "plan", true),
      ])
      .filter(Boolean).length,
    7,
  );
  assert.deepEqual(pointLabel(points[2], "actual", true), {
    text: "19",
    dy: -16,
  });
  assert.deepEqual(pointLabel(points[2], "plan", true), { text: "16", dy: 22 });
});
test("adjacent confirmed events use separate lanes; same-day events retain both descriptions", () => {
  const window = calendarWindow("2026-10-12", "2026-10-18");
  const events = [
    {
      production_date: "2026-10-12",
      shift: "Day",
      from_product: "A",
      to_product: "B",
    },
    {
      production_date: "2026-10-12",
      shift: "Night",
      from_product: "B",
      to_product: "C",
    },
    { production_date: "2026-10-13" },
    { production_date: "2026-10-14" },
  ];
  const { markers, bandHeight } = changeoverLayout(events, window, 760);
  assert.equal(markers.length, 3);
  assert.equal(markers[0].count, 2);
  assert(markers[0].title.includes("Day"));
  assert(markers[0].title.includes("Night"));
  assert(bandHeight > 0);
  for (const marker of markers.filter((m) => m.labelVisible)) {
    const bounds = plotBounds(760);
    assert(marker.left >= bounds.left && marker.right <= bounds.right);
  }
  for (let a = 0; a < markers.length; a++)
    for (let b = a + 1; b < markers.length; b++)
      if (markers[a].lane === markers[b].lane)
        assert(markers[b].left - markers[a].right >= 8);
  assert.equal(changeoverLayout([], window, 760).markers.length, 0);
});
test("dense event dates never lose reference-line markers or force overlapping text", () => {
  const window = calendarWindow("2026-09-26", "2026-10-25");
  const events = Array.from({ length: 30 }, (_, i) => ({
    production_date: new Date(window.start + i * DAY)
      .toISOString()
      .slice(0, 10),
  }));
  const { markers } = changeoverLayout(events, window, 760);
  assert.equal(markers.length, 30);
  for (let lane = 0; lane < 3; lane++) {
    const visible = markers.filter((m) => m.labelVisible && m.lane === lane);
    for (let i = 1; i < visible.length; i++)
      assert(visible[i].left - visible[i - 1].right >= 8);
  }
});

test("weekly labels fit even at the minimum viewport, including large counts and edge points", () => {
  const window = calendarWindow("2026-10-12", "2026-10-18");
  for (const count of [16, 144, 1000, 1000000]) {
    const points = Array.from({ length: 7 }, (_, i) =>
      p(
        new Date(window.start + i * DAY).toISOString().slice(0, 10),
        count,
        count,
      ),
    );
    const width = minimumCanvasWidth(points, window);
    for (const series of ["actual", "plan"]) {
      const boxes = points.map((point) =>
        textBox(
          pixelX(point.time, window, width),
          pointLabel(point, series).text,
          width,
        ),
      );
      for (let i = 1; i < boxes.length; i++)
        assert(boxes[i].left - boxes[i - 1].right >= 19, count + " " + series);
    }
  }
});
