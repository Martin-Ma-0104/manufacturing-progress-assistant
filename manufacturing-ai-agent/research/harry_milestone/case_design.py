"""Hand-calculated oracle. Never imported by model-facing agent code.

This creates the readable QA/JSON artifacts, not answers calculated by tools.
P1-P8 and E1-E10 refer to the tiny invented fixture rows in fixtures.py.
"""

import argparse
import json
from pathlib import Path
from .contracts import AS_OF, TIMEZONE, TOOL_A, TOOL_B


def cases():
    def args(start="2026-01-05", end="2026-01-07", machine=None, shift="All"):
        return dict(start_date=start, end_date=end, machine_id=machine, shift=shift)

    def a(p, a, d, s, n, e, r):
        return dict(
            planned_inputs=p,
            actual_inputs=a,
            difference=d,
            shortfall=s,
            net_shortfall=n,
            excess=e,
            record_count=r,
            unit="input mother rolls",
        )

    rows = []

    def add(ident, question, tool, arguments, answer, why, explanation):
        rows.append(
            dict(
                id=ident,
                question=question,
                expected_tool=tool,
                expected_arguments=arguments,
                expected_answer=answer,
                hand_verification=why,
                expected_explanation=explanation,
            )
        )

    add(
        "Q01",
        "Compare planned and actual input mother rolls from 2026-01-05 to 2026-01-07, including the shortfall.",
        TOOL_A,
        args(),
        a(70, 56, -14, 18, 14, 4, 8),
        "P1-P8: plan=10+10+12+20+10+8+0+0=70; input=8+12+9+15+10+0+2+0=56; deficits=2+3+5+8=18; excess=2+2=4.",
        "Distinguish record-level deficit 18 from net period shortfall 14; mother rolls only.",
    )
    add(
        "Q02",
        "For FX1, compare planned and actual mother-roll input from 2026-01-05 to 2026-01-07.",
        TOOL_A,
        args(machine="FX1"),
        a(32, 29, -3, 5, 3, 2, 3),
        "P1-P3: plan=32; input=29; deficits=2+3; excess=2.",
        "Net gap -3 and record-level shortfall 5 differ.",
    )
    add(
        "Q03",
        "On 2026-01-05, did FX1 have any input mother-roll shortfall even if the day total met plan?",
        TOOL_A,
        args(end="2026-01-05", machine="FX1"),
        a(20, 20, 0, 2, 0, 2, 2),
        "P1=10/8 and P2=10/12: net=0; deficit=2.",
        "Night excess does not erase the Day record deficit.",
    )
    add(
        "Q04",
        "Compare planned versus actual mother-roll input for FX1 Night shift on 2026-01-05.",
        TOOL_A,
        args(end="2026-01-05", machine="FX1", shift="Night"),
        a(10, 12, 2, 0, 0, 2, 1),
        "P2 only: 10 planned,12 input.",
        "This is excess input of 2, not a negative shortfall.",
    )
    add(
        "Q05",
        "What were FX4 planned and actual input mother rolls on 2026-01-07 Day shift?",
        TOOL_A,
        args(start="2026-01-07", machine="FX4", shift="Day"),
        a(0, 2, 2, 0, 0, 2, 1),
        "P7: plan 0, actual 2. No ratio is needed.",
        "Preserve explicit zero plan; do not invent attainment from a zero denominator.",
    )
    add(
        "Q06",
        "Compare planned and actual input mother rolls on 2026-01-08.",
        TOOL_A,
        args(start="2026-01-08", end="2026-01-08"),
        a(None, None, None, None, None, None, 0),
        "No production rows are dated Jan 8.",
        "Unavailable observations are not zero production.",
    )
    add(
        "Q07",
        "Compare FX8 planned and actual input mother rolls on 2026-01-07.",
        TOOL_A,
        args(start="2026-01-07", machine="FX8"),
        a(0, 0, 0, 0, 0, 0, 1),
        "P8 explicitly records zero plan and zero input.",
        "An explicit zero record differs from an absent row.",
    )
    add(
        "Q08",
        "Compare planned and actual input mother rolls last week.",
        TOOL_A,
        args(end="2026-01-11"),
        a(70, 56, -14, 18, 14, 4, 8),
        "Fixed business date Jan12 Monday: last calendar week is Jan5-Jan11. Only P1-P8 exist.",
        "Use the fixed clock and Monday-Sunday convention; disclose missing days, not zero-fill.",
    )
    add(
        "Q09",
        "For FX2, compare input mother-roll plan with actual input between 2026-01-05 and 2026-01-07.",
        TOOL_A,
        args(machine="FX2"),
        a(30, 25, -5, 5, 5, 0, 2),
        "P4+P5: 20+10 planned,15+10 actual.",
        "Use both range boundaries and only FX2.",
    )
    ranking_a = [
        dict(machine_id="FX1", rank=1, reported_minutes=180, partial=False),
        dict(machine_id="FX2", rank=2, reported_minutes=150, partial=True),
        dict(machine_id="FX4", rank=3, reported_minutes=15, partial=False),
    ]
    ranking_b = [
        dict(machine_id="FX2", rank=1, reported_minutes=300, partial=True),
        dict(machine_id="FX1", rank=2, reported_minutes=180, partial=False),
        dict(machine_id="FX4", rank=3, reported_minutes=15, partial=False),
    ]
    add(
        "Q10",
        "Rank machines by known recorded abnormality event-minutes from 2026-01-05 to 2026-01-07.",
        TOOL_B,
        args(),
        dict(
            reported_minutes=345,
            event_count=10,
            missing_minutes_count=2,
            open_count=3,
            overlap_event_count=2,
            incomplete_time_count=2,
            mismatch_count=1,
            rankings=ranking_a,
            unit="recorded event-minutes",
        ),
        "FX1:E1+E2+E3=180; FX2:E4+E5=150,E6 unknown; FX4:E7+E9+E10=15; FX5:E8 unknown; FX8 no events.",
        "Ranking is by known recorded subtotal; FX2 is partial, overlaps remain additive, no net-downtime claim.",
    )
    rows[-1]["database_b_answer"] = dict(
        rows[-1]["expected_answer"], reported_minutes=495, rankings=ranking_b
    )
    add(
        "Q11",
        "Rank machines by recorded abnormality minutes on 2026-01-05, including ties.",
        TOOL_B,
        args(end="2026-01-05"),
        dict(
            reported_minutes=240,
            event_count=4,
            rankings=[
                dict(machine_id="FX1", rank=1, reported_minutes=120),
                dict(machine_id="FX2", rank=1, reported_minutes=120),
                dict(machine_id="FX4", rank=3, reported_minutes=0),
            ],
        ),
        "E1+E2=120; E4=120; E10=0. Competition ranks 1,1,3.",
        "FX1 and FX2 tie; reported overlap does not become de-duplicated elapsed time.",
    )
    rows[-1]["database_b_answer"] = dict(
        reported_minutes=360,
        event_count=4,
        rankings=[
            dict(machine_id="FX2", rank=1, reported_minutes=240),
            dict(machine_id="FX1", rank=2, reported_minutes=120),
            dict(machine_id="FX4", rank=3, reported_minutes=0),
        ],
    )
    add(
        "Q12",
        "How many recorded abnormality minutes does FX1 have from 2026-01-06 through 2026-01-07?",
        TOOL_B,
        args(start="2026-01-06", machine="FX1"),
        dict(
            reported_minutes=60,
            event_count=1,
            rankings=[dict(machine_id="FX1", rank=1, reported_minutes=60)],
        ),
        "E3 crosses midnight but is one 60-minute recorded event assigned to Jan6.",
        "Retain the explicit overnight event once; date filtering uses production_date.",
    )
    add(
        "Q13",
        "Rank FX2 by its known recorded abnormality duration from 2026-01-06 to 2026-01-07; explain missing times.",
        TOOL_B,
        args(start="2026-01-06", machine="FX2"),
        dict(
            reported_minutes=30,
            event_count=2,
            missing_minutes_count=1,
            incomplete_time_count=1,
            open_count=2,
            rankings=[
                dict(machine_id="FX2", rank=1, reported_minutes=30, partial=True)
            ],
        ),
        "E5 reports 30 despite missing end; E6 has 20 clock minutes but unknown reported minutes. Do not add E6.",
        "Known subtotal 30 is partial, not complete duration or net downtime; Open is not an instruction to extend to now.",
    )
    rows[-1]["database_b_answer"] = dict(
        rows[-1]["expected_answer"],
        reported_minutes=60,
        rankings=[dict(machine_id="FX2", rank=1, reported_minutes=60, partial=True)],
    )
    add(
        "Q14",
        "What is FX5 recorded abnormality duration and rank on 2026-01-07?",
        TOOL_B,
        args(start="2026-01-07", machine="FX5"),
        dict(
            reported_minutes=None,
            event_count=1,
            rankings=[],
            unranked=[
                dict(
                    machine_id="FX5",
                    rank=None,
                    reason="missing_duration",
                    missing_minutes_count=1,
                )
            ],
        ),
        "E8 has unknown duration, start, end and status.",
        "Unknown is unranked, not zero or the lowest-duration machine.",
    )
    add(
        "Q15",
        "What is FX4 recorded abnormality duration on 2026-01-06 Night shift?",
        TOOL_B,
        args(start="2026-01-06", end="2026-01-06", machine="FX4", shift="Night"),
        dict(
            reported_minutes=0,
            event_count=1,
            rankings=[dict(machine_id="FX4", rank=1, reported_minutes=0)],
        ),
        "E7 explicitly reports 0.",
        "Preserve recorded zero and selected-scope rank; do not generalize to no problems.",
    )
    add(
        "Q16",
        "Rank machines by recorded abnormality duration on 2026-01-08.",
        TOOL_B,
        args(start="2026-01-08", end="2026-01-08"),
        dict(reported_minutes=None, event_count=0, rankings=[]),
        "No events dated Jan8.",
        "No records give no numeric ranking, not all machines tied at zero.",
    )
    for ident, question, reason, why in [
        (
            "Q17",
            "Which machine has the biggest production input shortfall recently?",
            "ambiguous",
            "Ask for a date range; recently has no fixed definition.",
        ),
        (
            "Q18",
            "Compare production last week.",
            "ambiguous",
            "Ask whether input mother rolls, qualified finished rolls or output m² is intended.",
        ),
        (
            "Q19",
            "Which machine had the most actual net downtime from 2026-01-05 to 2026-01-07?",
            "unsupported",
            "Explain that measured net downtime is unavailable; ask whether recorded event-minutes are acceptable.",
        ),
        (
            "Q20",
            "Compare input mother rolls for line A from 2026-01-05 to 2026-01-07.",
            "ambiguous",
            "Ask which known machine ID line A denotes; do not guess FX1.",
        ),
    ]:
        add(
            ident,
            question,
            None,
            None,
            dict(
                reason=reason,
                target={
                    "Q17": "date_range",
                    "Q18": "production_unit",
                    "Q19": "unsupported_metric",
                    "Q20": "machine_id",
                }[ident],
            ),
            "No business-tool call is correct before clarification.",
            why,
        )
    return dict(
        version="1.0",
        as_of=AS_OF,
        timezone=TIMEZONE,
        last_week="previous Monday through Sunday",
        dataset_b_cases=["Q10", "Q11", "Q12", "Q13", "Q14", "Q16"],
        cases=rows,
    )


