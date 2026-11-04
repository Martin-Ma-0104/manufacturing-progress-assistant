"""Exactly two read-only business tools. Paths are trusted application context."""

from contextlib import closing
from dataclasses import dataclass
from datetime import date, timedelta
import hashlib
from pathlib import Path
import sqlite3
import abnormality
from ai_production_data import catalog, normalize_scope, read_snapshot
from production_diagnostics import summary
from production_dashboard import machine_sort
from .contracts import Query, TOOL_A, TOOL_B


@dataclass(frozen=True)
class DataSource:
    path: Path
    kind: str

    def __post_init__(self):
        p = Path(self.path).expanduser().resolve()
        if self.kind not in ("synthetic", "real") or not p.is_file():
            raise ValueError(
                "Explicit existing real or synthetic database required; no default production path."
            )
        object.__setattr__(self, "path", p)
        with closing(sqlite3.connect(p.as_uri() + "?mode=ro", uri=True)) as connection:
            connection.execute("PRAGMA query_only=ON")
            found = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE name='research_fixture'"
            ).fetchone()
            if (self.kind == "synthetic") != bool(found):
                raise ValueError("Dataset origin does not match the database marker.")

    def fingerprint(self):
        return hashlib.sha256(self.path.read_bytes()).hexdigest()


class ResearchTools:
    def __init__(self, source: DataSource):
        self.source = source

    def describe(self):
        result = catalog(self.source.path)
        return dict(
            origin=self.source.kind,
            machines=result["machines"],
            date_range=[result["dates"][0], result["dates"][-1]]
            if result["dates"]
            else [],
            date_basis="inclusive recorded production_date",
            unit_a="input mother rolls",
            unit_b="recorded event-minutes",
        )

    def snapshot(self, query: Query):
        scope = normalize_scope(
            query.start_date,
            query.end_date,
            None if query.shift == "All" else query.shift,
            [query.machine_id] if query.machine_id else [],
        )
        try:
            result = read_snapshot(scope, self.source.path)
        except (TypeError, OverflowError):
            raise ValueError(
                "Production snapshot contains missing or malformed values."
            ) from None
        # Fail closed on malformed legacy data instead of making NULL into zero.
        for row in result["rows"]:
            if any(
                type(row[key]) is not int or row[key] < 0
                for key in ("planned_rolls", "input_rolls", "qualified_rolls")
            ):
                raise ValueError("Production count missing or malformed.")
        for event in result["abnormalities"]:
            abnormality.validate(
                {**event, "source_name": "read-only validation", "notes": ""}
            )
        return result

    @staticmethod
    def production_total(rows):
        value = summary(rows, [])
        plan, actual = value["planned_rolls"], value["input_rolls"]
        return dict(
            planned_inputs=plan,
            actual_inputs=actual,
            difference=value["input_delta"],
            shortfall=value["input_shortfall"],
            net_shortfall=max(plan - actual, 0) if rows else None,
            excess=value["input_excess"],
            record_count=len(rows),
        )

    def compare_production_inputs(self, query: Query):
        snapshot = self.snapshot(query)
        rows = snapshot["rows"]
        dates = sorted({r["production_date"] for r in rows})
        start, end = (
            date.fromisoformat(query.start_date),
            date.fromisoformat(query.end_date),
        )
        expected = [
            (start + timedelta(days=i)).isoformat()
            for i in range((end - start).days + 1)
        ]
        warnings = [
            "Input mother rolls are distinct from qualified finished rolls and output area.",
            "Shortfall is summed per record; net shortfall is a separate period measure.",
            "Missing observations do not establish zero input or complete shift coverage.",
        ]
        return dict(
            tool=TOOL_A,
            origin=self.source.kind,
            scope=query.model_dump(),
            unit="input mother rolls",
            **self.production_total(rows),
            by_machine=[
                dict(
                    machine_id=m,
                    **self.production_total([r for r in rows if r["machine_id"] == m]),
                )
                for m in sorted({r["machine_id"] for r in rows}, key=machine_sort)
            ],
            recorded_dates=dates,
            missing_dates=[d for d in expected if d not in dates],
            warnings=warnings,
        )

    def rank_abnormality_duration(self, query: Query):
        snapshot = self.snapshot(query)
        events = snapshot["abnormalities"]
        machines = (
            [query.machine_id] if query.machine_id else snapshot["available_machines"]
        )
        known, unranked = [], []
        for machine in machines:
            selected = [e for e in events if e["machine_id"] == machine]
            s = abnormality.summarize(selected)
            item = dict(machine_id=machine, **s, partial=s["missing_minutes_count"] > 0)
            if s["reported_minutes"] is None:
                unranked.append(
                    dict(
                        **item,
                        rank=None,
                        reason="missing_duration" if selected else "no_records",
                    )
                )
            else:
                known.append(item)
        known.sort(
            key=lambda r: (-r["reported_minutes"], machine_sort(r["machine_id"]))
        )
        previous = None
        rank = 0
        for index, row in enumerate(known, 1):
            if previous is None or row["reported_minutes"] != previous:
                rank = index
            row["rank"] = rank
            previous = row["reported_minutes"]
        warnings = [
            "Recorded event-minutes are additive and can overlap; they are not measured net downtime.",
            "Dates select source production_date, not clipped clock-window duration.",
            "Open status never extends an event to now; missing minutes remain unknown.",
            "Partial known totals cannot establish a complete ranking of actual abnormality duration.",
            "No event records do not establish zero abnormalities. Ties share competition ranks.",
        ]
        return dict(
            tool=TOOL_B,
            origin=self.source.kind,
            scope=query.model_dump(),
            unit="recorded event-minutes",
            **abnormality.summarize(events),
            rankings=known,
            unranked=unranked,
            warnings=warnings,
        )

    def invoke(self, name, args):
        functions = {
            TOOL_A: self.compare_production_inputs,
            TOOL_B: self.rank_abnormality_duration,
        }
        if name not in functions:
            raise ValueError("Unsupported research tool.")
        return functions[name](Query.model_validate(args))


