"""Local FastAPI facade over the existing shared Python layer."""

import logging
import os
from typing import Annotated
from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from .models import (
    Scope,
    CapacityInput,
    ScenarioInput,
    ChatInput,
    ChatResponse,
    SearchInput,
    SummaryResponse,
    CapacityResult,
    ScenarioResult,
    HealthResponse,
    OptionsResponse,
    RecordsResponse,
    MachinesResponse,
    DocumentsResponse,
    IndexResponse,
    SearchResponse,
    InventoryResponse,
    DowntimeResponse,
)
from . import data, knowledge
from .calculations import calculate_capacity, forecast_production, compare_scenarios
from .agent import answer

app = FastAPI(
    title="Manufacturing Operations API",
    version="0.1.0",
    description="Local development only. Historical reviewed records and isolated demonstrations. No authentication or live equipment integration yet.",
)
origins = [
    s.strip()
    for s in os.getenv(
        "ALLOWED_ORIGINS", "http://127.0.0.1:3000,http://localhost:3000"
    ).split(",")
    if s.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Local-Client"],
    allow_credentials=False,
)
app.add_middleware(
    TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"]
)
logger = logging.getLogger("manufacturing.api")


@app.middleware("http")
async def request_boundary(request: Request, call_next):
    if request.method == "POST":
        if request.headers.get("origin") and request.headers["origin"] not in origins:
            return JSONResponse({"detail": "Origin not allowed."}, 403)
        if request.headers.get("x-local-client") != "manufacturing-web":
            return JSONResponse({"detail": "Local client header required."}, 403)
        try:
            if int(request.headers.get("content-length", "0")) > 6 * 1024 * 1024:
                return JSONResponse({"detail": "Request too large."}, 413)
        except ValueError:
            return JSONResponse({"detail": "Invalid request length."}, 400)
    try:
        response = await call_next(request)
    except Exception as exc:
        logger.error("request_failed type=%s", type(exc).__name__)
        return JSONResponse(
            {
                "detail": "Request failed. Check local configuration; no internal trace is returned."
            },
            500,
        )
    logger.info("request method=%s status=%d", request.method, response.status_code)
    return response


def safe(fn, *args, **kw):
    try:
        return fn(*args, **kw)
    except ValueError as e:
        raise HTTPException(422, str(e)) from None


