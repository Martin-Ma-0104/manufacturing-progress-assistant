"""Reviewed rejected-film records. Exact areas, atomic import, no production updates.

JSON round-trip: python slitting_quality.py --import-json reviewed-quality.json
               python slitting_quality.py --export-json quality-recovery.json
These files are local business data and must not be committed.
"""

import argparse
from contextlib import closing
from datetime import date
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re
import sqlite3

SCALE = 1_000_000  # integer micro-square-metres; source precision is preserved
VERSION = "slitting-quality-v1"
FIELDS = (
    "product_id",
    "production_date",
    "shift",
    "machine_id",
    "product",
    "station",
    "specification",
    "rejected_area_m2",
    "area_unit",
    "ccd_defect",
    "appearance_defect",
    "remarks",
    "coating_barcode",
    "coating_machine",
    "source_name",
    "source_row",
    "notes",
)
COLUMNS = tuple("area_microm2" if k == "rejected_area_m2" else k for k in FIELDS)
BUSINESS = tuple(k for k in FIELDS if k not in ("source_name", "source_row", "notes"))
SCHEMA = """CREATE TABLE IF NOT EXISTS slitting_rejects (
    product_id TEXT PRIMARY KEY NOT NULL,
    production_date TEXT NOT NULL,
    shift TEXT NOT NULL CHECK(shift IN ('Day','Night')),
    machine_id TEXT NOT NULL, product TEXT NOT NULL, station TEXT NOT NULL,
    specification TEXT NOT NULL,
    area_microm2 INTEGER NOT NULL CHECK(typeof(area_microm2)='integer' AND area_microm2>=0),
    area_unit TEXT NOT NULL CHECK(area_unit='m2'),
    ccd_defect TEXT NOT NULL, appearance_defect TEXT NOT NULL, remarks TEXT NOT NULL,
    coating_barcode TEXT NOT NULL, coating_machine TEXT NOT NULL,
    source_name TEXT NOT NULL, source_row INTEGER NOT NULL CHECK(source_row>=2), notes TEXT NOT NULL
)"""
INDEX = "CREATE INDEX IF NOT EXISTS slitting_rejects_scope ON slitting_rejects(production_date,shift,machine_id,product)"


def area_units(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d+(?:\.\d{1,6})?", value):
        raise ValueError(
            "Rejected area must be a nonnegative decimal string with at most six decimal places."
        )
    try:
        number = Decimal(value)
    except InvalidOperation:
        raise ValueError("Invalid rejected area.") from None
    if number > Decimal("1000000000"):
        raise ValueError("Rejected area exceeds the supported per-record limit.")
    return int(number * SCALE)


def area_text(units):
    whole, remainder = divmod(units, SCALE)
    return str(whole) if not remainder else f"{whole}.{remainder:06d}".rstrip("0")


def barcode_scope(product_id):
    if not isinstance(product_id, str):
        raise ValueError("Product ID must be text.")
    match = re.fullmatch(r"S(\d{6})(UA|UB)[A-Za-z0-9]*-\d+", product_id)
    if not match:
        raise ValueError("Product ID needs the confirmed S + YYMMDD + UA/UB format.")
    digits = match[1]
    try:
        day = date(
            2000 + int(digits[:2]), int(digits[2:4]), int(digits[4:])
        ).isoformat()
    except ValueError:
        raise ValueError("Product ID contains an invalid calendar date.") from None
    return day, {"UA": "Day", "UB": "Night"}[match[2]]


def normalize(record):
    if not isinstance(record, dict) or set(record) != set(FIELDS):
        raise ValueError(
            "Quality record fields must match the versioned JSON contract."
        )
    for key in FIELDS:
        if key == "source_row":
            if type(record[key]) is not int or record[key] < 2:
                raise ValueError("Source row must be an integer at least two.")
        elif not isinstance(record[key], str) or len(record[key]) > 4000:
            raise ValueError(f"Quality {key} must be text of at most 4000 characters.")
    for key in ("product_id", "machine_id", "product", "specification", "source_name"):
        if not record[key].strip():
            raise ValueError(f"Quality {key} cannot be blank.")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", record["machine_id"]):
        raise ValueError("Invalid quality machine ID.")
    if record["area_unit"] != "m2":
        raise ValueError("Reviewed rejected-film area must use m2.")
    if (record["production_date"], record["shift"]) != barcode_scope(
        record["product_id"]
    ):
        raise ValueError(
            "Quality date/shift conflicts with the confirmed product ID rule."
        )
    result = dict(record)
    result["rejected_area_m2"] = area_text(area_units(record["rejected_area_m2"]))
    return result


def has_table(connection):
    return bool(
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='slitting_rejects'"
        ).fetchone()
    )


def _decode(values):
    result = dict(zip(FIELDS, values))
    result["rejected_area_m2"] = area_text(result["rejected_area_m2"])
    return result


