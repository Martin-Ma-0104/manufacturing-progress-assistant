"""Local web adapter over the frozen, read-only research tools. No model calls."""

from datetime import date
from typing import Annotated, Literal
import sqlite3
from fastapi import APIRouter, HTTPException, Query as WebQuery
from pydantic import model_validator
from .models import Scope, Strict
from .data import db_path
from research.harry_milestone.contracts import Query
from research.harry_milestone.tools import DataSource, ResearchTools, evidence


class ResearchScope(Scope):
    start: date
    end: date

    @model_validator(mode="after")
    def supported_filters(self):
        if self.product:
            raise ValueError(
                "Research analysis supports date, machine and shift. Clear the product filter first."
            )
        return self


class InputTotals(Strict):
    planned_inputs: int | None
    actual_inputs: int | None
    difference: int | None
    shortfall: int | None
    net_shortfall: int | None
    excess: int | None
    record_count: int


class InputMachine(InputTotals):
    machine_id: str


class InputComparison(InputTotals):
    tool: Literal["compare_production_inputs"]
    origin: Literal["real"]
    scope: Query
    unit: Literal["input mother rolls"]
    by_machine: list[InputMachine]
    recorded_dates: list[str]
    missing_dates: list[str]
    warnings: list[str]


class EventStatistics(Strict):
    event_count: int
    reported_minutes: float | None
    valid_minutes_count: int
    missing_minutes_count: int
    open_count: int
    unknown_status_count: int
    unknown_shift_count: int
    incomplete_time_count: int
    mismatch_count: int
    overlap_event_count: int


class RankedMachine(EventStatistics):
    machine_id: str
    partial: bool
    rank: int | None
    reason: Literal["missing_duration", "no_records"] | None = None


class AbnormalityRanking(EventStatistics):
    tool: Literal["rank_abnormality_duration"]
    origin: Literal["real"]
    scope: Query
    unit: Literal["recorded event-minutes"]
    rankings: list[RankedMachine]
    unranked: list[RankedMachine]
    warnings: list[str]


class ResearchAnalysis(Strict):
    mode: Literal["deterministic_tools_only"]
    model_requests: Literal[0]
    comparison: InputComparison
    abnormalities: AbnormalityRanking
    input_explanation: list[str]
    abnormality_explanation: list[str]


class RequestTools(ResearchTools):
    """Both tool outputs use one existing transaction-consistent snapshot."""

    def __init__(self, source, query):
        super().__init__(source)
        self.query = query
        self.captured = super().snapshot(query)

    def snapshot(self, query):
        if query != self.query:
            raise ValueError("Research snapshot scope does not match this request.")
        return self.captured


def analyze(scope: ResearchScope):
    path = db_path()
    if not path.is_file():
        raise HTTPException(
            503, "Reviewed database is not available. No database was created."
        )
    query = Query(
        start_date=scope.start.isoformat(),
        end_date=scope.end.isoformat(),
        machine_id=scope.machine,
        shift=scope.shift,
    )
    try:
        service = RequestTools(DataSource(path, "real"), query)
        comparison = service.compare_production_inputs(query)
        abnormalities = service.rank_abnormality_duration(query)
        return dict(
            mode="deterministic_tools_only",
            model_requests=0,
            comparison=comparison,
            abnormalities=abnormalities,
            input_explanation=list(evidence(comparison).values()),
            abnormality_explanation=list(evidence(abnormalities).values()),
        )
    except ValueError as error:
        raise HTTPException(422, str(error)) from None
    except sqlite3.Error:
        raise HTTPException(
            503, "Reviewed records could not be read. Check the local database."
        ) from None


router = APIRouter(prefix="/api/research", tags=["Read-only research analysis"])


@router.get("/analysis", response_model=ResearchAnalysis)
def analysis(scope: Annotated[ResearchScope, WebQuery()]):
    return analyze(scope)
