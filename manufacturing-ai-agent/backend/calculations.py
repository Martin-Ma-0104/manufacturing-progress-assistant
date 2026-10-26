"""Scenario arithmetic only: no measured factory capacity or optimal scheduling claims."""

import math
from .models import CapacityInput, ScenarioInput


def calculate_capacity(value: CapacityInput) -> dict:
    effective = value.available_minutes - value.downtime_minutes
    theoretical = (
        math.floor(value.available_minutes / value.cycle_minutes) * value.machines
    )
    cycles = math.floor(effective / value.cycle_minutes) * value.machines
    gross = cycles * value.units_per_cycle
    qualified = gross * value.expected_yield
    no_downtime = theoretical * value.units_per_cycle * value.expected_yield
    return dict(
        theoretical_cycles=theoretical,
        effective_minutes_per_machine=effective,
        effective_machine_minutes=effective * value.machines,
        estimated_cycles=cycles,
        gross_output=gross,
        estimated_qualified_output=qualified,
        output_unit=value.output_unit,
        estimated_output_difference_from_no_downtime=no_downtime - qualified,
        scenario_capacity_fraction=cycles / theoretical if theoretical else None,
        assumptions=[
            "Scenario, not measured production capacity. All machines use identical stated inputs.",
            "Available time and downtime are PER MACHINE; completed cycles are floored per machine.",
            "Yield is a user-supplied fraction. Unknown source-report yield is never substituted.",
            "Only stated downtime is deducted. Recorded abnormality minutes are not automatically treated as downtime.",
        ],
        inputs=value.model_dump(),
    )


def forecast_production(value: CapacityInput) -> dict:
    return calculate_capacity(value)


def compare_scenarios(value: ScenarioInput) -> dict:
    a, b = calculate_capacity(value.baseline), calculate_capacity(value.alternative)
    return dict(
        baseline=a,
        alternative=b,
        output_change=b["estimated_qualified_output"] - a["estimated_qualified_output"],
        output_unit=a["output_unit"],
        globally_optimal=False,
    )


def analyze_downtime(events, machine_id=None, start=None, end=None):
    """Aggregate reported event minutes; never relabel them as net downtime.

    Dates are inclusive business production dates. Absolute overlap and missing
    time diagnostics come from the established abnormality module.
    """
    import abnormality

    selected = [
        event
        for event in events
        if (machine_id is None or event["machine_id"] == machine_id)
        and (start is None or event["production_date"] >= start)
        and (end is None or event["production_date"] <= end)
    ]
    categories = abnormality.grouped(selected, "category")
    categories.sort(key=lambda item: -(item["reported_minutes"] or 0))
    summary = abnormality.summarize(selected)
    minutes = summary["reported_minutes"]
    running = 0
    for item in categories:
        value = item["reported_minutes"]
        item["fraction"] = value / minutes if value is not None and minutes else None
        running += value or 0
        item["cumulative_fraction"] = running / minutes if minutes else None
    return dict(**summary, categories=categories)
