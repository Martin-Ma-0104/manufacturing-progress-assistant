"""Optional stdio-only FastMCP adapter; same shared logic, no additional agent."""

from mcp.server.fastmcp import FastMCP
from .calculations import calculate_capacity
from .models import CapacityInput, Scope
from .data import dashboard
from .knowledge import search

mcp = FastMCP("Manufacturing read-only tools")


@mcp.tool()
def production_lookup(
    start: str, end: str, machine: str | None = None, shift: str = "All"
) -> dict:
    """Reviewed historical production; up to 30 dates; no writes or arbitrary SQL."""
    result = dashboard(Scope(start=start, end=end, machine=machine, shift=shift))
    return dict(
        summary=result["summary"],
        abnormalities=result["abnormalities"],
        warnings=result["warnings"],
    )


@mcp.tool()
def capacity_scenario(
    available_minutes: float, cycle_minutes: float, machines: int = 1
) -> dict:
    """Explicit per-machine minutes and cycle time; scenario, not measured capacity."""
    return calculate_capacity(
        CapacityInput(
            available_minutes=available_minutes,
            cycle_minutes=cycle_minutes,
            machines=machines,
        )
    )


@mcp.tool()
def sop_lookup(question: str) -> list:
    """Local knowledge index retrieval, with no external embeddings permitted."""
    return search(question, allow_external=False)


if __name__ == "__main__":
    mcp.run(transport="stdio")
