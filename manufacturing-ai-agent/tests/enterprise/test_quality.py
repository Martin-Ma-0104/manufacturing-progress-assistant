"""Synthetic quality import, recovery, exact grouping and independent API scopes."""

from contextlib import closing
from copy import deepcopy
from decimal import Decimal
import json
import sqlite3

from fastapi.testclient import TestClient
import pytest
from backend.main import app
from backend import data, quality
from backend.models import Scope
from production import import_records as import_production
import slitting_quality as q


def record(day="2026-01-10", shift="Day", sequence=1, **changes):
    code = day[2:].replace("-", "")
    return dict(
        product_id=f"S{code}{'UA' if shift == 'Day' else 'UB'}3-{sequence:05d}",
        production_date=day,
        shift=shift,
        machine_id="FX1",
        product="TEST-SPEC",
        station="2",
        specification="TEST 88.8 mm / 2000 m",
        rejected_area_m2="177.6",
        area_unit="m2",
        ccd_defect="",
        appearance_defect="Crease",
        remarks="",
        coating_barcode="TEST-UPSTREAM",
        coating_machine="TEST-U1",
        source_name="PRIVATE source.xlsx",
        source_row=2,
        notes="PRIVATE note",
        **changes,
    )


def altered(**changes):
    row = record()
    row.update(changes)
    return row


def test_confirmed_date_shift_and_invalid_identifiers():
    assert q.barcode_scope("S261028UA3-001") == ("2026-10-28", "Day")
    assert q.barcode_scope("S261028UB3-001") == ("2026-10-28", "Night")
    assert q.barcode_scope("S240229UB3-001") == ("2024-02-29", "Night")
    for bad in (
        None,
        "S261332UA3-001",
        "S260229UA3-001",
        "S261028UC3-001",
        "S261028UA3-001junk",
    ):
        with pytest.raises(ValueError):
            q.barcode_scope(bad)


@pytest.mark.parametrize(
    "change",
    [
        {"rejected_area_m2": -1},
        {"rejected_area_m2": "-1"},
        {"rejected_area_m2": 177.6},
        {"rejected_area_m2": "NaN"},
        {"rejected_area_m2": "1e3"},
        {"rejected_area_m2": "0.0000001"},
        {"rejected_area_m2": "1000000001"},
        {"area_unit": "rolls"},
        {"area_unit": "m²"},
        {"production_date": "2026-01-09"},
        {"shift": "Night"},
        {"source_row": True},
        {"source_row": 1},
        {"source_name": " "},
        {"machine_id": "FX1';DROP TABLE x"},
        {"extra": "unsupported"},
        {"remarks": None},
    ],
)
def test_invalid_records_are_rejected_before_schema_write(change):
    with closing(sqlite3.connect(":memory:")) as db:
        with pytest.raises(ValueError):
            q.import_records([altered(**change)], db)
        assert not q.has_table(db)


def test_exact_roundtrip_zero_and_original_precision():
    rows = [record(sequence=i) for i in range(1, 5)]
    for row, area in zip(rows, ("177.689", "355.2", "0", "0.000001")):
        row["rejected_area_m2"] = area
    with closing(sqlite3.connect(":memory:")) as db:
        assert q.import_records(rows, db) == 4
        read = q.read_records(db)
        assert read == rows
        assert q.summarize(read)["rejected_area_m2"] == "532.889001"
        assert all(
            x[0] == "integer"
            for x in db.execute("SELECT typeof(area_microm2) FROM slitting_rejects")
        )
        payload = json.dumps(dict(schema=q.VERSION, records=read))
        with closing(sqlite3.connect(":memory:")) as restored:
            assert q.import_records(q.decode_payload(payload), restored) == 4
            assert q.read_records(restored) == rows


