"""Offline golden/baseline checks and an explicitly gated live evaluation runner."""

import argparse
import asyncio
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sqlite3
import statistics
import platform
import time
from unittest.mock import patch
from .contracts import AS_OF, MODEL, Query, TOOL_A
from .tools import DataSource, ResearchTools

HERE = Path(__file__).resolve().parent
CORE = (
    "contracts.py",
    "tool_definitions.json",
    "fixtures.py",
    "tools.py",
    "agent.py",
    "evaluation.py",
    "case_design.py",
    "evaluation_cases.json",
    "QA.md",
    "fixtures_source.json",
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def matches(actual, expected):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            k in actual and matches(actual[k], v) for k, v in expected.items()
        )
    if isinstance(expected, list):
        return (
            isinstance(actual, list)
            and len(actual) == len(expected)
            and all(matches(a, b) for a, b in zip(actual, expected))
        )
    if type(expected) in (int, float):
        return type(actual) in (int, float) and abs(actual - expected) <= 0.000001
    return type(actual) is type(expected) and actual == expected


def freeze(data_dir, destination):
    data_dir = Path(data_dir).expanduser().resolve()
    destination = Path(destination)
    if destination.exists():
        raise ValueError("Manifest already exists; do not rewrite a frozen version.")
    datasets = {}
    for variant in ("A", "B"):
        path = Path(data_dir) / f"sample_{variant.lower()}.db"
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as db:
            metadata = db.execute(
                "SELECT dataset_id,logical_sha256 FROM research_fixture"
            ).fetchone()
        if metadata[0] != variant:
            raise ValueError("Wrong fixture variant.")
        datasets[variant] = dict(
            filename=path.name, sha256=sha(path), logical_sha256=metadata[1]
        )
    value = dict(
        version="1.1",
        frozen_at_utc=datetime.now(timezone.utc).isoformat(),
        frozen_before_live_testing=True,
        model=MODEL,
        immutable_model_snapshot_available=False,
        reasoning="none",
        service_tier="default",
        as_of=AS_OF,
        files={name: sha(HERE / name) for name in CORE},
        datasets=datasets,
        shared_files={
            name: sha(HERE.parents[1] / name)
            for name in (
                "ai_production_data.py",
                "production_diagnostics.py",
                "production_dashboard.py",
                "production.py",
                "abnormality.py",
                "backend/data.py",
                "backend/__init__.py",
                "backend/runtime.py",
                "backend/models.py",
            )
        },
        python_version=platform.python_version(),
        sqlite_version=sqlite3.sqlite_version,
        versions={
            name: importlib.metadata.version(name)
            for name in ("openai-agents", "openai", "pydantic")
        },
        pricing=dict(
            as_of="2026-11-02",
            input_per_million=2,
            output_per_million=10,
            currency="USD",
        ),
        design=dict(
            primary_questions=20,
            variant_b_questions=6,
            repetitions=3,
            max_business_calls_per_trial=1,
            max_model_calls_per_trial=2,
        ),
        explanation_method="LLM selects evidence IDs; factual sentences and numerical tables are rendered locally, not unrestricted prose.",
    )
    destination.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    return value


def verify_freeze(data_dir, manifest_path):
    manifest = json.loads(Path(manifest_path).read_text())
    for name, digest in manifest["files"].items():
        if sha(HERE / name) != digest:
            raise ValueError("Frozen source changed: " + name)
    for name, digest in manifest["shared_files"].items():
        if sha(HERE.parents[1] / name) != digest:
            raise ValueError("Frozen shared calculation changed: " + name)
    if (
        platform.python_version() != manifest["python_version"]
        or sqlite3.sqlite_version != manifest["sqlite_version"]
    ):
        raise ValueError("Python/SQLite runtime differs from frozen experiment.")
    for value in manifest["datasets"].values():
        if sha(Path(data_dir) / value["filename"]) != value["sha256"]:
            raise ValueError("Frozen database changed.")
    versions = {name: importlib.metadata.version(name) for name in manifest["versions"]}
    if versions != manifest["versions"]:
        raise ValueError("SDK versions differ from frozen experiment.")
    return manifest


def tool_checks(data_dir):
    dataset = json.loads((HERE / "evaluation_cases.json").read_text())
    trials = []
    for variant in ("A", "B"):
        source = DataSource(
            Path(data_dir).resolve() / f"sample_{variant.lower()}.db", "synthetic"
        )
        service = ResearchTools(source)
        before = source.fingerprint()
        for case in dataset["cases"]:
            if case["expected_tool"] is None or (
                variant == "B" and case["id"] not in dataset["dataset_b_cases"]
            ):
                continue
            start = time.perf_counter()
            actual = service.invoke(case["expected_tool"], case["expected_arguments"])
            expected = (
                case.get("database_b_answer", case["expected_answer"])
                if variant == "B"
                else case["expected_answer"]
            )
            trials.append(
                dict(
                    case_id=case["id"],
                    dataset=variant,
                    passed=matches(actual, expected),
                    seconds=time.perf_counter() - start,
                )
            )
        if before != source.fingerprint():
            raise AssertionError("Tool validation mutated a fixture.")
    return dict(
        mode="tools_only",
        trial_count=len(trials),
        passed=sum(r["passed"] for r in trials),
        trials=trials,
        tool_selection_accuracy=None,
        argument_accuracy=None,
        explanation_consistency=None,
        note="Expected arguments are injected for deterministic tool checking. No natural-language model was tested.",
    )


