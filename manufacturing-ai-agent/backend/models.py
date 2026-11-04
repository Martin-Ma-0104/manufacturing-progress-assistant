from datetime import date
from typing import Literal, Any
from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Scope(Strict):
    start: date | None = None
    end: date | None = None
    machine: str | None = Field(default=None, max_length=128)
    product: str | None = Field(default=None, max_length=256)
    shift: Literal["All", "Day", "Night"] = "All"
    source: Literal["reviewed"] = "reviewed"

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


class RuntimeTotals(Strict):
    status: Literal["estimated", "unavailable"]
    observed_shift_count: int = Field(ge=0)
    possible_shift_count: int = Field(ge=0)
    unrecorded_shift_count: int = Field(ge=0)
    invalid_event_count: int = Field(ge=0)
    no_recorded_stop_shift_count: int = Field(ge=0)
    available_minutes: float | None = Field(ge=0)
    merged_stop_minutes: float | None = Field(ge=0)
    runtime_lower_minutes: float | None = Field(ge=0)
    runtime_upper_minutes: float | None = Field(ge=0)
    utilization_lower: float | None = Field(ge=0, le=1)
    utilization_upper: float | None = Field(ge=0, le=1)
    reason: str | None

    @model_validator(mode="after")
    def bounds(self):
        if (
            self.possible_shift_count
            != self.observed_shift_count + self.unrecorded_shift_count
        ):
            raise ValueError("Runtime estimate coverage does not reconcile")
        if self.status == "estimated":
            if self.available_minutes is None or self.available_minutes <= 0:
                raise ValueError("Runtime estimate needs a positive denominator")
            if self.runtime_lower_minutes is None or self.runtime_upper_minutes is None:
                raise ValueError("Runtime bounds are missing")
            if (
                not 0
                <= self.runtime_lower_minutes
                <= self.runtime_upper_minutes
                <= self.available_minutes
            ):
                raise ValueError("Runtime bounds are inconsistent")
            if (
                self.utilization_lower is None
                or self.utilization_upper is None
                or self.utilization_lower > self.utilization_upper
            ):
                raise ValueError("Utilization bounds are inconsistent")
        elif any(
            value is not None
            for value in (
                self.runtime_lower_minutes,
                self.runtime_upper_minutes,
                self.utilization_lower,
                self.utilization_upper,
            )
        ):
            raise ValueError("Unavailable runtime must not contain inferred values")
        return self


class RuntimeMachine(RuntimeTotals):
    machine_id: str


class RuntimeEstimate(RuntimeTotals):
    source: Literal["reviewed", "demo"]
    basis: Literal["12h-shift-2h-flexible-break-all-events-stop-v1"]
    shift_minutes: Literal[720]
    break_minutes: Literal[120]
    available_minutes_per_shift: Literal[600]
    assumptions: list[str]
    per_machine: list[RuntimeMachine]


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
    runtime_estimate: RuntimeEstimate


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


class ProductionEntry(Strict):
    source: Literal["reviewed"] = "reviewed"
    confirmed_real: bool = Field(strict=True)
    production_date: date
    shift: Literal["Day", "Night"]
    machine_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
    product: str = Field(min_length=1, max_length=256)
    planned_rolls: int = Field(strict=True, ge=0, le=2147483647)
    input_rolls: int = Field(strict=True, ge=0, le=2147483647)
    qualified_rolls: int = Field(strict=True, ge=0, le=2147483647)
    actual_output_m2: float = Field(strict=True, ge=0, le=1e12)
    qualified_output_m2: float = Field(strict=True, ge=0, le=1e12)
    reported_yield_pct: float | None = Field(default=None, strict=True, ge=0, le=100)
    source_report_date: date
    source_shift_label: str = Field(min_length=1, max_length=128)
    source_name: str = Field(min_length=1, max_length=256)
    notes: str = Field(default="", max_length=4000)

    @field_validator("production_date", "source_report_date", mode="before")
    @classmethod
    def entry_dates(cls, value):
        if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
            raise ValueError("Use a calendar date in YYYY-MM-DD format.")
        return value

    @model_validator(mode="after")
    def reviewed_record(self):
        if not self.confirmed_real:
            raise ValueError(
                "Confirm that these are verified actual production values before saving."
            )
        for field in ("product", "source_shift_label", "source_name"):
            value = getattr(self, field).strip()
            if not value:
                raise ValueError(f"{field} must not be blank.")
            setattr(self, field, value)
        if self.machine_id.upper().startswith(("DEMO-", "SYNTHETIC")):
            raise ValueError("Synthetic machines cannot be saved through this website.")
        if self.qualified_output_m2 > self.actual_output_m2:
            raise ValueError("Qualified area cannot exceed actual output area.")
        return self


class ProductionEntryResult(Strict):
    status: Literal["saved", "unchanged"]
    added: Literal[0, 1]
    production_date: str
    machine_id: str
    shift: Literal["Day", "Night"]
    product: str
    source: Literal["reviewed"]


class QualityGroup(Strict):
    label: str
    detail_count: int = Field(ge=0)
    rejected_area_m2: str = Field(pattern=r"^\d+(?:\.\d{1,6})?$")


class QualitySummary(Strict):
    source: Literal["reviewed"]
    unit: Literal["m2"]
    status: Literal["recorded", "no_records", "not_imported"]
    scope: Scope
    detail_count: int = Field(ge=0)
    machine_count: int = Field(ge=0)
    rejected_area_m2: str | None
    by_machine: list[QualityGroup]
    by_reason: list[QualityGroup]
    daily: list[QualityGroup]
    recorded_dates: list[str]
    missing_dates: list[str]
    recorded_shifts: list[Literal["Day", "Night"]]
    matched_production_group_count: int = Field(ge=0)
    unmatched_production_group_count: int = Field(ge=0)


class QualityDetail(Strict):
    production_date: str
    shift: Literal["Day", "Night"]
    machine_id: str
    product: str
    product_id: str
    station: str
    specification: str
    rejected_area_m2: str
    ccd_defect: str
    appearance_defect: str
    remarks: str
    coating_barcode: str
    coating_machine: str


class QualityRecords(Strict):
    scope: Scope
    unit: Literal["m2"]
    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    limit: int = Field(ge=1, le=200)
    records: list[QualityDetail]


class QualityPageScope(Scope):
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=100, ge=1, le=200)
