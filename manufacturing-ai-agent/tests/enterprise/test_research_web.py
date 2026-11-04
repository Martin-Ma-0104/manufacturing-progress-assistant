"""Web adapters must agree with the frozen tools without model calls or writes."""

from contextlib import closing
import sqlite3
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.research import InputComparison, AbnormalityRanking
from research.harry_milestone.contracts import Query
from research.harry_milestone.fixtures import build
from research.harry_milestone.tools import DataSource, ResearchTools


@pytest.fixture()
def reviewed(tmp_path, monkeypatch):
    path = tmp_path / "reviewed.db"
    build(path)
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("DROP TABLE research_fixture")
        connection.commit()
    monkeypatch.setenv("PRODUCTION_DB", str(path))
    before = path.read_bytes()
    with TestClient(app) as client, patch("openai.AsyncOpenAI") as model:
        yield client, path
        model.assert_not_called()
    assert path.read_bytes() == before


def args(**changes):
    return (
        dict(start="2026-01-05", end="2026-01-07", shift="All", source="reviewed")
        | changes
    )


@pytest.mark.parametrize(
    "extra",
    [
        {},
        dict(machine="FX1"),
        dict(machine="FX2", shift="Day"),
        dict(machine="FX4", shift="Night"),
        dict(start="2026-01-08", end="2026-01-08"),
        dict(machine="FX8", start="2026-01-07", end="2026-01-07"),
    ],
)
def test_web_result_matches_both_frozen_tools_for_exact_filters(reviewed, extra):
    client, path = reviewed
    params = args(**extra)
    response = client.get("/api/research/analysis", params=params)
    assert response.status_code == 200, response.text
    result = response.json()
    query = Query(
        start_date=params["start"],
        end_date=params["end"],
        machine_id=params.get("machine"),
        shift=params["shift"],
    )
    tools = ResearchTools(DataSource(path, "real"))
    assert result["comparison"] == InputComparison.model_validate(
        tools.compare_production_inputs(query)
    ).model_dump(mode="json")
    assert result["abnormalities"] == AbnormalityRanking.model_validate(
        tools.rank_abnormality_duration(query)
    ).model_dump(mode="json")
    assert (
        result["model_requests"] == 0 and result["mode"] == "deterministic_tools_only"
    )
    assert (
        "source_name" not in response.text
        and "notes" not in response.text
        and str(path) not in response.text
    )


def test_one_transaction_snapshot_prevents_cross_tool_fanout_and_preserves_known_subtotals(
    reviewed,
):
    client, _ = reviewed
    original = ResearchTools.snapshot
    with patch.object(
        ResearchTools, "snapshot", autospec=True, side_effect=original
    ) as snapshot:
        value = client.get("/api/research/analysis", params=args()).json()
        assert snapshot.call_count == 1
    assert (
        value["comparison"]["planned_inputs"] == 70
        and value["comparison"]["shortfall"] == 18
    )
    assert value["abnormalities"]["reported_minutes"] == 345
    assert (
        value["abnormalities"]["overlap_event_count"] == 2
        and value["abnormalities"]["missing_minutes_count"] == 2
    )
    assert value["abnormalities"]["rankings"][1]["partial"] is True


@pytest.mark.parametrize(
    "params",
    [
        {},
        dict(start="2026-01-05"),
        args(start="2026-01-08", end="2026-01-05"),
        args(end="2026-02-20"),
        args(shift="guess"),
        args(product="SYN-A"),
        args(machine="FX1';DROP TABLE x"),
        args(source="demo"),
        args(sql="DELETE FROM slitting_records"),
    ],
)
def test_web_rejects_missing_or_unsupported_scope_instead_of_ignoring_filters(
    reviewed, params
):
    client, _ = reviewed
    assert client.get("/api/research/analysis", params=params).status_code == 422


def test_missing_database_is_not_created(tmp_path, monkeypatch):
    path = tmp_path / "absent.db"
    monkeypatch.setenv("PRODUCTION_DB", str(path))
    with TestClient(app) as client:
        assert client.get("/api/research/analysis", params=args()).status_code == 503
    assert not path.exists()


def test_no_write_method_is_exposed(reviewed):
    client, _ = reviewed
    assert (
        client.post(
            "/api/research/analysis",
            headers={"X-Local-Client": "manufacturing-web"},
            json=args(),
        ).status_code
        == 405
    )
