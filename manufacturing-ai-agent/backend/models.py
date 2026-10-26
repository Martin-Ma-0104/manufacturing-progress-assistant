from datetime import date
from typing import Literal, Any
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Scope(Strict):
    start: date | None = None
    end: date | None = None
    machine: str | None = Field(default=None, max_length=128)
    product: str | None = Field(default=None, max_length=256)
    shift: Literal["All", "Day", "Night"] = "All"
    source: Literal["reviewed", "demo"] = "reviewed"

    @model_validator(mode="after")
    def dates(self):
        if self.start and self.end and not 0 <= (self.end - self.start).days < 30:
            raise ValueError("Select an ordered range of at most 30 calendar dates.")
        return self


class CapacityInput(Strict):
    available_minutes: float = Field(ge=0, le=525600)
    cycle_minutes: float = Field(gt=0, le=525600)
    machines: int = Field(default=1, ge=1, le=1000)
    downtime_minutes: float = Field(default=0, ge=0, le=525600)
    units_per_cycle: float = Field(default=1, gt=0, le=1000000)
    output_unit: Literal["cycles", "finished_rolls", "m2"] = "cycles"
    expected_yield: float = Field(default=1, ge=0, le=1)

    @model_validator(mode="after")
    def time_budget(self):
        if self.downtime_minutes > self.available_minutes:
            raise ValueError("Downtime cannot exceed available minutes per machine.")
        if self.output_unit == "cycles" and self.units_per_cycle != 1:
            raise ValueError(
                "Cycles use one cycle unit per completed cycle; select finished_rolls or m2 for a converted output."
            )
        return self


class ScenarioInput(Strict):
    baseline: CapacityInput
    alternative: CapacityInput

    @model_validator(mode="after")
    def units(self):
        if self.baseline.output_unit != self.alternative.output_unit:
            raise ValueError("Scenario output units must match.")
        return self


class ChatInput(Strict):
    message: str = Field(min_length=1, max_length=1000)
    scope: Scope = Field(default_factory=Scope)
    capacity: CapacityInput | None = None
    use_llm: bool = False
    allow_external: bool = False
    document_ids: list[str] = Field(default_factory=list, max_length=20)


class SearchInput(Strict):
    question: str = Field(min_length=2, max_length=1000)
    document_ids: list[str] = Field(default_factory=list, max_length=20)
    limit: int = Field(default=4, ge=1, le=8)
    allow_external: bool = False


class SummaryResponse(Strict):
    source: str
    scope: dict[str, Any]
    summary: dict[str, Any]
    daily: list[dict[str, Any]]
    machines: list[dict[str, Any]]
    abnormalities: dict[str, Any]
    records: list[dict[str, Any]]
    changeovers: list[dict[str, Any]]
    warnings: list[str]
    last_recorded_date: str | None


class ChatResponse(Strict):
    mode: str
    summary: str
    verified_data: dict[str, Any] = Field(default_factory=dict)
    calculations: dict[str, Any] = Field(default_factory=dict)
    potential_causes: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)


class CapacityResult(Strict):
    theoretical_cycles: int
    effective_minutes_per_machine: float
    effective_machine_minutes: float
    estimated_cycles: int
    gross_output: float
    estimated_qualified_output: float
    output_unit: str
    estimated_output_difference_from_no_downtime: float
    scenario_capacity_fraction: float | None
    assumptions: list[str]
    inputs: CapacityInput


class ScenarioResult(Strict):
    baseline: CapacityResult
    alternative: CapacityResult
    output_change: float
    output_unit: str
    globally_optimal: bool


class HealthResponse(Strict):
    status: str
    version: str
    production_db_available: bool
    llm_configured: bool
    embedding_provider: str
    authentication: str
    live_machines: bool


class OptionsResponse(Strict):
    dates: list[str]
    machines: list[str]
    products: list[str]


class RecordsResponse(Strict):
    records: list[dict[str, Any]]
    source: str


class MachinesResponse(Strict):
    machines: list[dict[str, Any]]
    source: str


class DocumentsResponse(Strict):
    documents: list[dict[str, Any]]
    provider: str
    external_by_default: bool


class IndexResponse(Strict):
    id: str
    duplicate: bool = False
    chunks: int | None = None
    provider: str | None = None
    reindexed: bool = False


class SearchResponse(Strict):
    sources: list[dict[str, Any]]


class InventoryResponse(Strict):
    source: str
    warning: str
    items: list[dict[str, Any]]


class DowntimeResponse(Strict):
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
    categories: list[dict[str, Any]]
    unit: str
