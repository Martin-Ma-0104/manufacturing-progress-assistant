import io
import sqlite3
from types import SimpleNamespace
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.models import CapacityInput, ChatInput
from backend.calculations import calculate_capacity
from backend import knowledge
from production import import_records

HEADERS = {"X-Local-Client": "manufacturing-web"}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db = tmp_path / "reviewed.db"
    monkeypatch.setenv("PRODUCTION_DB", str(db))
    monkeypatch.setenv("KNOWLEDGE_DIR", str(tmp_path / "knowledge"))
    monkeypatch.setenv("EMBEDDING_PROVIDER", "local-hash-v1")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    rows = [
        dict(
            production_date="2026-10-17",
            shift="Day",
            machine_id="FX8",
            product="TEST-SPEC",
            planned_rolls=10,
            input_rolls=8,
            qualified_rolls=20,
            actual_output_m2=100.0,
            qualified_output_m2=80.0,
            reported_yield_pct=None,
            source_report_date="2026-10-17",
            source_shift_label="Day",
            source_name="PRIVATE.png",
            notes="PRIVATE note",
        )
    ]
    with sqlite3.connect(db) as con:
        import_records(rows, con)
    before = db.read_bytes()
    with TestClient(app) as c:
        yield c
    assert db.read_bytes() == before


def test_no_key_health_and_readonly_data(client):
    assert client.get("/api/health").json()["llm_configured"] is False
    data = client.get("/api/dashboard/summary").json()
    assert data["summary"]["attainment"] == "80.0%"
    assert data["summary"]["average_cycle_minutes"] is None
    assert "FX8" in [m["machine_id"] for m in data["machines"]]
    assert (
        next(m for m in data["machines"] if m["machine_id"] == "FX3")["input_rolls"]
        is None
    )
    assert "PRIVATE" not in str(data)


@pytest.mark.parametrize(
    "params",
    [
        {"start": "2026-10-20", "end": "2026-10-01"},
        {"start": "2026-01-01", "end": "2026-10-18"},
        {"shift": "guess"},
        {"machine": "FX1';DROP TABLE x"},
        {"product": "unknown"},
    ],
)
def test_invalid_filters(client, params):
    assert client.get("/api/dashboard/summary", params=params).status_code == 422


def test_missing_single_shift_and_demo_are_distinct(client):
    real = client.get("/api/dashboard/summary", params={"shift": "Night"}).json()
    assert real["summary"]["input_rolls"] is None and real["records"] == []
    demo = client.get("/api/dashboard/summary", params={"source": "demo"}).json()
    assert demo["source"] == "demo" and all(
        r["product"].startswith("SYNTHETIC") for r in demo["records"]
    )
    assert "SYNTHETIC" in demo["warnings"][0]


def test_capacity_rounding_yield_and_units(client):
    value = CapacityInput(
        available_minutes=480,
        cycle_minutes=30,
        machines=2,
        downtime_minutes=120,
        units_per_cycle=10,
        output_unit="finished_rolls",
        expected_yield=0.9,
    )
    result = calculate_capacity(value)
    assert (
        result["estimated_cycles"] == 24 and result["estimated_qualified_output"] == 216
    )
    assert result["estimated_output_difference_from_no_downtime"] == 72
    assert (
        calculate_capacity(CapacityInput(available_minutes=0, cycle_minutes=10))[
            "scenario_capacity_fraction"
        ]
        is None
    )
    response = client.post(
        "/api/production/forecast", headers=HEADERS, json=value.model_dump()
    )
    assert response.json() == result


@pytest.mark.parametrize(
    "change",
    [
        {"cycle_minutes": 0},
        {"downtime_minutes": 500},
        {"expected_yield": 1.2},
        {"machines": 0},
        {"available_minutes": -1},
        {"sql": "SELECT"},
    ],
)
def test_capacity_invalid_inputs(client, change):
    assert (
        client.post(
            "/api/production/capacity",
            headers=HEADERS,
            json={"available_minutes": 480, "cycle_minutes": 30, **change},
        ).status_code
        == 422
    )