def dashboard_comparison(source, queries):
    """Real dashboard calculation path; no claim about human UI task time."""
    # The existing backend initializer loads a private .env on import. Its
    # calculation-only baseline must not load that file or mutate this process's
    # configuration. Keep this guard local; do not change the running application.
    with patch("dotenv.load_dotenv", return_value=False):
        from backend.data import dashboard
        from backend.models import Scope

    service = ResearchTools(source)
    before = source.fingerprint()
    rows = []
    for args in queries:
        q = Query.model_validate(args)
        start = time.perf_counter()
        a = service.compare_production_inputs(q)
        b = service.rank_abnormality_duration(q)
        tool_time = time.perf_counter() - start
        with patch("backend.data.db_path", return_value=source.path):
            start = time.perf_counter()
            base = dashboard(
                Scope(
                    start=q.start_date,
                    end=q.end_date,
                    machine=q.machine_id,
                    shift=q.shift,
                )
            )
            base_time = time.perf_counter() - start
        original = base["summary"]
        prod = base["records"]
        expected = dict(
            planned_inputs=original["planned_rolls"],
            actual_inputs=original["input_rolls"],
            difference=sum(r["input_rolls"] - r["planned_rolls"] for r in prod)
            if prod
            else None,
            shortfall=sum(max(r["planned_rolls"] - r["input_rolls"], 0) for r in prod)
            if prod
            else None,
        )
        consistent = matches(a, expected) and matches(
            b,
            {
                k: base["abnormalities"][k]
                for k in (
                    "event_count",
                    "reported_minutes",
                    "missing_minutes_count",
                    "open_count",
                    "overlap_event_count",
                )
            },
        )
        for item in b["rankings"] + b["unranked"]:
            old = next(
                m for m in base["machines"] if m["machine_id"] == item["machine_id"]
            )["abnormalities"]
            consistent = consistent and matches(
                item,
                {
                    k: old[k]
                    for k in (
                        "event_count",
                        "reported_minutes",
                        "missing_minutes_count",
                    )
                },
            )
        rows.append(
            dict(
                scope=q.model_dump(),
                agreement=bool(consistent),
                two_tools_seconds=tool_time,
                dashboard_service_seconds=base_time,
            )
        )
    if source.fingerprint() != before:
        raise AssertionError("Dashboard comparison changed a database.")
    return dict(
        origin=source.kind,
        scope_count=len(rows),
        agreements=sum(r["agreement"] for r in rows),
        rows=rows,
        median_two_tools_seconds=statistics.median(r["two_tools_seconds"] for r in rows)
        if rows
        else None,
        median_dashboard_service_seconds=statistics.median(
            r["dashboard_service_seconds"] for r in rows
        )
        if rows
        else None,
        human_dashboard_task_time="not measured",
        live_agent_task_time="not measured",
        limitation="Agreement of reused calculations is not an independent oracle. Synthetic hand arithmetic is checked separately. Service timings are not a UI/user study or a speedup finding.",
    )


def comparison_queries(source):
    description = ResearchTools(source).describe()
    end = date.fromisoformat(description["date_range"][-1])
    periods = [
        (end - timedelta(days=6), end),
        (end, end),
        (end - timedelta(days=29), end),
    ]
    return [
        Query(
            start_date=start.isoformat(),
            end_date=stop.isoformat(),
            machine_id=machine,
            shift=shift,
        ).model_dump()
        for start, stop in periods
        for machine in [None, *description["machines"]]
        for shift in ("All", "Day", "Night")
    ]


def score_trial(case, answer, variant="A"):
    expected_tool = case["expected_tool"]
    trace = answer.get("trace", [])
    if expected_tool is None:
        ok = (
            answer.get("status") == "clarification"
            and not trace
            and matches(answer.get("clarification", {}), case["expected_answer"])
        )
        return dict(
            tool_selection=None,
            arguments=None,
            numerical=None,
            explanation=None,
            clarification=ok,
            end_to_end=ok,
        )
    selected = len(trace) == 1 and trace[0].get("tool") == expected_tool
    arguments = selected and trace[0].get("arguments") == case["expected_arguments"]
    expected = (
        case.get("database_b_answer", case["expected_answer"])
        if variant == "B"
        else case["expected_answer"]
    )
    numerical = answer.get("status") == "answered" and matches(
        answer.get("result"), expected
    )
    required = (
        {"totals", "gaps", "coverage"}
        if expected_tool == TOOL_A
        else {"ranking", "coverage", "unranked"}
    )
    # Factual text is local. This measures evidence selection/renderer consistency,
    # not free-form explanation quality or a substitute for human review.
    explanation = (
        numerical
        and required.issubset(answer.get("fact_ids", []))
        and answer.get("warnings") == answer.get("result", {}).get("warnings")
    )
    return dict(
        tool_selection=selected,
        arguments=arguments,
        numerical=numerical,
        explanation=explanation,
        clarification=None,
        end_to_end=bool(selected and arguments and numerical and explanation),
    )