def evidence(result):
    """Locally worded facts. The model can select IDs but cannot author numbers."""
    if result["tool"] == TOOL_A:
        facts = {
            "totals": f"Planned input: {result['planned_inputs']}; actual input: {result['actual_inputs']}; difference (actual minus plan): {result['difference']} input mother rolls.",
            "gaps": f"Record-level shortfall: {result['shortfall']}; net period shortfall: {result['net_shortfall']}; excess: {result['excess']} input mother rolls.",
            "coverage": f"{result['record_count']} production observations; {len(result['recorded_dates'])} recorded dates. Missing observations remain unavailable.",
        }
    else:
        ranking = (
            "; ".join(
                f"rank {r['rank']}: {r['machine_id']} = {r['reported_minutes']:g}"
                for r in result["rankings"]
            )
            or "No machines have a known recorded duration"
        )
        facts = {
            "ranking": ranking + " recorded event-minutes.",
            "coverage": f"{result['event_count']} events; {result['missing_minutes_count']} missing durations; {result['open_count']} open events; {result['overlap_event_count']} events participating in known overlaps.",
            "unranked": f"{len(result['unranked'])} machines are unranked because duration or event records are unavailable.",
        }
    if result["tool"] == TOOL_A and not result["record_count"]:
        facts["totals"] = (
            "No production observations are recorded in this scope; planned and actual inputs are unavailable."
        )
        facts["gaps"] = (
            "Input difference and shortfalls are unavailable; missing observations are not zero."
        )
    if result["tool"] == TOOL_B and not result["rankings"]:
        facts["ranking"] = (
            "No machines have known recorded event-minutes; no numeric ranking is available."
        )
    return facts