def test_idempotence_different_filename_and_conflict_roll_back_whole_batch():
    first = record()
    with closing(sqlite3.connect(":memory:")) as db:
        assert q.import_records([first, first], db) == 1
        changed_source = altered(
            source_name="other.xlsx", source_row=100, notes="new provenance"
        )
        assert q.import_records([changed_source], db) == 0
        assert q.read_records(db) == [first]
        with pytest.raises(ValueError, match="Conflicting"):
            q.import_records(
                [record(sequence=2), altered(rejected_area_m2="355.2")], db
            )
        assert q.read_records(db) == [first]
        with pytest.raises(ValueError):
            q.import_records([first, altered(appearance_defect="Other")], db)
        assert q.read_records(db) == [first]


def test_caller_transaction_and_atomic_schema_rollback():
    with closing(sqlite3.connect(":memory:")) as db:
        with pytest.raises(ValueError):
            q.import_records([record()], db, manage_transaction=False)
        db.execute("BEGIN IMMEDIATE")
        with pytest.raises(ValueError):
            q.import_records([record()], db)
        assert q.import_records([record()], db, manage_transaction=False) == 1
        db.rollback()
        assert not q.has_table(db)


def test_defect_grouping_has_no_duplicate_area_and_preserves_suffixes():
    rows = [
        altered(ccd_defect="Foreign object -1", appearance_defect="Foreign object -1"),
        record(sequence=2),
        record(sequence=3),
        record(sequence=4),
    ]
    rows[1].update(ccd_defect="Foreign object", appearance_defect="")
    rows[2].update(ccd_defect="Bright spot", appearance_defect="Scratch")
    rows[3].update(ccd_defect="", appearance_defect="")
    before = deepcopy(rows)
    result = q.summarize(rows)
    assert rows == before
    assert result["detail_count"] == 4 and result["rejected_area_m2"] == "710.4"
    assert len(result["by_reason"]) == 4
    assert sum(Decimal(r["rejected_area_m2"]) for r in result["by_reason"]) == Decimal(
        "710.4"
    )
    labels = [r["label"] for r in result["by_reason"]]
    assert {
        "Foreign object -1",
        "Foreign object",
        "CCD: Bright spot; Appearance: Scratch",
        "Not recorded",
    } == set(labels)


def test_payload_contract():
    for value in (
        [],
        {},
        {"schema": "unknown", "records": []},
        {"schema": q.VERSION, "records": [], "extra": 1},
    ):
        with pytest.raises(ValueError):
            q.decode_payload(json.dumps(value))


@pytest.fixture()
def reviewed(tmp_path, monkeypatch):
    path = tmp_path / "records.db"
    monkeypatch.setenv("PRODUCTION_DB", str(path))
    with closing(sqlite3.connect(path)) as db:
        import_production(
            [
                dict(
                    production_date="2026-01-10",
                    shift="Day",
                    machine_id="FX1",
                    product="TEST-SPEC",
                    planned_rolls=10,
                    input_rolls=8,
                    qualified_rolls=10,
                    actual_output_m2=100,
                    qualified_output_m2=80,
                    reported_yield_pct=None,
                    source_report_date="2026-01-10",
                    source_shift_label="Day",
                    source_name="PRIVATE",
                    notes="",
                )
            ],
            db,
        )
    scope = Scope(start="2026-01-10", end="2026-01-10")
    baseline = data.dashboard(scope)
    rows = [record(sequence=i) for i in range(1, 206)]
    night = record(day="2026-01-12", shift="Night")
    night.update(machine_id="FX9", product="QUALITY-ONLY-SPEC", rejected_area_m2="0")
    with closing(sqlite3.connect(path)) as db:
        q.import_records(rows + [night], db)
    before = path.read_bytes()
    yield path, baseline
    assert path.read_bytes() == before


