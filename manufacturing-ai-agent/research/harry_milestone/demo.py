"""Local real-data tools or a clearly mocked end-to-end synthetic demonstration."""

import argparse
import asyncio
import json
from pathlib import Path
from .contracts import Query, TOOL_A, TOOL_B
from .tools import DataSource, ResearchTools


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--sample-db", type=Path)
    source.add_argument("--real-db", type=Path)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--machine")
    parser.add_argument("--shift", choices=["All", "Day", "Night"], default="All")
    parser.add_argument("--tool", choices=[TOOL_A, TOOL_B])
    parser.add_argument("--mock", action="store_true")
    args = parser.parse_args()
    tools = ResearchTools(
        DataSource(
            args.real_db or args.sample_db, "real" if args.real_db else "synthetic"
        )
    )
    q = Query(
        start_date=args.start,
        end_date=args.end,
        machine_id=args.machine,
        shift=args.shift,
    )
    before = tools.source.fingerprint()
    if args.mock:
        if args.real_db:
            parser.error(
                "The scripted mock demonstration uses a synthetic fixture only."
            )
        from .agent import ResearchAgent, ScriptedDemoRunner

        result = asyncio.run(
            ResearchAgent(tools, q).run(
                "Show FX1 mother-roll input for 2026-01-05 through 2026-01-06.",
                mock_runner=ScriptedDemoRunner(),
            )
        )
    else:
        if not args.tool:
            parser.error(
                "Select a read-only tool with --tool, or use --mock for the synthetic scripted demo."
            )
        result = dict(
            mode="deterministic_tools_only",
            model_requests=0,
            result=tools.invoke(args.tool, q.model_dump()),
        )
    if before != tools.source.fingerprint():
        raise AssertionError("Demo changed the database.")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
