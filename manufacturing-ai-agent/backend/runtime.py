"""Assumption-based machine-time ranges; never measured runtime or net downtime.

Source labels and event-minute sums are untouched. Clock windows are naive local
wall-clock assumptions: Day 08-20, Night 20-next 08; no timezone/DST claim.
"""

from contextlib import closing
from datetime import date, datetime, time, timedelta
import math
from pathlib import Path
import re
import sqlite3


SHIFT_MINUTES = 720
BREAK_MINUTES = 120
AVAILABLE_MINUTES = SHIFT_MINUTES - BREAK_MINUTES
BASIS = "12h-shift-2h-flexible-break-all-events-stop-v1"
ASSUMPTIONS = [
    "Estimate only: each record-evidenced machine shift assumes 12 hours, including 2 hours of flexible breaks.",
    "All recorded abnormality intervals are treated as complete stops; overlapping intervals are merged per machine.",
    "Break times are unknown, so runtime and utilization are ranges; unrecorded stops cannot be deducted.",
    "Clock windows: Day 08:00-20:00; Night 20:00-next 08:00. Source event dates and shift labels remain unchanged.",
    "Machine time is not allocated to products. No record does not establish a schedule, operation or zero downtime.",
    "Full assumed shifts are used, including the selected end date; this is not elapsed runtime as of now.",
]


def _day(value):
    return date.fromisoformat(value) if isinstance(value, str) else value


def _clock(value):
    if value is None:
        return None
    if not isinstance(value, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?", value
    ):
        raise ValueError("Expected explicit source-local date and clock time")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is not None:
        raise ValueError("Expected source-local timestamps without timezone offsets")
    return parsed


def _minutes(spans):
    merged = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return sum((end - start).total_seconds() / 60 for start, end in merged)


def _totals(rows):
    observed = sum(r["observed_shift_count"] for r in rows)
    possible = sum(r["possible_shift_count"] for r in rows)
    invalid = sum(r["invalid_event_count"] for r in rows)
    available = observed * AVAILABLE_MINUTES if observed else None
    usable = bool(observed) and not invalid
    lower = sum(r["runtime_lower_minutes"] or 0 for r in rows) if usable else None
    upper = sum(r["runtime_upper_minutes"] or 0 for r in rows) if usable else None
    return dict(
        status="estimated" if usable else "unavailable",
        observed_shift_count=observed,
        possible_shift_count=possible,
        unrecorded_shift_count=possible - observed,
        invalid_event_count=invalid,
        no_recorded_stop_shift_count=sum(
            r["no_recorded_stop_shift_count"] for r in rows
        ),
        available_minutes=available,
        merged_stop_minutes=sum(r["merged_stop_minutes"] or 0 for r in rows)
        if usable
        else None,
        runtime_lower_minutes=lower,
        runtime_upper_minutes=upper,
        utilization_lower=lower / available if usable else None,
        utilization_upper=upper / available if usable else None,
        reason=(
            "Incomplete or contradictory event times prevent a reliable range."
            if invalid
            else "No record-evidenced machine shifts in this scope."
            if not observed
            else None
        ),
    )