@app.get("/api/health", response_model=HealthResponse)
def health():
    return dict(
        status="ok",
        version="0.1.0",
        production_db_available=data.db_path().is_file(),
        llm_configured=bool(os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")),
        embedding_provider=knowledge.provider(),
        authentication="not_implemented_local_only",
        live_machines=False,
    )


@app.get("/api/production/options", response_model=OptionsResponse)
def options(source: str = "reviewed"):
    if source not in ("reviewed", "demo"):
        raise HTTPException(422, "Invalid source.")
    return data.options(source)


@app.get("/api/dashboard/summary", response_model=SummaryResponse)
def summary(scope: Annotated[Scope, Query()]):
    return safe(data.dashboard, scope)


@app.get("/api/production", response_model=RecordsResponse)
def production(scope: Annotated[Scope, Query()]):
    return dict(records=safe(data.dashboard, scope)["records"], source=scope.source)


@app.get("/api/production/machines", response_model=MachinesResponse)
def machines(scope: Annotated[Scope, Query()]):
    return dict(machines=safe(data.dashboard, scope)["machines"], source=scope.source)


@app.get("/api/production/machines/{machine_id}", response_model=SummaryResponse)
def machine(machine_id: str, scope: Annotated[Scope, Query()]):
    return safe(data.dashboard, scope.model_copy(update={"machine": machine_id}))


@app.get("/api/production/downtime", response_model=DowntimeResponse)
def downtime(scope: Annotated[Scope, Query()]):
    return dict(
        **safe(data.dashboard, scope)["abnormalities"],
        unit="recorded event-minutes, not net downtime",
    )


@app.post("/api/production/capacity", response_model=CapacityResult)
def capacity(value: CapacityInput):
    return calculate_capacity(value)


@app.post("/api/production/forecast", response_model=CapacityResult)
def forecast(value: CapacityInput):
    return forecast_production(value)


@app.post("/api/planning/compare", response_model=ScenarioResult)
def compare(value: ScenarioInput):
    return compare_scenarios(value)


@app.get("/api/inventory", response_model=InventoryResponse)
def inventory(planned_quantity: float = Query(default=0, ge=0, le=1000000)):
    return dict(
        source="synthetic_demo",
        warning="SYNTHETIC planning example; ERP/MES inventory is not connected.",
        items=[
            dict(
                material_id="DEMO-RESIN",
                name="Demo resin",
                category="Raw material",
                on_hand=1200,
                reserved=200,
                available=1000,
                safety_stock=250,
                unit="kg",
                usage_per_finished_roll=0.5,
                estimated_consumption_kg=planned_quantity * 0.5,
                shortage_kg=max(planned_quantity * 0.5 - 1000, 0),
                coverage_finished_roll_equivalent=2000,
                below_demo_safety_stock=False,
            )
        ],
    )


@app.get("/api/knowledge/documents", response_model=DocumentsResponse)
def list_documents():
    return dict(
        documents=knowledge.documents(),
        provider=knowledge.provider(),
        external_by_default=False,
    )


@app.post("/api/knowledge/documents", response_model=IndexResponse)
async def upload(
    file: UploadFile = File(...),
    category: str = Form("Production SOP"),
    allow_external: bool = Form(False),
):
    content = await file.read(5 * 1024 * 1024 + 1)
    try:
        return knowledge.ingest(file.filename or "", content, category, allow_external)
    except ValueError as e:
        raise HTTPException(422, str(e)) from None
    except Exception:
        raise HTTPException(
            422,
            "Document could not be extracted/indexed. Use an unencrypted text-based supported file.",
        ) from None
    finally:
        await file.close()


@app.post(
    "/api/knowledge/documents/{document_id}/reindex", response_model=IndexResponse
)
def reindex(document_id: str, allow_external: bool = False):
    return safe(knowledge.reindex, document_id, allow_external)


@app.post("/api/knowledge/search", response_model=SearchResponse)
def search(value: SearchInput):
    return dict(
        sources=safe(
            knowledge.search,
            value.question,
            value.document_ids,
            value.limit,
            value.allow_external,
        )
    )


@app.post("/api/agent/chat", response_model=ChatResponse)
async def chat(value: ChatInput):
    try:
        return await answer(value)
    except ValueError as e:
        raise HTTPException(422, str(e)) from None
    except Exception:
        raise HTTPException(
            502,
            "Assistant unavailable. Local calculations and production views remain available; no automatic retry.",
        ) from None


@app.get("/api/reports/selection.html")
def selection_html(scope: Annotated[Scope, Query()]):
    from fastapi.responses import HTMLResponse
    from production_report import render_report

    result = safe(data.dashboard, scope)
    title = (
        ("SYNTHETIC DEMO - " if scope.source == "demo" else "Reviewed history - ")
        + result["scope"]["start"]
        + " to "
        + result["scope"]["end"]
    )
    return HTMLResponse(
        render_report(
            result["records"],
            title,
            None if scope.shift == "All" else scope.shift,
            scope.machine,
        ),
        headers={
            "Content-Disposition": 'attachment; filename="production-selection.html"'
        },
    )


@app.get("/api/reports/selection.pdf")
def selection_pdf(scope: Annotated[Scope, Query()]):
    from fastapi.responses import Response
    from .reports import selection_pdf as render_selection_pdf

    result = safe(data.dashboard, scope)
    return Response(
        render_selection_pdf(result),
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="production-selection.pdf"'
        },
    )
