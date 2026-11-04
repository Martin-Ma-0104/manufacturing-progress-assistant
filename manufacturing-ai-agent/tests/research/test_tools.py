from contextlib import closing
import sqlite3
import pytest
from research.harry_milestone.fixtures import build
from research.harry_milestone.contracts import Query, TOOL_A
from research.harry_milestone.tools import DataSource, ResearchTools


@pytest.fixture()
def tools(tmp_path):
    path = tmp_path / "a.db"
    build(path)
    service = ResearchTools(DataSource(path, "synthetic"))
    before = path.read_bytes()
    yield service
    assert path.read_bytes() == before


def query(**changes):
    return Query(**(dict(start_date="2026-01-05", end_date="2026-01-07") | changes))


def test_production_totals_shortfall_units_and_no_event_join(tools):
    value = tools.compare_production_inputs(query())
    assert [
        value[k]
        for k in (
            "planned_inputs",
            "actual_inputs",
            "difference",
            "shortfall",
            "net_shortfall",
            "excess",
            "record_count",
        )
    ] == [70, 56, -14, 18, 14, 4, 8]
    offset = tools.compare_production_inputs(
        query(start_date="2026-01-05", end_date="2026-01-05", machine_id="FX1")
    )
    assert (
        offset["difference"] == offset["net_shortfall"] == 0
        and offset["shortfall"] == 2
    )
    assert value["unit"] == "input mother rolls"
    assert "notes" not in str(value) and "SYN-A" not in str(value)


def test_rank_missing_overlap_overnight_unresolved_and_changed_database(
    tools, tmp_path
):
    value = tools.rank_abnormality_duration(query())
    assert [
        (r["machine_id"], r["rank"], r["reported_minutes"]) for r in value["rankings"]
    ] == [("FX1", 1, 180), ("FX2", 2, 150), ("FX4", 3, 15)]
    assert value["reported_minutes"] == 345 and value["event_count"] == 10
    assert value["missing_minutes_count"] == 2 and value["open_count"] == 3
    assert (
        value["overlap_event_count"] == value["incomplete_time_count"] == 2
        and value["mismatch_count"] == 1
    )
    assert value["rankings"][1]["partial"] is True
    unknown = {r["machine_id"]: r for r in value["unranked"]}
    assert (
        unknown["FX5"]["reason"] == "missing_duration"
        and unknown["FX8"]["reason"] == "no_records"
    )
    overnight = tools.rank_abnormality_duration(
        query(start_date="2026-01-06", machine_id="FX1")
    )
    assert overnight["reported_minutes"] == 60
    b = tmp_path / "b.db"
    build(b, "B")
    other = ResearchTools(DataSource(b, "synthetic")).rank_abnormality_duration(query())
    assert (
        other["rankings"][0]["machine_id"] == "FX2" and other["reported_minutes"] == 495
    )


def test_ties_and_zero_are_distinct_from_absence(tools):
    value = tools.rank_abnormality_duration(query(end_date="2026-01-05"))
    assert [r["rank"] for r in value["rankings"]] == [1, 1, 3]
    zero = tools.rank_abnormality_duration(
        query(
            start_date="2026-01-06",
            end_date="2026-01-06",
            machine_id="FX4",
            shift="Night",
        )
    )
    assert zero["reported_minutes"] == 0 and zero["rankings"][0]["rank"] == 1
    empty = tools.compare_production_inputs(
        query(start_date="2026-01-08", end_date="2026-01-08")
    )
    assert empty["actual_inputs"] is None and empty["shortfall"] is None
    empty_b = tools.rank_abnormality_duration(
        query(start_date="2026-01-08", end_date="2026-01-08")
    )
    assert empty_b["rankings"] == [] and empty_b["reported_minutes"] is None


@pytest.mark.parametrize(
    "changes",
    [
        {"start_date": "2026-02-30"},
        {"end_date": "2026-01-04"},
        {"end_date": "2026-03-01"},
        {"start_date": 123},
        {"machine_id": ""},
        {"shift": "guess"},
        {"sql": "DELETE FROM x"},
    ],
)
def test_strict_filter_validation(changes):
    with pytest.raises(ValueError):
        query(**changes)


def test_unknown_machine_and_generated_sql_are_rejected(tools):
    with pytest.raises(ValueError):
        tools.invoke(TOOL_A, query(machine_id="FX1';DROP TABLE x").model_dump())
    with pytest.raises(ValueError):
        tools.invoke("execute_sql", {})


def test_readonly_connections_prevent_writes_and_source_marker(tools, tmp_path):
    from ai_production_data import _readonly_connection

    with _readonly_connection(tools.source.path) as connection:
        with pytest.raises(sqlite3.OperationalError):
            connection.execute("DELETE FROM slitting_records")
    with pytest.raises(ValueError):
        DataSource(tools.source.path, "real")
    with pytest.raises(ValueError):
        DataSource(tmp_path / "missing.db", "synthetic")
    with pytest.raises(ValueError):
        build(tools.source.path)


def test_partial_known_minutes_do_not_infer_from_available_timestamps(tools):
    result = tools.rank_abnormality_duration(
        query(start_date="2026-01-06", machine_id="FX2")
    )
    assert (
        result["reported_minutes"] == 30
    )  # E6 has timestamps, but unknown source minutes.
    assert result["missing_minutes_count"] == 1


def test_fail_closed_on_null_production_counts(tmp_path):
    p = tmp_path / "broken.db"
    with closing(sqlite3.connect(p)) as db:
        db.execute(
            "CREATE TABLE slitting_records(production_date,shift,machine_id,product,planned_rolls,input_rolls,qualified_rolls,actual_output_m2,qualified_output_m2,reported_yield_pct)"
        )
        db.execute(
            "INSERT INTO slitting_records VALUES ('2026-01-05','Day','FX1','X',NULL,8,1,10,5,NULL)"
        )
        db.commit()
    service = ResearchTools(DataSource(p, "real"))
    with pytest.raises(ValueError, match="malformed"):
        service.compare_production_inputs(query())