def test_scenarios(client):
    base = dict(available_minutes=480, cycle_minutes=30, machines=2)
    r = client.post(
        "/api/planning/compare",
        headers=HEADERS,
        json={"baseline": base, "alternative": {**base, "cycle_minutes": 27}},
    ).json()
    assert r["output_change"] == 2 and not r["globally_optimal"]
    bad = client.post(
        "/api/planning/compare",
        headers=HEADERS,
        json={"baseline": base, "alternative": {**base, "output_unit": "m2"}},
    )
    assert bad.status_code == 422


def test_write_origin_and_headers(client):
    payload = {"available_minutes": 480, "cycle_minutes": 30}
    assert client.post("/api/production/capacity", json=payload).status_code == 403
    assert (
        client.post(
            "/api/production/capacity",
            headers={**HEADERS, "Origin": "https://evil.example"},
            json=payload,
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/production/capacity",
            headers={**HEADERS, "Origin": "http://localhost:3000"},
            json=payload,
        ).status_code
        == 200
    )


def test_index_retrieve_citations_reindex_and_duplicates(client):
    text = b"Cleaning checklist evidence requires equipment identifier and reviewer sign-off. Use the approved revision."
    r = client.post(
        "/api/knowledge/documents",
        headers=HEADERS,
        files={"file": ("demo-sop.md", text, "text/markdown")},
    )
    assert r.status_code == 200, r.text
    doc = r.json()["id"]
    assert client.post(
        "/api/knowledge/documents", headers=HEADERS, files={"file": ("same.md", text)}
    ).json()["duplicate"]
    hits = client.post(
        "/api/knowledge/search",
        headers=HEADERS,
        json={"question": "What cleaning evidence requires reviewer sign-off?"},
    ).json()["sources"]
    assert hits and hits[0]["document_id"] == doc and "sign-off" in hits[0]["quote"]
    assert client.post(
        f"/api/knowledge/documents/{doc}/reindex", headers=HEADERS, json={}
    ).json()["reindexed"]
    assert len(client.get("/api/knowledge/documents").json()["documents"]) == 1
    unrelated = client.post(
        "/api/knowledge/search",
        headers=HEADERS,
        json={"question": "interstellar banana quantum entanglement"},
    ).json()["sources"]
    assert unrelated == []
    answer = client.post(
        "/api/agent/chat",
        headers=HEADERS,
        json={"message": "What does the SOP cleaning checklist require?"},
    ).json()
    assert (
        answer["mode"] == "local_retrieval"
        and answer["sources"][0]["document_id"] == doc
    )


@pytest.mark.parametrize(
    "name,body",
    [
        ("malware.exe", b"hello"),
        ("fake.pdf", b"hello"),
        ("empty.txt", b""),
        ("scan.txt", b"\xff\xfe"),
        ("large.txt", b"x" * (5 * 1024 * 1024 + 1)),
    ],
)
def test_bad_uploads(client, name, body):
    assert (
        client.post(
            "/api/knowledge/documents", headers=HEADERS, files={"file": (name, body)}
        ).status_code
        == 422
    )


def test_docx_and_pdf_extraction(client):
    from docx import Document

    doc = Document()
    doc.add_paragraph("Cleaning checklist requires a reviewed inspection record.")
    stream = io.BytesIO()
    doc.save(stream)
    assert (
        client.post(
            "/api/knowledge/documents",
            headers=HEADERS,
            files={"file": ("sample.docx", stream.getvalue())},
        ).status_code
        == 200
    )
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    out = io.BytesIO()
    writer.write(out)
    # A scanned/blank PDF must not be pretended to have OCR text.
    assert (
        client.post(
            "/api/knowledge/documents",
            headers=HEADERS,
            files={"file": ("blank.pdf", out.getvalue())},
        ).status_code
        == 422
    )


def test_external_embeddings_require_explicit_permission(client, monkeypatch):
    monkeypatch.setenv("EMBEDDING_PROVIDER", "openai")
    with pytest.raises(ValueError, match="permission"):
        knowledge.embeddings(["confidential"], False)