def estimate_runtime(
    production_rows,
    events,
    start,
    end,
    *,
    shift="All",
    machines=None,
    source="reviewed",
):
    """Pure calculation. Inputs may include events starting outside the date range."""
    start, end = _day(start), _day(end)
    if not 0 <= (end - start).days < 30 or shift not in ("All", "Day", "Night"):
        raise ValueError("Invalid runtime estimate scope")
    if source not in ("reviewed", "demo"):
        raise ValueError("Invalid runtime estimate source")
    ids = sorted(
        set(
            machines
            if machines is not None
            else [r["machine_id"] for r in production_rows]
            + [e["machine_id"] for e in events]
        )
    )
    keys = {
        (r["machine_id"], r["production_date"], r["shift"]) for r in production_rows
    }
    windows = []
    day = start
    while day <= end:
        for name, hour in (("Day", 8), ("Night", 20)):
            if shift in ("All", name):
                left = datetime.combine(day, time(hour))
                windows.append(
                    (day.isoformat(), name, left, left + timedelta(hours=12))
                )
        day += timedelta(days=1)
    earliest, latest = windows[0][2], windows[-1][3]
    intervals = {machine: [] for machine in ids}
    invalid = {machine: [] for machine in ids}
    for event in events:
        machine = event["machine_id"]
        if machine not in intervals:
            continue
        try:
            left, right = _clock(event.get("started_at")), _clock(event.get("ended_at"))
            if left is None or right is None or right < left:
                raise ValueError("Incomplete or reversed timestamps")
            reported = event.get("reported_minutes")
            if reported is not None and (
                not math.isfinite(reported)
                or abs((right - left).total_seconds() / 60 - reported) > 0.01
            ):
                raise ValueError("Timestamp and reported-minute disagreement")
        except (ValueError, TypeError, OverflowError):
            # Fail closed for an affected machine, rather than assume unknown time is zero.
            try:
                event_day = _day(event["production_date"])
                relevant = (
                    start - timedelta(days=1) <= event_day <= end + timedelta(days=1)
                )
            except (ValueError, TypeError, KeyError):
                relevant = True
            try:
                a, b = _clock(event.get("started_at")), _clock(event.get("ended_at"))
                relevant |= (a is not None and b is None and a < latest) or (
                    b is not None and a is None and b > earliest
                )
            except (ValueError, TypeError, OverflowError):
                pass
            if relevant:
                invalid[machine].append(event)
            continue
        intervals[machine].append((left, right))

    per_machine = []
    for machine in ids:
        totals = []
        for day, name, left, right in windows:
            spans = [
                (max(left, a), min(right, b))
                for a, b in intervals[machine]
                if max(left, a) < min(right, b)
            ]
            zero = any(a == b and left <= a < right for a, b in intervals[machine])
            incomplete_label = any(
                e.get("production_date") == day and e.get("shift") in (None, name)
                for e in invalid[machine]
            )
            if (
                (machine, day, name) not in keys
                and not spans
                and not zero
                and not incomplete_label
            ):
                continue
            stopped = _minutes(spans)
            assert 0 <= stopped <= SHIFT_MINUTES
            # Flexible breaks can overlap stops by between max(0,S-600) and min(S,120).
            totals.append(
                dict(
                    observed_shift_count=1,
                    possible_shift_count=1,
                    invalid_event_count=0,
                    no_recorded_stop_shift_count=int(stopped == 0),
                    merged_stop_minutes=stopped,
                    runtime_lower_minutes=max(0, AVAILABLE_MINUTES - stopped),
                    runtime_upper_minutes=min(
                        AVAILABLE_MINUTES, SHIFT_MINUTES - stopped
                    ),
                )
            )
        summary = _totals(totals)
        summary.update(
            possible_shift_count=len(windows),
            unrecorded_shift_count=len(windows) - len(totals),
            invalid_event_count=len(invalid[machine]),
        )
        if invalid[machine]:
            for key in (
                "merged_stop_minutes",
                "runtime_lower_minutes",
                "runtime_upper_minutes",
                "utilization_lower",
                "utilization_upper",
            ):
                summary[key] = None
            summary.update(
                status="unavailable",
                reason="Incomplete or contradictory event times prevent a reliable range.",
            )
        per_machine.append(dict(machine_id=machine, **summary))
    return dict(
        **_totals(per_machine),
        source=source,
        basis=BASIS,
        shift_minutes=SHIFT_MINUTES,
        break_minutes=BREAK_MINUTES,
        available_minutes_per_shift=AVAILABLE_MINUTES,
        assumptions=list(ASSUMPTIONS),
        per_machine=per_machine,
    )


def read_runtime_estimate(path, start, end, *, shift="All", machine=None):
    """Parameterized SQLite read-only snapshot, with carry-in/carry-out intervals."""
    start_day, end_day = _day(start), _day(end)
    lower = datetime.combine(start_day, time(20 if shift == "Night" else 8))
    upper = datetime.combine(end_day, time(20 if shift == "Day" else 8))
    if shift != "Day":
        upper += timedelta(days=1)
    with closing(
        sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)
    ) as db:
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        db.row_factory = sqlite3.Row
        tables = {
            r[0]
            for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        known, rows, events = set(), [], []
        for table in ("slitting_records", "abnormality_events"):
            if table in tables:
                known.update(
                    r[0] for r in db.execute("SELECT DISTINCT machine_id FROM " + table)
                )
        clause = " AND machine_id=?" if machine else ""
        suffix = [machine] if machine else []
        if "slitting_records" in tables:
            rows = [
                dict(r)
                for r in db.execute(
                    "SELECT production_date,shift,machine_id FROM slitting_records WHERE production_date BETWEEN ? AND ?"
                    + clause,
                    [start_day.isoformat(), end_day.isoformat(), *suffix],
                )
            ]
        if "abnormality_events" in tables:
            events = [
                dict(r)
                for r in db.execute(
                    "SELECT production_date,shift,machine_id,started_at,ended_at,reported_minutes FROM abnormality_events WHERE ("
                    "(started_at < ? AND ended_at >= ?) OR production_date BETWEEN ? AND ? OR "
                    "(started_at < ? AND ended_at IS NULL) OR (ended_at > ? AND started_at IS NULL))"
                    + clause,
                    [
                        upper.isoformat(timespec="minutes"),
                        lower.isoformat(timespec="minutes"),
                        (start_day - timedelta(days=1)).isoformat(),
                        (end_day + timedelta(days=1)).isoformat(),
                        upper.isoformat(timespec="minutes"),
                        lower.isoformat(timespec="minutes"),
                        *suffix,
                    ],
                )
            ]
    return estimate_runtime(
        rows,
        events,
        start_day,
        end_day,
        shift=shift,
        machines=[machine] if machine else known,
    )