def write(directory):
    directory = Path(directory)
    value = cases()
    (directory / "evaluation_cases.json").write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    table = [
        "# Frozen evaluation questions v1.0",
        "",
        f"Fixed clock: {AS_OF}, {TIMEZONE}. All values below are invented.",
        "",
        "| ID | Question | Expected tool / arguments | Correct answer | Hand verification | Expected explanation |",
        "|---|---|---|---|---|---|",
    ]
    for row in value["cases"]:
        cells = [
            row["id"],
            row["question"],
            str(row["expected_tool"]) + " " + json.dumps(row["expected_arguments"]),
            json.dumps(row["expected_answer"]),
            row["hand_verification"],
            row["expected_explanation"],
        ]
        table.append("| " + " | ".join(c.replace("|", "\\|") for c in cells) + " |")
    table += [
        "",
        "## Database B controls",
        "",
        "Only E4 and E5 change: E4 becomes 240 minutes (10:00–14:00); E5 reports 60 minutes. FX2 becomes the top known subtotal (300); FX1 remains 180. Production is identical.",
        "",
    ]
    for row in value["cases"]:
        if row["id"] in value["dataset_b_cases"]:
            table.append(
                f"- {row['id']}: `"
                + json.dumps(row.get("database_b_answer", row["expected_answer"]))
                + "`"
            )
    (directory / "QA.md").write_text("\n".join(table) + "\n", encoding="utf-8")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, required=True)
    write(p.parse_args().output)