def test_chat_tools_no_key_and_no_fake_causes(client):
    r = client.post(
        "/api/agent/chat",
        headers=HEADERS,
        json={"message": "Capacity for 2 machines over 8 hours at CT 27 minutes?"},
    ).json()
    assert r["calculations"]["estimated_cycles"] == 34
    no_input = client.post(
        "/api/agent/chat", headers=HEADERS, json={"message": "capacity at CT 27"}
    ).json()
    assert no_input["mode"] == "clarification"
    proof = client.post(
        "/api/agent/chat", headers=HEADERS, json={"message": "Summarize production"}
    ).json()
    assert proof["verified_data"]["shortfall_mother_rolls"] == 2
    assert "No demonstrated root cause" in proof["potential_causes"][0]


def test_scope_cannot_be_expanded_by_question(client):
    req = {"message": "FX2 production", "scope": {"machine": "FX8"}}
    assert client.post("/api/agent/chat", headers=HEADERS, json=req).status_code == 422
    assert (
        client.post(
            "/api/agent/chat", headers=HEADERS, json={"message": "yesterday production"}
        ).status_code
        == 422
    )


def test_sdk_tool_selection_is_mocked_and_consent_is_enforced(client, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "NOT-A-REAL-KEY")
    with patch("agents.Runner.run") as run:

        async def fake(agent, **kw):
            assert kw["run_config"].tracing_disabled
            assert agent.tool_use_behavior == "stop_on_first_tool"
            assert agent.model_settings.store is False
            assert "PRIVATE" not in kw["input"]
            from agents.tool_context import ToolContext

            context = ToolContext(
                context=None,
                tool_name=agent.tools[0].name,
                tool_call_id="test-call",
                tool_arguments="{}",
                run_config=kw["run_config"],
            )
            output = await agent.tools[0].on_invoke_tool(context, "{}")
            return SimpleNamespace(final_output=output)

        run.side_effect = fake
        denied = client.post(
            "/api/agent/chat",
            headers=HEADERS,
            json={"message": "production", "use_llm": True},
        )
        assert denied.status_code == 422
        run.assert_not_called()
        r = client.post(
            "/api/agent/chat",
            headers=HEADERS,
            json={"message": "production", "use_llm": True, "allow_external": True},
        )
        assert r.status_code == 200, r.text
        assert r.json()["mode"] == "agents_sdk_tool_selection"


def test_optional_fastmcp_shares_tools(client):
    from backend.mcp_server import capacity_scenario

    assert capacity_scenario(480, 30, 2)["estimated_cycles"] == 32


def test_inventory_is_always_labeled_demo(client):
    data = client.get("/api/inventory", params={"planned_quantity": 3000}).json()
    assert data["source"] == "synthetic_demo"
    assert data["items"][0]["shortage_kg"] == 500


def test_zero_denominator_and_filtered_coverage(client, monkeypatch, tmp_path):
    from backend.data import db_path
    import shutil

    copy = tmp_path / "zero-case.db"
    shutil.copyfile(db_path(), copy)
    monkeypatch.setenv("PRODUCTION_DB", str(copy))
    with sqlite3.connect(copy) as db:
        db.execute(
            "UPDATE slitting_records SET planned_rolls=0,input_rolls=0,actual_output_m2=0,qualified_output_m2=0,qualified_rolls=0"
        )
    data = client.get("/api/dashboard/summary", params={"machine": "FX8"}).json()
    assert (
        data["summary"]["attainment"] == "—" and data["summary"]["qualification"] == "—"
    )
    assert data["summary"]["input_rolls"] == 0
    assert any("白班有记录 1 台" in text for text in data["warnings"])


