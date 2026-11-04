from datetime import date
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MODEL = "gpt-6-sol"
AS_OF = "2026-01-12"
TIMEZONE = "America/New_York"
TOOL_A = "compare_production_inputs"
TOOL_B = "rank_abnormality_duration"


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Query(Strict):
    start_date: str
    end_date: str
    machine_id: str | None = Field(default=None, max_length=128)
    shift: Literal["All", "Day", "Night"] = "All"

    @field_validator("start_date", "end_date")
    @classmethod
    def calendar_date(cls, value):
        if date.fromisoformat(value).isoformat() != value:
            raise ValueError("Use YYYY-MM-DD calendar dates.")
        return value

    @model_validator(mode="after")
    def valid_scope(self):
        if (
            not 0
            <= (
                date.fromisoformat(self.end_date) - date.fromisoformat(self.start_date)
            ).days
            < 30
        ):
            raise ValueError("Select an inclusive range of at most 30 calendar dates.")
        if self.machine_id is not None and (
            not self.machine_id or self.machine_id.strip() != self.machine_id
        ):
            raise ValueError("Machine must be a known nonempty identifier, or null.")
        return self


class Clarification(Strict):
    reason: Literal["ambiguous", "unsupported"]
    target: Literal[
        "date_range",
        "production_unit",
        "machine_id",
        "scope",
        "unsupported_metric",
        "unsupported_task",
    ]


class Explanation(Strict):
    # Selection of locally worded evidence, not unrestricted model-authored claims.
    fact_ids: list[str] = Field(min_length=1, max_length=8)