def test_quality_only_dates_and_products_remain_visible_without_runtime_evidence(
    reviewed,
):
    path, baseline = reviewed
    opts = data.options()
    assert (
        opts["dates"][-1] == "2026-01-12"
        and "QUALITY-ONLY-SPEC" in opts["products"]
        and "FX9" in opts["machines"]
    )
    dashboard = data.dashboard(Scope(start="2026-01-10", end="2026-01-10"))
    assert dashboard["summary"] == baseline["summary"]
    assert dashboard["runtime_estimate"] == baseline["runtime_estimate"]
    empty = data.dashboard(Scope(start="2026-01-12", end="2026-01-12", machine="FX9"))
    assert empty["summary"]["input_rolls"] is None
    assert empty["runtime_estimate"]["status"] == "unavailable"
    only = quality.summary(
        Scope(
            start="2026-01-12",
            end="2026-01-12",
            machine="FX9",
            product="QUALITY-ONLY-SPEC",
            shift="Night",
        )
    )
    assert only["rejected_area_m2"] == "0" and only["detail_count"] == 1
    assert only["unmatched_production_group_count"] == 1
    assert only["recorded_shifts"] == ["Night"]


def test_quality_api_paging_filters_missing_and_private_provenance(reviewed):
    with TestClient(app) as client:
        response = client.get(
            "/api/production/quality",
            params={"start": "2026-01-10", "end": "2026-01-12"},
        )
        assert response.status_code == 200
        result = response.json()
        assert result["detail_count"] == 206 and result["rejected_area_m2"] == "36408"
        assert result["missing_dates"] == ["2026-01-11"]
        assert "PRIVATE" not in response.text and "TEST-UPSTREAM" not in response.text
        assert (
            result["matched_production_group_count"]
            == result["unmatched_production_group_count"]
            == 1
        )
        ids = []
        for offset in (0, 100, 200):
            page = client.get(
                "/api/production/quality/records",
                params={"start": "2026-01-10", "end": "2026-01-12", "offset": offset},
            ).json()
            ids.extend(r["product_id"] for r in page["records"])
            assert page["total"] == 206 and len(page["records"]) <= 100
            assert "PRIVATE" not in str(page)
        assert len(ids) == len(set(ids)) == 206
        night = client.get("/api/production/quality", params={"shift": "Night"}).json()
        assert night["detail_count"] == 1 and night["rejected_area_m2"] == "0"
        empty = client.get(
            "/api/production/quality",
            params={"start": "2026-01-11", "end": "2026-01-11"},
        ).json()
        assert empty["rejected_area_m2"] is None and empty["status"] == "no_records"
        for endpoint, params in [
            ("", {"machine": "bad'--"}),
            ("", {"product": "unknown"}),
            ("", {"source": "demo"}),
            ("", {"start": "2026-01-01", "end": "2026-02-28"}),
            ("/records", {"offset": -1}),
            ("/records", {"limit": 201}),
        ]:
            assert (
                client.get(
                    "/api/production/quality" + endpoint, params=params
                ).status_code
                == 422
            )
        assert (
            client.get(
                "/api/production/quality/records", params={"offset": 10000}
            ).json()["records"]
            == []
        )


def test_no_quality_table_and_missing_db_do_not_create_anything(tmp_path, monkeypatch):
    path = tmp_path / "empty.db"
    monkeypatch.setenv("PRODUCTION_DB", str(path))
    assert quality.summary(Scope())["status"] == "not_imported"
    assert not path.exists()
    with closing(sqlite3.connect(path)):
        pass
    before = path.read_bytes()
    assert quality.summary(Scope())["rejected_area_m2"] is None
    assert path.read_bytes() == before


def test_cli_export_refuses_existing_destination(reviewed, tmp_path):
    import subprocess
    import sys
    from pathlib import Path

    path, _ = reviewed
    script = Path(q.__file__)
    destination = tmp_path / "recovery.json"
    destination.write_text("existing recovery")
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            str(script),
            "--db",
            str(path),
            "--export-json",
            str(destination),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1 and destination.read_text() == "existing recovery"
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            str(script),
            "--db",
            str(path),
            "--export-json",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    destination.unlink()
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            str(script),
            "--db",
            str(path),
            "--export-json",
            str(destination),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert len(q.decode_payload(destination.read_text())) == 206
