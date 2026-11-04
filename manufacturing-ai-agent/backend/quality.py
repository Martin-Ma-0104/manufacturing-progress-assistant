"""Read-only quality views, independent of production/downtime denominators."""

from contextlib import closing
from datetime import date, timedelta
import sqlite3
import slitting_quality as quality
from . import data
from .models import Scope


def effective_scope(scope):
    opts = data.options(scope.source)
    end = scope.end or (
        date.fromisoformat(opts["dates"][-1]) if opts["dates"] else date.today()
    )
    start = scope.start or end - timedelta(days=6)
    resolved = Scope(**{**scope.model_dump(), "start": start, "end": end})
    if scope.machine and scope.machine not in opts["machines"]:
        raise ValueError("Unknown machine.")
    if scope.product and scope.product not in opts["products"]:
        raise ValueError("Unknown product.")
    return resolved


def snapshot(scope):
    resolved = effective_scope(scope)
    path = data.db_path()
    rows, matched, table = [], set(), False
    if path.is_file():
        with closing(
            sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
        ) as connection:
            connection.execute("PRAGMA query_only=ON")
            connection.execute("BEGIN")
            table = quality.has_table(connection)
            rows = quality.read_records(
                connection,
                resolved.start.isoformat(),
                resolved.end.isoformat(),
                resolved.shift,
                resolved.machine,
                resolved.product,
            )
            if (
                rows
                and connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE name='slitting_records' AND type='table'"
                ).fetchone()
            ):
                matched = set(
                    connection.execute(
                        "SELECT production_date,shift,machine_id,product FROM slitting_records WHERE production_date>=? AND production_date<=?",
                        (resolved.start.isoformat(), resolved.end.isoformat()),
                    )
                )
    groups = {
        (r["production_date"], r["shift"], r["machine_id"], r["product"]) for r in rows
    }
    dates = sorted({r["production_date"] for r in rows})
    expected = [
        (resolved.start + timedelta(days=i)).isoformat()
        for i in range((resolved.end - resolved.start).days + 1)
    ]
    summary = dict(
        **quality.summarize(rows),
        source="reviewed",
        unit="m2",
        scope=resolved.model_dump(mode="json"),
        status="recorded" if rows else ("no_records" if table else "not_imported"),
        recorded_dates=dates,
        missing_dates=[d for d in expected if d not in dates],
        recorded_shifts=sorted({r["shift"] for r in rows}),
        matched_production_group_count=len(groups & matched),
        unmatched_production_group_count=len(groups - matched),
    )
    return summary, rows


def summary(scope):
    return snapshot(scope)[0]


def records(scope, offset=0, limit=100):
    if offset < 0 or not 1 <= limit <= 200:
        raise ValueError("Quality paging needs offset >= 0 and limit from 1 to 200.")
    result, rows = snapshot(scope)
    # Provenance/notes remain local; tracing fields are returned only on explicit detail requests.
    fields = (
        "production_date",
        "shift",
        "machine_id",
        "product",
        "product_id",
        "station",
        "specification",
        "rejected_area_m2",
        "ccd_defect",
        "appearance_defect",
        "remarks",
        "coating_barcode",
        "coating_machine",
    )
    return dict(
        scope=result["scope"],
        unit="m2",
        total=len(rows),
        offset=offset,
        limit=limit,
        records=[{k: row[k] for k in fields} for row in rows[offset : offset + limit]],
    )