async def live_evaluation(data_dir, manifest, permit, output_dir):
    from .agent import ResearchAgent

    verify_freeze(data_dir, manifest)
    cases = json.loads((HERE / "evaluation_cases.json").read_text())
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    records = []
    for variant in ("A", "B"):
        service = ResearchTools(
            DataSource(
                Path(data_dir).resolve() / f"sample_{variant.lower()}.db", "synthetic"
            )
        )
        agent = ResearchAgent(
            service, Query(start_date="2026-01-01", end_date="2026-01-30")
        )
        for case in cases["cases"]:
            if variant == "B" and case["id"] not in cases["dataset_b_cases"]:
                continue
            for repeat in range(3):
                verify_freeze(data_dir, manifest)
                answer = await agent.run(case["question"], permit=permit)
                row = dict(
                    recorded_at_utc=datetime.now(timezone.utc).isoformat(),
                    case_id=case["id"],
                    dataset=variant,
                    repeat=repeat + 1,
                    answer=answer,
                    score=score_trial(case, answer, variant),
                    manual_explanation_review="not reviewed",
                )
                records.append(row)
                with (output_dir / "trials.jsonl").open(
                    "a", encoding="utf-8"
                ) as stream:
                    stream.write(json.dumps(row, ensure_ascii=False) + "\n")
                if answer.get("error_type") == "PermissionError":
                    break
            else:
                continue
            break
        else:
            continue
        break
    metrics = {}
    for name in (
        "tool_selection",
        "arguments",
        "numerical",
        "explanation",
        "clarification",
        "end_to_end",
    ):
        relevant = [r["score"][name] for r in records if r["score"][name] is not None]
        metrics[name] = dict(
            correct=sum(relevant),
            applicable=len(relevant),
            attempted_rate=sum(relevant) / len(relevant) if relevant else None,
        )
    conditional = [r for r in records if r["score"]["arguments"] is True]
    metrics["numerical_given_correct_arguments"] = dict(
        correct=sum(r["score"]["numerical"] for r in conditional),
        applicable=len(conditional),
    )
    result = dict(
        mode="live",
        planned_trials=78,
        attempted_trials=len(records),
        metrics=metrics,
        model=MODEL,
        accounted_cost_usd=permit.spent_usd,
        requests=permit.requests,
        budget_usd=permit.budget_usd,
        missing_attempts=78 - len(records),
        manual_review="not reviewed",
        unrestricted_explanation_quality="not evaluated",
        human_dashboard_task_time="not measured",
        median_attempt_seconds=statistics.median(
            r["answer"]["seconds"] for r in records
        )
        if records
        else None,
    )
    (output_dir / "summary.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--manifest", type=Path, default=HERE / "manifest.json")
    parser.add_argument("--real-db", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--mode", choices=["tools", "freeze", "baseline", "live"], default="tools"
    )
    parser.add_argument("--allow-paid", action="store_true")
    parser.add_argument("--budget-usd", type=float)
    args = parser.parse_args()
    if args.data_dir is None and args.real_db is None:
        parser.error("Choose --data-dir or --real-db explicitly.")
    if args.mode == "live":
        if not args.allow_paid or args.budget_usd is None:
            parser.error(
                "Live calls require --allow-paid and an explicit --budget-usd; keys alone do not authorize spending."
            )
        if args.real_db:
            parser.error(
                "The frozen live benchmark accepts synthetic databases only. Use real data locally through baseline/tools."
            )
        if args.data_dir is None:
            parser.error("--data-dir is required.")
        from .agent import LivePermit

        result = asyncio.run(
            live_evaluation(
                args.data_dir,
                args.manifest,
                LivePermit(args.budget_usd, allow_external=True),
                args.output,
            )
        )
    elif args.mode == "freeze":
        if args.data_dir is None:
            parser.error("--data-dir is required.")
        result = freeze(args.data_dir, args.output)
    else:
        if args.mode == "tools":
            if args.real_db:
                parser.error(
                    "Golden-answer checking is synthetic only; use --mode baseline for the real database."
                )
            verify_freeze(args.data_dir, args.manifest)
            result = tool_checks(args.data_dir)
        else:
            source = (
                DataSource(args.real_db, "real")
                if args.real_db
                else DataSource(args.data_dir.resolve() / "sample_a.db", "synthetic")
            )
            result = dashboard_comparison(source, comparison_queries(source))
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {k: v for k, v in result.items() if k not in ("trials", "rows", "files")},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
