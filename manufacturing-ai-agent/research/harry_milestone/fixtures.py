"""Entirely invented records. No business-data extraction or anonymization."""

import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import abnormality
from production import import_records

HERE = Path(__file__).resolve().parent


def canonical():
    production = []
    rows = [
        ("P1", "2026-01-05", "Day", "FX1", "SYN-A", 10, 8, 40, 100, 80),
        ("P2", "2026-01-05", "Night", "FX1", "SYN-B", 10, 12, 60, 140, 120),
        ("P3", "2026-01-06", "Day", "FX1", "SYN-A", 12, 9, 45, 120, 90),
        ("P4", "2026-01-05", "Day", "FX2", "SYN-A", 20, 15, 70, 200, 140),
        ("P5", "2026-01-07", "Day", "FX2", "SYN-A", 10, 10, 50, 120, 100),
        ("P6", "2026-01-06", "Night", "FX4", "SYN-C", 8, 0, 0, 0, 0),
        ("P7", "2026-01-07", "Day", "FX4", "SYN-C", 0, 2, 10, 30, 20),
        ("P8", "2026-01-07", "Day", "FX8", "SYN-D", 0, 0, 0, 0, 0),
    ]
    for (
        ident,
        day,
        shift,
        machine,
        product,
        plan,
        actual,
        qualified,
        area,
        good,
    ) in rows:
        production.append(
            dict(
                production_date=day,
                shift=shift,
                machine_id=machine,
                product=product,
                planned_rolls=plan,
                input_rolls=actual,
                qualified_rolls=qualified,
                actual_output_m2=area,
                qualified_output_m2=good,
                reported_yield_pct=None,
                source_report_date=day,
                source_shift_label=shift,
                source_name="SYNTHETIC fixture",
                notes=ident + ": invented, not company production",
            )
        )
    events = []
    event_rows = [
        (
            "E1",
            "2026-01-05",
            "Day",
            "FX1",
            "Equipment",
            "2026-01-05T08:00",
            "2026-01-05T09:00",
            60,
            "Closed",
        ),
        (
            "E2",
            "2026-01-05",
            "Day",
            "FX1",
            "QC",
            "2026-01-05T08:30",
            "2026-01-05T09:30",
            60,
            "Open",
        ),
        (
            "E3",
            "2026-01-06",
            "Night",
            "FX1",
            "Equipment",
            "2026-01-06T23:30",
            "2026-01-07T00:30",
            60,
            "Closed",
        ),
        (
            "E4",
            "2026-01-05",
            "Day",
            "FX2",
            "Equipment",
            "2026-01-05T10:00",
            "2026-01-05T12:00",
            120,
            "Closed",
        ),
        (
            "E5",
            "2026-01-06",
            "Day",
            "FX2",
            "Material",
            "2026-01-06T11:00",
            None,
            30,
            "Open",
        ),
        (
            "E6",
            "2026-01-07",
            "Day",
            "FX2",
            "QC",
            "2026-01-07T14:00",
            "2026-01-07T14:20",
            None,
            "Open",
        ),
        (
            "E7",
            "2026-01-06",
            "Night",
            "FX4",
            "QC",
            "2026-01-06T20:00",
            "2026-01-06T20:00",
            0,
            "Closed",
        ),
        ("E8", "2026-01-07", None, "FX5", "Other", None, None, None, "Unknown"),
        (
            "E9",
            "2026-01-07",
            "Day",
            "FX4",
            "Other",
            "2026-01-07T09:00",
            "2026-01-07T09:10",
            15,
            "Closed",
        ),
        (
            "E10",
            "2026-01-05",
            "Day",
            "FX4",
            "Other",
            "2026-01-05T07:00",
            "2026-01-05T07:00",
            0,
            "Closed",
        ),
    ]
    for ident, day, shift, machine, category, start, end, minutes, status in event_rows:
        events.append(
            dict(
                event_id=ident,
                production_date=day,
                shift=shift,
                machine_id=machine,
                category=category,
                subcategory="SYNTHETIC",
                started_at=start,
                ended_at=end,
                reported_minutes=minutes,
                status=status,
                source_name="SYNTHETIC fixture",
                notes="Invented event; status is not equipment state.",
            )
        )
    return dict(production=production, abnormalities=events)


def build(destination: Path, variant="A"):
    if variant not in ("A", "B"):
        raise ValueError("Choose sample A or B.")
    destination = Path(destination).resolve()
    if destination.exists():
        raise ValueError("Refuse to overwrite an existing database.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    value = canonical()
    if variant == "B":
        value["abnormalities"][3].update(
            reported_minutes=240, ended_at="2026-01-05T14:00"
        )
        value["abnormalities"][4].update(reported_minutes=60)
    try:
        with closing(sqlite3.connect(destination)) as connection:
            import_records(value["production"], connection)
            connection.execute(abnormality.SCHEMA)
            connection.execute(
                "CREATE TABLE research_fixture(dataset_id TEXT PRIMARY KEY, logical_sha256 TEXT NOT NULL)"
            )
            with connection:
                abnormality.import_events(value["abnormalities"], connection)
                logical = hashlib.sha256(
                    json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
                ).hexdigest()
                connection.execute(
                    "INSERT INTO research_fixture VALUES (?,?)", (variant, logical)
                )
        return dict(
            path=str(destination),
            dataset=variant,
            logical_sha256=logical,
            sha256=hashlib.sha256(destination.read_bytes()).hexdigest(),
        )
    except Exception:
        destination.unlink(missing_ok=True)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            [
                build(args.output / "sample_a.db", "A"),
                build(args.output / "sample_b.db", "B"),
            ],
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
