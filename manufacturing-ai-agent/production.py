"""Daily slitting records: validated, atomic JSON import with duplicate protection."""
import argparse
import json
import math
import sqlite3
from contextlib import closing, nullcontext
from datetime import date
from pathlib import Path

from database import DB_PATH, get_connection

SCHEMA = """
CREATE TABLE IF NOT EXISTS slitting_records (
    id INTEGER PRIMARY KEY,
    production_date TEXT NOT NULL,
    shift TEXT NOT NULL CHECK (shift IN ('Day', 'Night')),
    machine_id TEXT NOT NULL,
    product TEXT NOT NULL,
    planned_rolls INTEGER NOT NULL CHECK (planned_rolls >= 0),
    input_rolls INTEGER NOT NULL CHECK (input_rolls >= 0),
    qualified_rolls INTEGER NOT NULL CHECK (qualified_rolls >= 0),
    actual_output_m2 REAL NOT NULL CHECK (actual_output_m2 >= 0),
    qualified_output_m2 REAL NOT NULL CHECK (
        qualified_output_m2 >= 0 AND qualified_output_m2 <= actual_output_m2),
    reported_yield_pct REAL CHECK (reported_yield_pct BETWEEN 0 AND 100),
    source_report_date TEXT NOT NULL,
    source_shift_label TEXT NOT NULL,
    source_name TEXT NOT NULL,
    notes TEXT NOT NULL,
    UNIQUE (production_date, shift, machine_id, product)
)
"""
FIELDS = (
    'production_date', 'shift', 'machine_id', 'product', 'planned_rolls',
    'input_rolls', 'qualified_rolls', 'actual_output_m2', 'qualified_output_m2',
    'reported_yield_pct', 'source_report_date', 'source_shift_label', 'source_name', 'notes',
)


def validate(record):
    if set(record) != set(FIELDS):
        raise ValueError('Record fields must match the documented JSON format exactly.')
    for field in ('production_date', 'source_report_date'):
        if date.fromisoformat(record[field]).isoformat() != record[field]:
            raise ValueError(f'{field} must use YYYY-MM-DD.')
    if record['shift'] not in ('Day', 'Night'):
        raise ValueError('shift must be Day or Night.')
    for field in ('machine_id', 'product', 'source_shift_label', 'source_name'):
        if not isinstance(record[field], str) or not record[field].strip():
            raise ValueError(f'{field} must be nonempty text.')
    if not isinstance(record['notes'], str):
        raise ValueError('notes must be text.')
    for field in ('planned_rolls', 'input_rolls', 'qualified_rolls'):
        if type(record[field]) is not int or record[field] < 0:
            raise ValueError(f'{field} must be a nonnegative integer.')
    for field in ('actual_output_m2', 'qualified_output_m2', 'reported_yield_pct'):
        value = record[field]
        if field == 'reported_yield_pct' and value is None:
            continue
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ValueError(f'{field} must be a finite nonnegative number.')
    if record['qualified_output_m2'] > record['actual_output_m2']:
        raise ValueError('Qualified area cannot exceed actual output area.')
    if record['reported_yield_pct'] is not None and record['reported_yield_pct'] > 100:
        raise ValueError('Reported yield must be between 0 and 100, or null.')


def import_records(records, connection, *, manage_transaction=True):
    """Same key + same values is a no-op; conflicting values require explicit correction."""
    if not isinstance(records, list) or not records:
        raise ValueError('Input must be a nonempty JSON list of records.')
    for record in records:
        validate(record)
    connection.execute(SCHEMA)
    added = 0
    with connection if manage_transaction else nullcontext():
        for record in records:
            values = tuple(record[field] for field in FIELDS)
            existing = connection.execute(
                f"SELECT {', '.join(FIELDS)} FROM slitting_records "
                'WHERE production_date=? AND shift=? AND machine_id=? AND product=?',
                values[:4],
            ).fetchone()
            if existing is not None:
                if tuple(existing) != values:
                    raise ValueError(f'Conflicting existing record: {values[:4]}. No rows imported.')
                continue
            connection.execute(
                f"INSERT INTO slitting_records ({', '.join(FIELDS)}) "
                f"VALUES ({', '.join('?' for _ in FIELDS)})", values,
            )
            added += 1
    return added


def get_records(connection, production_date):
    date.fromisoformat(production_date)
    cursor = connection.execute(
        f"SELECT {', '.join(FIELDS)} FROM slitting_records WHERE production_date=? "
        "ORDER BY CASE shift WHEN 'Day' THEN 0 ELSE 1 END, machine_id, product",
        (production_date,),
    )
    return [dict(zip(FIELDS, row)) for row in cursor.fetchall()]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path, help='Local JSON list; never commit real production data.')
    args = parser.parse_args()
    if not DB_PATH.is_file():
        parser.exit(1, 'Database not initialized. Run python3 init_db.py first.\n')
    try:
        records = json.loads(args.input.read_text(encoding='utf-8'))
        with closing(get_connection()) as connection:
            added = import_records(records, connection)
        print(f'Imported {added} records; skipped {len(records) - added} identical records.')
    except (OSError, ValueError, TypeError, sqlite3.Error) as error:
        parser.exit(1, f'Import failed: {error}\n')


if __name__ == '__main__':
    main()
