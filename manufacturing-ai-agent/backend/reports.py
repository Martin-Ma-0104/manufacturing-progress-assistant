"""PDF adapter reusing the established ReportLab layout and Python calculations."""

from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import Spacer, PageBreak
from production_pdf import paragraph, table, build, comparison
from production_dashboard import aggregate_machines


def selection_pdf(result):
    rows = result["records"]
    scope = result["scope"]
    s = result["summary"]
    title = (
        "SYNTHETIC DEMONSTRATION"
        if result["source"] == "demo"
        else "Reviewed production history"
    )
    width = landscape(A4)[0] - 84
    story = [
        paragraph(title, 18),
        paragraph(
            scope["start"]
            + " to "
            + scope["end"]
            + " | "
            + scope["shift"]
            + " | "
            + (scope["machine"] or "All machines"),
            11,
        ),
        paragraph(
            "Historical records. Abnormality minutes are not net downtime. Missing observations are not zero.",
            9,
        ),
        Spacer(1, 8),
    ]
    story += [
        table(
            [
                "Planned input (mother rolls)",
                "Actual input (mother rolls)",
                "Input plan attainment",
                "Qualified area (m2)",
                "Area qualification",
            ],
            [
                [
                    s["planned_rolls"] if rows else "Not available",
                    s["input_rolls"] if rows else "Not available",
                    s["attainment"],
                    s["qualified_output_m2"] if rows else "Not available",
                    s["qualification"],
                ]
            ],
            [width / 5] * 5,
        )
    ]
    if rows:
        devices = aggregate_machines(rows)
        for fields, labels, unit in [
            (
                ("planned_rolls", "input_rolls"),
                ("Planned input", "Actual input"),
                "mother rolls",
            ),
            (
                ("actual_output_m2", "qualified_output_m2"),
                ("Actual area", "Qualified area"),
                "m2",
            ),
        ]:
            maximum = max((r[f] for r in devices for f in fields), default=0) or 1
            story += [
                Spacer(1, 12),
                paragraph(" / ".join(labels), 11),
                comparison(devices, fields, labels, unit, width, maximum),
            ]
        story += [PageBreak(), paragraph("Recorded production details", 14)]
        headers = [
            "Date",
            "Machine",
            "Shift",
            "Product",
            "Plan",
            "Input",
            "Qualified rolls",
            "Actual m2",
            "Qualified m2",
            "Source yield %",
        ]
        values = [
            [
                r["production_date"],
                r["machine_id"],
                r["shift"],
                r["product"],
                r["planned_rolls"],
                r["input_rolls"],
                r["qualified_rolls"],
                r["actual_output_m2"],
                r["qualified_output_m2"],
                r["reported_yield_pct"]
                if r["reported_yield_pct"] is not None
                else "N/A",
            ]
            for r in rows
        ]
        fractions = [0.1, 0.06, 0.06, 0.22, 0.06, 0.06, 0.09, 0.09, 0.09, 0.07]
        details = table(headers, values, [width * f for f in fractions])
        # Compact rows avoid an isolated final row on a nearly empty page.
        details.setStyle(
            [
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
        story += [details]
    else:
        story += [paragraph("No records in the selected scope.")]
    return build(story, title, landscape(A4))
