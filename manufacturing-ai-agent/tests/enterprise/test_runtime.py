"""Synthetic-only checks for explicitly assumed runtime ranges."""

import copy
from datetime import datetime, timedelta
import random
import sqlite3

import pytest
from backend.models import RuntimeEstimate
from backend.runtime import estimate_runtime, read_runtime_estimate


DAY = "2026-01-10"


def prod(machine="FX1", day=DAY, shift="Day", product="TEST-A"):
    return dict(machine_id=machine, production_date=day, shift=shift, product=product)


def event(
    start="10:00",
    end="11:00",
    *,
    day=DAY,
    end_day=None,
    machine="FX1",
    shift="Day",
    **extra,
):
    start = None if start is None else day + "T" + start
    end = None if end is None else (end_day or day) + "T" + end
    minutes = (
        (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds()
        / 60
        if start and end
        else None
    )
    return dict(
        machine_id=machine,
        production_date=day,
        shift=shift,
        started_at=start,
        ended_at=end,
        reported_minutes=minutes,
        **extra,
    )


def estimate(rows=(), events=(), *, start=DAY, end=DAY, shift="Day", **extra):
    result = estimate_runtime(
        list(rows), list(events), start, end, shift=shift, **extra
    )
    RuntimeEstimate.model_validate(result)
    return result


def test_flexible_break_range_and_inputs_unchanged():
    rows, events = [prod()], [event()]
    before = copy.deepcopy((rows, events))
    result = estimate(rows, events)
    assert (result["available_minutes"], result["merged_stop_minutes"]) == (600, 60)
    assert (result["runtime_lower_minutes"], result["runtime_upper_minutes"]) == (
        540,
        600,
    )
    assert (result["utilization_lower"], result["utilization_upper"]) == (0.9, 1)
    assert (rows, events) == before


def test_no_records_unavailable_and_no_known_stops_explicitly_assumed():
    empty = estimate(machines=["FX1"])
    assert empty["status"] == "unavailable"
    assert empty["runtime_lower_minutes"] is None and empty["utilization_upper"] is None
    assert empty["unrecorded_shift_count"] == 1
    known = estimate([prod()])
    assert known["runtime_lower_minutes"] == known["runtime_upper_minutes"] == 600
    assert known["no_recorded_stop_shift_count"] == 1
    assert any("unrecorded stops" in a for a in known["assumptions"])


def test_union_includes_containment_adjacent_and_cross_category_shift_labels():
    events = [
        event("09:00", "11:00"),
        event("10:00", "12:00", shift="Night"),
        event("09:15", "09:30"),
        event("12:00", "13:00"),
        event("09:00", "11:00"),
    ]
    result = estimate([], events)
    assert result["observed_shift_count"] == 1
    assert result["merged_stop_minutes"] == 240
    assert (
        result["runtime_lower_minutes"] == 360
        and result["runtime_upper_minutes"] == 480
    )


@pytest.mark.parametrize(
    "minutes,lower,upper",
    [
        (0, 600, 600),
        (60, 540, 600),
        (120, 480, 600),
        (600, 0, 120),
        (660, 0, 60),
        (720, 0, 0),
    ],
)
def test_stop_and_break_boundaries(minutes, lower, upper):
    end = (
        datetime.fromisoformat(DAY + "T08:00") + timedelta(minutes=minutes)
    ).strftime("%H:%M")
    result = estimate([prod()], [event("08:00", end)])
    assert (result["runtime_lower_minutes"], result["runtime_upper_minutes"]) == (
        lower,
        upper,
    )


def test_clip_at_boundaries_and_zero_event_evidence():
    before = event("06:00", "08:00")
    assert estimate([], [before])["observed_shift_count"] == 0
    zero = estimate([], [event("08:00", "08:00")])
    assert zero["observed_shift_count"] == 1 and zero["merged_stop_minutes"] == 0
    overnight = event("23:00", "11:00", day="2026-01-09", end_day=DAY)
    result = estimate([prod()], [overnight])
    assert (
        result["merged_stop_minutes"] == 180
    )  # 08-11 only, carried in from yesterday.
    result = estimate(
        [], [event("19:00", "09:00", end_day="2026-01-11")], shift="Night"
    )
    assert result["merged_stop_minutes"] == 720 and result["runtime_upper_minutes"] == 0


def test_clock_shift_overrides_no_source_label_and_does_not_extend_open_events():
    first = event("03:00", "04:00", day="2026-01-11", shift="Day", status="Open")
    result = estimate([], [first], shift="Night")
    assert result["merged_stop_minutes"] == 60 and result["observed_shift_count"] == 1
    assert first["shift"] == "Day" and first["production_date"] == "2026-01-11"
    assert (
        estimate([], [first], start="2026-01-11", end="2026-01-11", shift="Day")[
            "status"
        ]
        == "unavailable"
    )


def test_unique_product_keys_per_machine_and_weighted_ratio():
    rows = [prod(), prod(product="TEST-B"), prod(day="2026-01-11"), prod(machine="FX2")]
    result = estimate(rows, [event("08:00", "18:00")], end="2026-01-11")
    assert result["observed_shift_count"] == 3 and result["available_minutes"] == 1800
    assert (result["runtime_lower_minutes"], result["runtime_upper_minutes"]) == (
        1200,
        1320,
    )
    assert result["utilization_lower"] == pytest.approx(2 / 3)
    assert result["utilization_lower"] != 0.75  # Not the mean of machine percentages.
    separate = estimate([prod(), prod(machine="FX2")], [event(), event(machine="FX2")])
    assert separate["merged_stop_minutes"] == 120


@pytest.mark.parametrize(
    "bad",
    [
        event(start=None),
        event(end=None),
        event(start=None, end=None),
        event("11:00", "10:00"),
        dict(event(), reported_minutes=999),
        dict(event(), started_at=DAY),
    ],
)
def test_missing_and_contradictory_times_block_affected_estimates(bad):
    result = estimate([prod(), prod(machine="FX2")], [bad])
    assert result["status"] == "unavailable" and result["invalid_event_count"] == 1
    assert (
        result["runtime_lower_minutes"] is None
        and result["merged_stop_minutes"] is None
    )
    assert result["per_machine"][1]["runtime_lower_minutes"] == 600


def test_second_precision_and_missing_reported_minutes():
    result = estimate([], [dict(event("10:00:00", "10:01:30"), reported_minutes=None)])
    assert result["merged_stop_minutes"] == 1.5


def test_randomized_interval_union_against_independent_minute_occupancy():
    rng = random.Random(61)
    for _ in range(60):
        intervals = [
            (rng.randrange(-120, 840), rng.randrange(-120, 840)) for _ in range(8)
        ]
        spans = sorted((min(a, b), max(a, b)) for a, b in intervals)
        occupied = set()
        events = []
        origin = datetime.fromisoformat(DAY + "T08:00")
        for a, b in spans:
            left, right = origin + timedelta(minutes=a), origin + timedelta(minutes=b)
            events.append(event(left.strftime("%H:%M"), right.strftime("%H:%M")))
            occupied.update(range(max(0, a), min(720, b)))
        result = estimate([prod()], events)
        assert result["merged_stop_minutes"] == len(occupied)
        assert (
            0
            <= result["runtime_lower_minutes"]
            <= result["runtime_upper_minutes"]
            <= 600
        )


def test_readonly_loader_carry_in_and_product_independence(tmp_path):
    db = tmp_path / "runtime.db"
    with sqlite3.connect(db) as c:
        c.execute(
            "CREATE TABLE slitting_records (production_date TEXT,shift TEXT,machine_id TEXT,product TEXT)"
        )
        c.execute(
            "INSERT INTO slitting_records VALUES (?,?,?,?)",
            (DAY, "Day", "FX1", "TEST-A"),
        )
        c.execute(
            "INSERT INTO slitting_records VALUES (?,?,?,?)",
            (DAY, "Day", "FX1", "TEST-B"),
        )
        c.execute(
            "CREATE TABLE abnormality_events (production_date TEXT,shift TEXT,machine_id TEXT,started_at TEXT,ended_at TEXT,reported_minutes REAL)"
        )
        e = event("23:00", "11:00", day="2026-01-09", end_day=DAY, shift="Night")
        c.execute(
            "INSERT INTO abnormality_events VALUES (?,?,?,?,?,?)",
            tuple(
                e[k]
                for k in (
                    "production_date",
                    "shift",
                    "machine_id",
                    "started_at",
                    "ended_at",
                    "reported_minutes",
                )
            ),
        )
    before = db.read_bytes()
    result = read_runtime_estimate(db, DAY, DAY, shift="Day")
    RuntimeEstimate.model_validate(result)
    assert result["available_minutes"] == 600 and result["merged_stop_minutes"] == 180
    assert (
        result["runtime_lower_minutes"] == 420
        and result["runtime_upper_minutes"] == 540
    )
    assert (
        read_runtime_estimate(db, DAY, DAY, shift="Day", machine="FX3")["status"]
        == "unavailable"
    )
    assert db.read_bytes() == before


@pytest.mark.parametrize("shift", ["All", "Day", "Night"])
def test_api_contract_filter_independence_and_demo_isolation(
    tmp_path, monkeypatch, shift
):
    from fastapi.testclient import TestClient
    from backend.main import app
    from production import import_records
    import abnormality

    db = tmp_path / "api.db"
    monkeypatch.setenv("PRODUCTION_DB", str(db))
    monkeypatch.setenv("KNOWLEDGE_DIR", str(tmp_path / "knowledge"))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    rows = [
        dict(
            **prod(product=product),
            planned_rolls=10,
            input_rolls=8,
            qualified_rolls=12,
            actual_output_m2=100.0,
            qualified_output_m2=80.0,
            reported_yield_pct=None,
            source_report_date=DAY,
            source_shift_label="Day",
            source_name="PRIVATE",
            notes="PRIVATE",
        )
        for product in ("TEST-A", "TEST-B")
    ]
    with sqlite3.connect(db) as c:
        import_records(rows, c)
        c.execute(abnormality.SCHEMA)
        e = dict(
            event(shift="Night"),
            event_id="TEST",
            category="QC Issue",
            subcategory="",
            status="Closed",
            source_name="PRIVATE",
            notes="PRIVATE",
        )
        abnormality.import_events([e], c)
    before = db.read_bytes()
    with TestClient(app) as client:
        args = dict(start=DAY, end=DAY, shift=shift, source="reviewed")
        response = client.get("/api/dashboard/summary", params=args)
        assert response.status_code == 200
        result = response.json()
        assert result["summary"]["machine_utilization"] is None
        assert "PRIVATE" not in str(result)
        one = client.get(
            "/api/dashboard/summary", params=dict(args, product="TEST-A")
        ).json()
        assert result["runtime_estimate"] == one["runtime_estimate"]
        if shift in ("All", "Day"):
            assert result["runtime_estimate"]["runtime_lower_minutes"] == 540
            assert result["runtime_estimate"]["observed_shift_count"] == 1
        else:
            assert result["runtime_estimate"]["status"] == "unavailable"
        # Demo requests are rejected and never trigger a real-data fallback.
        monkeypatch.setenv("PRODUCTION_DB", str(tmp_path / "does-not-exist.db"))
        demo = client.get(
            "/api/dashboard/summary",
            params=dict(
                start="2026-10-12", end="2026-10-18", shift=shift, source="demo"
            ),
        )
        assert demo.status_code == 422
        assert not (tmp_path / "does-not-exist.db").exists()
    assert db.read_bytes() == before
