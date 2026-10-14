# Daily Slitting Production

This extension stores user-supplied daily production observations separately from
Phase 1 simulated orders, inventory, and machine settings. It uses only Python's
standard library. It does not implement automatic image recognition or call an AI
service. Screenshot transcription is reviewed in conversation and saved locally.

## Import and report

From the project directory:

```bash
python3 production.py local_data/slitting-2026-10-12.json
python3 production_report.py --date 2026-10-12
open reports/slitting-2026-10-12.html
python3 -m unittest test_production.py
```

The import creates `slitting_records` in the existing database without modifying
the five demo tables. Every record is one production date, shift, machine and
product. Multiple runs of the same product within a shift must be aggregated
before import. Different products remain separate records. Reimporting identical
records is a no-op. Conflicting records reject and roll back the entire batch;
this importer deliberately does not silently overwrite previously entered data.

`production_date` is the operational date supplied by the user. Preserve the
original screenshot's date and shift in `source_report_date` and
`source_shift_label`, even when the user corrects their classification.
`source_name` references a locally retained source image and `notes` records
transcription context. Historical machine IDs do not inherit current settings
from the simulated machine master; an observed machine need not exist there.

JSON input is a list of objects with all these fields (synthetic example):

```json
[
  {
    "production_date": "2026-01-01",
    "shift": "Day",
    "machine_id": "TEST1",
    "product": "DEMO",
    "planned_rolls": 10,
    "input_rolls": 5,
    "qualified_rolls": 20,
    "actual_output_m2": 100.0,
    "qualified_output_m2": 80.0,
    "reported_yield_pct": null,
    "source_report_date": "2026-01-01",
    "source_shift_label": "Day",
    "source_name": "example.png",
    "notes": "Synthetic example, not production data."
  }
]
```

Use `Day` or `Night` for shift; dates use `YYYY-MM-DD`. Counts must be nonnegative
integers; areas must be finite nonnegative numbers. Qualified area cannot exceed
actual output area. Unknown reported yield is `null`, not zero.

## Chart selection and metric definitions

For one day's data, the offline HTML report automatically generates two grouped
bar charts: planned versus actual input rolls, and actual versus qualified output
area. It includes day/night totals and all machine/product details. No CDN, web
server or package installation is required. The web application also provides 7/30-day trends.

- Input plan attainment = input rolls / planned rolls.
- Area qualification rate = qualified output area / actual output area.
- Aggregates use ratios of sums, not averages of machine percentages.
- Zero denominators display as unavailable.
- Reported yield is retained from the source. Its formula and original input area
  are unknown, so aggregate yield is not inferred.
- Input rolls and finished rolls represent different units of work; do not divide
  them to infer yield. Missing machines/shifts are absent observations, not zeros.
- Output records describe actual production, not theoretical capacity. Area not
  recorded as qualified is not automatically classified as scrap.

## Local data

`local_data/` (including screenshots and transcribed JSON), `reports/`, and the
SQLite database are ignored by Git. Real production records must not be put in
seed scripts, tests, README examples, commits, or public repositories. Back up
these local files separately; a Git clone alone does not recover production data.
The existing `verify_db.py` prints the five Phase 1 tables; use the production
report for daily production details.

## Existing Streamlit web app

The existing optional Streamlit app now has a **分切生产日报** sidebar page
(default) and retains **订单分析**. Use the calendar to select a production date, shift and machine, then view
current SQLite records or download the filtered report. **刷新数据**
reloads dates and records after another import. No report generation command is
needed for the web view. This page does not upload or recognize photographs.

Run with the existing virtual environment (Streamlit is already installed there):

```bash
.venv/bin/python -m streamlit run streamlit_app.py --server.address 127.0.0.1
```

By default Streamlit uses port 8501. This project’s current local preview uses
port 8502 (add `--server.port 8502` to the command). This local app is separate from
the source factory reporting website shown in screenshots. The standard-library
CLI remains usable without Streamlit.

## Report modes and trends

The web page initially prompts for a report type. Daily data appears only after
selecting **当日数据**. Weekly and monthly machine trends use rolling windows of
7 and 30 calendar days, including the selected end date. Choose all machines or
one machine, all shifts or one shift, and an area/count metric. Each point sums
recorded products and selected shifts for a machine/date. Missing dates remain
gaps; lines never bridge missing dates. An orange point in all-shifts mode means
only one shift was recorded. One-day histories show points without inferred
trends. New imports are included on refresh.

## Confirmed changeovers

Trend markers read explicit records from `changeover_events`, keyed by production
date, shift and machine. Product-code differences alone never create a marker.
The optional table contains `from_product`, `to_product`, and `confirmation_note`.
Absent event tables or missing events produce no changeover markers. Events obey
the selected date and shift filters; production quantities are unchanged.

## PLAN-003 v1 Dashboard layout

The daily page uses native Streamlit filters, metric cards and expandable details.
`production_dashboard.py` owns pure filtering, ratios of sums, unique device counts,
per-device totals, coverage descriptions and detail formatting. Both the web page
and `production_report.py` use these functions. Device comparison bars aggregate
selected shifts/products; original records remain available in the details.

The first four indicators are qualified output area, input plan attainment,
area qualification rate and recorded device count. Counts describe observed IDs,
not running machines or utilization. Supporting counts/area and shift summaries
remain visible. No-data areas and ratios show —, and recorded device count is 0.
Coverage reports recorded Day/Night machines and their intersection only; it does
not establish full-factory completeness or indicate downtime.

Daily mode now includes linked machine trends after the comparisons. Its date is
the inclusive trend end date, with a 7/30-day selector. Global date, shift and machine
filters apply consistently; devices are selectable from historical observations,
so a missing current-date observation does not remove a device from the selector.
Standalone weekly/monthly modes remain supported. The single device selection
also determines the comparison scale. Plan lines remain dashed; only confirmed
changeovers are marked. Existing orange shift-coverage markers describe missing
shift observations without assessing performance.

`.streamlit/config.toml` defines the light blue-gray theme. No new packages were
introduced; requirements.txt now records the already installed Streamlit version.
New `test_dashboard.py` uses synthetic records and isolated databases only.