def test_abnormality_analysis_does_not_require_production(client):
    from backend.agent import abnormality_answer

    data = {
        "scope": {},
        "abnormalities": {
            "event_count": 1,
            "reported_minutes": 35,
            "categories": [{"label": "Blade", "reported_minutes": 35}],
        },
        "warnings": ["Partial coverage"],
    }
    with patch("backend.agent.dashboard", return_value=data):
        result = abnormality_answer(ChatInput(message="abnormalities"))
        assert (
            result.verified_data["reported_minutes"] == 35
            and "not deduplicated" in result.summary
        )
    answer = client.post(
        "/api/agent/chat", headers=HEADERS, json={"message": "downtime by reason"}
    ).json()
    assert (
        answer["tools"] == ["analyze_downtime"]
        and answer["verified_data"]["reported_minutes"] is None
    )


def test_complex_capacity_needs_explicit_form(client):
    result = client.post(
        "/api/agent/chat",
        headers=HEADERS,
        json={
            "message": "Capacity for 2 machines 8 hours CT 27 with downtime 2 hours?"
        },
    ).json()
    assert result["mode"] == "clarification"


def test_report_downloads_keep_scope_and_source(client):
    html = client.get("/api/reports/selection.html", params={"machine": "FX8"})
    assert (
        html.status_code == 200
        and "TEST-SPEC" in html.text
        and "PRIVATE" not in html.text
    )
    pdf = client.get("/api/reports/selection.pdf", params={"machine": "FX8"})
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF-")
    from pypdf import PdfReader

    text = " ".join(p.extract_text() for p in PdfReader(io.BytesIO(pdf.content)).pages)
    assert "2026-10-17" in text and "TEST-SPEC" in text and "PRIVATE" not in text
    demo = client.get("/api/reports/selection.pdf", params={"source": "demo"})
    assert (
        "SYNTHETIC DEMONSTRATION"
        in PdfReader(io.BytesIO(demo.content)).pages[0].extract_text()
    )


def test_pdf_text_location_citation(client):
    from reportlab.pdfgen.canvas import Canvas

    stream = io.BytesIO()
    canvas = Canvas(stream)
    canvas.drawString(
        30, 700, "Cleaning evidence requires inspection date and reviewer signoff."
    )
    canvas.save()
    upload = client.post(
        "/api/knowledge/documents",
        headers=HEADERS,
        files={"file": ("demo.pdf", stream.getvalue())},
    )
    assert upload.status_code == 200, upload.text
    answer = client.post(
        "/api/knowledge/search",
        headers=HEADERS,
        json={"question": "Cleaning inspection evidence"},
    ).json()
    assert answer["sources"][0]["location"] == "Page 1"


def test_missing_db_is_not_created(client, monkeypatch, tmp_path):
    path = tmp_path / "does-not-exist.db"
    monkeypatch.setenv("PRODUCTION_DB", str(path))
    result = client.get("/api/dashboard/summary").json()
    assert result["summary"]["input_rolls"] is None and not path.exists()


def test_reported_event_minutes_filter_and_fraction():
    from backend.calculations import analyze_downtime

    def event(machine, reason, minutes):
        return dict(
            event_id=machine + reason,
            production_date="2026-10-17",
            machine_id=machine,
            shift="Day",
            category=reason,
            reported_minutes=minutes,
            started_at=None,
            ended_at=None,
            status="Open",
        )

    result = analyze_downtime(
        [
            event("FX1", "Blade", 30),
            event("FX1", "Quality", 10),
            event("FX2", "Blade", 100),
        ],
        machine_id="FX1",
    )
    assert result["reported_minutes"] == 40 and result["event_count"] == 2
    assert (
        result["categories"][0]["fraction"] == 0.75
        and result["categories"][-1]["cumulative_fraction"] == 1
    )
    assert analyze_downtime([event("FX1", "Blade", None)])["reported_minutes"] is None
    assert (
        analyze_downtime([event("FX1", "Blade", 0)])["categories"][0]["fraction"]
        is None
    )
    assert (
        analyze_downtime([event("FX1", "Blade", 30)], start="2026-10-18")["event_count"]
        == 0
    )


def test_capacity_output_units_are_consistent(client):
    result = client.post(
        "/api/production/capacity",
        headers=HEADERS,
        json={
            "available_minutes": 480,
            "cycle_minutes": 30,
            "units_per_cycle": 10,
            "output_unit": "cycles",
        },
    )
    assert result.status_code == 422