def import_records(records, connection, *, manage_transaction=True):
    if not isinstance(records, list) or not records:
        raise ValueError("Import needs a nonempty list of reviewed quality records.")
    batch = {}
    for raw in records:
        row = normalize(raw)
        previous = batch.get(row["product_id"])
        if previous and any(previous[k] != row[k] for k in BUSINESS):
            raise ValueError(
                "Conflicting product ID within quality batch; nothing imported."
            )
        batch.setdefault(row["product_id"], row)
    if manage_transaction:
        if connection.in_transaction:
            raise ValueError(
                "Quality import requires its own transaction or explicit transaction ownership."
            )
        connection.execute("BEGIN IMMEDIATE")
    elif not connection.in_transaction:
        raise ValueError(
            "Caller must start a transaction before importing quality records."
        )
    try:
        connection.execute(SCHEMA)
        connection.execute(INDEX)
        added = 0
        for row in batch.values():
            existing = connection.execute(
                "SELECT "
                + ",".join(COLUMNS)
                + " FROM slitting_rejects WHERE product_id=?",
                (row["product_id"],),
            ).fetchone()
            if existing is not None:
                previous = _decode(existing)
                if any(previous[k] != row[k] for k in BUSINESS):
                    raise ValueError(
                        "Conflicting existing quality product ID; batch rolled back without overwrite."
                    )
                continue
            values = [
                area_units(row[k]) if k == "rejected_area_m2" else row[k]
                for k in FIELDS
            ]
            connection.execute(
                "INSERT INTO slitting_rejects ("
                + ",".join(COLUMNS)
                + ") VALUES ("
                + ",".join("?" for _ in FIELDS)
                + ")",
                values,
            )
            added += 1
        if manage_transaction:
            connection.commit()
        return added
    except Exception:
        if manage_transaction:
            connection.rollback()
        raise


def read_records(
    connection, start=None, end=None, shift="All", machine=None, product=None
):
    if not has_table(connection):
        return []
    clauses, args = [], []
    for column, op, value in (
        ("production_date", ">=", start),
        ("production_date", "<=", end),
        ("shift", "=", shift if shift != "All" else None),
        ("machine_id", "=", machine),
        ("product", "=", product),
    ):
        if value:
            clauses.append(f"{column}{op}?")
            args.append(value)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    sql = (
        "SELECT "
        + ",".join(COLUMNS)
        + " FROM slitting_rejects"
        + where
        + " ORDER BY production_date,shift,machine_id,product_id"
    )
    return [_decode(row) for row in connection.execute(sql, args)]


def reason(record):
    ccd, appearance = record["ccd_defect"].strip(), record["appearance_defect"].strip()
    if ccd and appearance and ccd != appearance:
        return f"CCD: {ccd}; Appearance: {appearance}"
    return ccd or appearance or "Not recorded"


def summarize(records):
    def group(key):
        groups = {}
        for record in records:
            label = key(record)
            value = groups.setdefault(label, [0, 0])
            value[0] += 1
            value[1] += area_units(record["rejected_area_m2"])
        return [
            dict(label=label, detail_count=count, rejected_area_m2=area_text(area))
            for label, (count, area) in sorted(groups.items())
        ]

    return dict(
        detail_count=len(records),
        machine_count=len({r["machine_id"] for r in records}),
        rejected_area_m2=area_text(
            sum(area_units(r["rejected_area_m2"]) for r in records)
        )
        if records
        else None,
        by_machine=group(lambda r: r["machine_id"]),
        by_reason=group(reason),
        daily=group(lambda r: r["production_date"]),
    )


def decode_payload(raw):
    value = json.loads(raw)
    if (
        not isinstance(value, dict)
        or set(value) != {"schema", "records"}
        or value["schema"] != VERSION
        or not isinstance(value["records"], list)
    ):
        raise ValueError("Expected a slitting-quality-v1 recovery bundle.")
    return [normalize(r) for r in value["records"]]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db",
        type=Path,
        default=Path(__file__).resolve().with_name("manufacturing.db"),
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--import-json", type=Path)
    action.add_argument("--export-json", type=Path)
    args = parser.parse_args()
    try:
        mode = "rw" if args.import_json else "ro"
        with closing(
            sqlite3.connect(args.db.resolve().as_uri() + "?mode=" + mode, uri=True)
        ) as connection:
            if args.import_json:
                added = import_records(
                    decode_payload(args.import_json.read_text(encoding="utf-8")),
                    connection,
                )
                print(f"Added {added} reviewed quality records.")
            else:
                connection.execute("PRAGMA query_only=ON")
                records = read_records(connection)
                # Never overwrite an existing workbook, database, or prior recovery file.
                content = (
                    json.dumps(
                        dict(schema=VERSION, records=records),
                        ensure_ascii=False,
                        indent=2,
                    )
                    + "\n"
                )
                with args.export_json.open("x", encoding="utf-8") as output:
                    output.write(content)
                print(
                    f"Exported {len(records)} quality records; legacy cloud bundles remain separate."
                )
    except (ValueError, OSError, sqlite3.Error) as exc:
        parser.exit(1, f"Quality operation failed: {exc}\n")


if __name__ == "__main__":
    main()
