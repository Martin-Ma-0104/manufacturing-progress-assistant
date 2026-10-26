"""Adapters for existing reviewed SQLite and completely separate synthetic examples."""

from datetime import date, timedelta
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import abnormality
from ai_production_data import catalog, normalize_scope, read_snapshot
from production_dashboard import summarize, coverage_text
from .models import Scope
from .calculations import analyze_downtime


def db_path():
    return (
        Path(os.getenv("PRODUCTION_DB", str(ROOT / "manufacturing.db")))
        .expanduser()
        .resolve()
    )


def demo_rows():
    rows = []
    for d in range(7):
        for n in range(1, 8):
            if n == 3 and d == 4:
                continue
            inputs = 6 + (n + d) % 9
            actual = inputs * 1900.0
            rows.append(
                dict(
                    production_date=(
                        date(2026, 10, 12) + timedelta(days=d)
                    ).isoformat(),
                    shift="Day",
                    machine_id=f"FX{n}",
                    product="SYNTHETIC separator 88.8 mm",
                    planned_rolls=14,
                    input_rolls=inputs,
                    qualified_rolls=inputs * 9,
                    actual_output_m2=actual,
                    qualified_output_m2=actual * 0.86,
                    reported_yield_pct=None,
                )
            )
    return rows


def options(source="reviewed"):
    if source == "demo":
        rows = demo_rows()
        return dict(
            dates=sorted({r["production_date"] for r in rows}),
            machines=[f"FX{n}" for n in range(1, 8)],
            products=sorted({r["product"] for r in rows}),
        )
    if not db_path().is_file():
        return dict(dates=[], machines=[f"FX{n}" for n in range(1, 8)], products=[])
    c = catalog(db_path())
    # Keep real FX8, while requested FX1-FX7 without records remain explicitly unconnected.
    ids = sorted(set(c["machines"]) | {f"FX{n}" for n in range(1, 8)})
    products = []
    if c["dates"]:
        import sqlite3

        with sqlite3.connect(db_path().as_uri() + "?mode=ro", uri=True) as db:
            if db.execute(
                "SELECT 1 FROM sqlite_master WHERE name='slitting_records'"
            ).fetchone():
                products = [
                    r[0]
                    for r in db.execute(
                        "SELECT DISTINCT product FROM slitting_records ORDER BY product"
                    )
                ]
    return dict(dates=c["dates"], machines=ids, products=products)


def snapshot(scope: Scope):
    opts = options(scope.source)
    end = scope.end or (
        date.fromisoformat(opts["dates"][-1]) if opts["dates"] else date.today()
    )
    start = scope.start or end - timedelta(days=6)
    normalized = normalize_scope(
        start.isoformat(),
        end.isoformat(),
        None if scope.shift == "All" else scope.shift,
        [],
    )
    warnings = [
        "Historical observations; no live machine connection. Status, cycle time and measured utilization are unavailable.",
        "Plan attainment compares input mother rolls, not planned finished output.",
        abnormality.CAUTION,
    ]
    if scope.source == "demo":
        rows = [
            r
            for r in demo_rows()
            if start.isoformat() <= r["production_date"] <= end.isoformat()
            and (scope.shift == "All" or r["shift"] == scope.shift)
        ]
        events = []
        for n in range(1, 8):
            events.append(
                dict(
                    event_id=f"SYNTHETIC-{n}",
                    production_date=end.isoformat(),
                    shift="Day",
                    machine_id=f"FX{n}",
                    category=["Blade change", "Quality check", "Material wait"][n % 3],
                    subcategory="",
                    started_at=None,
                    ended_at=None,
                    reported_minutes=20 + n * 12,
                    status="Closed",
                )
            )
        events = [e for e in events if scope.shift in ("All", "Day")]
        changes = []
        warnings.insert(
            0,
            "SYNTHETIC DEMONSTRATION — not company production. No real data is mixed in.",
        )
    elif db_path().is_file():
        snap = read_snapshot(normalized, db_path())
        rows = snap["rows"]
        events = snap["abnormalities"]
        changes = snap["changeovers"]

    else:
        rows = []
        events = []
        changes = []
        warnings.append(
            "Reviewed database not found; initialize using the existing workflow. No database has been created by this API."
        )
    if scope.machine:
        if scope.machine not in opts["machines"]:
            raise ValueError("Unknown machine.")
        rows = [r for r in rows if r["machine_id"] == scope.machine]
        events = [e for e in events if e["machine_id"] == scope.machine]
        changes = [e for e in changes if e["machine_id"] == scope.machine]
    if scope.product:
        if scope.product not in opts["products"]:
            raise ValueError("Unknown product.")
        rows = [r for r in rows if r["product"] == scope.product]
        warnings.append(
            "Abnormalities have no product attribution: event figures use date/machine/shift filters, not product attribution."
        )
    warnings += [
        coverage_text(rows, None if scope.shift == "All" else scope.shift),
        abnormality.coverage(events),
    ]
    return (
        rows,
        events,
        changes,
        dict(
            start=start.isoformat(),
            end=end.isoformat(),
            machine=scope.machine,
            shift=scope.shift,
            product=scope.product,
            source=scope.source,
        ),
        warnings,
        opts,
    )


def dashboard(scope: Scope):
    rows, events, changes, s, warnings, opts = snapshot(scope)
    total = summarize(rows)
    if not rows:
        for field in (
            "planned_rolls",
            "input_rolls",
            "qualified_rolls",
            "actual_output_m2",
            "qualified_output_m2",
        ):
            total[field] = None
    total.update(
        average_cycle_minutes=None, machine_utilization=None, estimated_capacity=None
    )
    machine_rows = []
    ids = [scope.machine] if scope.machine else opts["machines"]
    for machine in ids:
        subset = [r for r in rows if r["machine_id"] == machine]
        ms = summarize(subset)
        if not subset:
            for f in (
                "planned_rolls",
                "input_rolls",
                "qualified_rolls",
                "actual_output_m2",
                "qualified_output_m2",
            ):
                ms[f] = None
        machine_rows.append(
            dict(
                machine_id=machine,
                status="Historical records" if subset else "Not connected / no records",
                cycle_minutes=None,
                utilization=None,
                **ms,
                abnormalities=abnormality.summarize(
                    [e for e in events if e["machine_id"] == machine]
                ),
            )
        )
    return dict(
        source=scope.source,
        scope=s,
        summary=total,
        daily=[
            dict(
                production_date=d,
                **summarize([r for r in rows if r["production_date"] == d]),
            )
            for d in sorted({r["production_date"] for r in rows})
        ],
        machines=machine_rows,
        abnormalities=analyze_downtime(events),
        records=rows,
        changeovers=changes,
        warnings=warnings,
        last_recorded_date=opts["dates"][-1] if opts["dates"] else None,
    )
