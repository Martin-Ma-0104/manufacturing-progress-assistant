# Production Data Viewer Agent

A manufacturing data dashboard for IE and production managers, focused on daily
**slitting machine performance**. Review planned input, actual input, qualified
finished rolls, output areas, and recorded production history for machines such
as FX1 and FX2.

The application uses Python, Streamlit, SQLite, and ReportLab. Its current role
is production data viewing and reporting; it does not perform autonomous AI
analysis, recognize screenshots, or collect live machine signals. Existing
screen labels are primarily Chinese; this README describes the workflow in English.

## Slitting Machine Dashboard

### Daily production data

Select the daily report mode, choose a date from the calendar, then filter by
**All / Day / Night** shifts and **All / Single Machine**. The page presents:

1. **Overall summary:** qualified output area, input plan attainment, area
   qualification rate, and recorded machine count.
2. **Machine comparisons:** planned versus actual input rolls, and actual versus
   qualified output area, with machine labels, units, legends, and values.
3. **Machine trends:** linked 7-day or 30-day history ending on the selected date.
4. **Production details:** expandable records by machine, product, and shift.

Each production record retains the following fields:

| Metric | Field | Unit / definition |
| --- | --- | --- |
| Planned input | `planned_rolls` | Input rolls planned for the recorded machine and shift |
| Actual input | `input_rolls` | Input rolls actually processed |
| Qualified finished rolls | `qualified_rolls` | Qualified finished rolls, distinct from input rolls |
| Actual output area | `actual_output_m2` | Square meters (m²) |
| Qualified output area | `qualified_output_m2` | Square meters (m²) |
| Input plan attainment | Calculated | Actual input rolls / planned input rolls |
| Area qualification rate | Calculated | Qualified output area / actual output area |
| Reported yield | `reported_yield_pct` | Original report percentage; unknown values remain unavailable |

Summaries calculate ratios from the **sum of numerators divided by the sum of
denominators**, not the average of machine percentages. A zero denominator is
shown as unavailable. Recorded machine count describes observed machine IDs;
it is not a running-machine count or utilization measure.

### Trends and shift coverage

- View one machine or all machines over the most recent **7 or 30 calendar days**,
  including the selected end date. Separate weekly and monthly report modes are
  also available.
- Choose qualified output area, actual output area, qualified finished rolls, or
  actual input together with planned input.
- Input trends show **actual input as a solid line** and **planned input as a
  dashed reference line**.
- Missing dates remain gaps; lines do not bridge dates without records.
- In all-shift views, an orange point identifies a date with only one recorded
  shift. Coverage messages describe recorded shifts, not factory completeness.
- Purple changeover markers appear only for explicitly confirmed events. A
  product code difference alone does not create a marker.
- Machine trends aggregate recorded products for the selected machine and shifts.
  They do not automatically rank machines or label a low-output machine as underperforming.

Date, shift, machine, report, and trend selections persist in the URL so a
refresh restores the current view. Use the refresh button after a new import.
This restores selections, not unsaved form edits or the exact scroll position.

### PDF and HTML reports

Download the current daily report or machine trend report as **PDF or HTML**.
Exports follow the selected date, shift, machine, period, and trend metric where
applicable, and include charts and full data tables. PDF generation is deferred
until the download button is clicked. Longer reports use multiple pages.

PDF generation uses ReportLab locally, without an external conversion service.
On macOS it embeds the installed Arial Unicode font when available; other
platforms use a CJK font fallback. Local PDF rendering and downloads have been
checked; font rendering in the latest cloud build has not been verified.

## Quick Start

Use Python 3.10 or later. Run the following from this directory, or first enter
`manufacturing-ai-agent/` from the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python init_db.py
python seed_data.py
python -m streamlit run streamlit_app.py --server.address 127.0.0.1 --server.port 8502
```

Open [http://127.0.0.1:8502](http://127.0.0.1:8502) on the computer running the
service. This loopback address does not provide access from another computer.
Keep the service running while using the site.

`init_db.py` creates missing enterprise demo tables without removing existing
data. `seed_data.py` inserts missing simulated records and preserves existing
records. These commands **do not restore real production observations**.
A fresh clone has no slitting history; import reviewed data to use the production
reports. The order progress demo can be explored without importing production data.

Runtime dependencies are pinned in [requirements.txt](requirements.txt):
Streamlit 1.65.0 and ReportLab 4.5.1. SQLite is part of Python. The import and
standalone HTML report scripts use only the Python standard library.

Optional database checks:

```bash
python verify_db.py
python main.py
```

`verify_db.py` prints the five enterprise demo tables; it is not a production
history export. `main.py` checks that the enterprise tables are initialized.

## Production Data Workflow

```text
Daily screenshots supplied by the user
    -> Review date, shift, machine, product, and values in conversation
    -> Save reviewed JSON and original screenshots locally
    -> Validate and import into SQLite
    -> Refresh and filter the dashboard
    -> Compare machines, inspect trends, and download reports
```

Import a reviewed JSON list using the existing CLI. Replace the example path
with your actual reviewed file:

```bash
python production.py local_data/reviewed-production.json
```

One observation represents a production date, shift, machine, and product.
Repeated imports of identical records are skipped. Conflicting values for an
existing key reject the batch instead of silently overwriting it. Production
dates and shift assignments follow the user's confirmed business date; the
system does not guess how an overnight shift should be assigned.

See [PRODUCTION.md](PRODUCTION.md) for the complete JSON format, validation,
source metadata, and offline HTML report commands. The password-controlled
web importer accepts reviewed JSON or recovery bundles; it does not accept
screenshots for automatic transcription.

### Data interpretation

- Missing records are not zero output. Explicit zero observations remain zero.
- Input rolls and finished rolls are different units; dividing them does not
  establish yield.
- Reported yield retains the source value. Its original formula is not known,
  so the dashboard does not infer aggregate yield.
- Area not recorded as qualified is not automatically classified as scrap.
- Recorded production does not establish theoretical capacity, machine state,
  utilization, or a complete factory operating plan.

## Order Analysis and Progress Demo

The order analysis page contains two tabs:

| Tab | Current behavior |
| --- | --- |
| Order progress demo | Four isolated synthetic orders, with required rolls, accumulated qualified finished rolls, remaining rolls, completion percentage, progress bar, cumulative chart, and shift/machine details |
| Original order analysis | Lookup of seeded enterprise orders and BOM-based material requirements, available stock, and shortages |

The default synthetic order, **DEMO-001**, requires **1,000 finished rolls** and
has **650 qualified finished rolls**, leaving **350 rolls** and **65% completion**.
Try another order or change the target to explore no production, completion,
overproduction, or a zero target. Date labels on the cumulative chart are horizontal.

For the demo:

```text
Completed rolls = sum of qualified finished rolls assigned to that synthetic order
Remaining rolls = max(required rolls - completed rolls, 0)
Completion rate = completed rolls / required rolls
```

A zero target makes the rate and remaining demand unavailable. Above 100%, the
percentage and excess rolls remain visible while the progress bar stops at 100%.
Target edits are stored only for the current session. Demo data is defined in
`order_progress_demo.py`; it does not read or write real production records.
Real production has not been allocated to real orders, and production completion
does not indicate shipment or delivery.

Original order analysis uses simulated enterprise data. For each BOM material:

```text
Required = ceil(order quantity * material quantity per unit)
Available = max(current stock - safety stock, 0)
Shortage = max(required - available, 0)
```

This is a material requirement illustration, not an automated purchasing or
scheduling system. Seeded orders, BOMs, inventories, machine settings, and supplier
lead times are demonstration data and are separate from production observations.

## Storage, Privacy, and Cloud Use

The app resolves `manufacturing.db` beside `database.py`. Production observations
and enterprise demo tables occupy different tables in that database. Synthetic
order progress examples remain in code and session memory.

The following stay outside Git: `manufacturing.db`, other local database files,
`local_data/` (reviewed JSON, screenshots, backups, and recovery bundles),
`reports/`, virtual environments, `.env`, and `.streamlit/secrets.toml`.
Back these up separately; cloning the source repository does not restore them.

A private Streamlit Community Cloud app has been deployed from
`manufacturing-ai-agent/cloud_entry.py` in this repository. Viewer access is
controlled by the hosting platform; the import password separately protects
reviewed data uploads. Do not make production records public.

Cloud local files are temporary and can be lost on restart or rebuild. The
cloud entrypoint creates enterprise demo tables if no database exists; it does
not automatically recover production history from a local computer. Retain the
local recovery bundle and restore it through the reviewed import workflow when
needed. See [DEPLOYMENT.md](DEPLOYMENT.md) for configuration and recovery steps.
The latest source has been synchronized to GitHub; the latest cloud build and
its retained data have not been verified.

## Project Modules and Data Tables

| File | Responsibility |
| --- | --- |
| `streamlit_app.py` | Production dashboard, filters, report downloads, and order analysis |
| `production.py` | Production record validation and atomic JSON import |
| `production_dashboard.py` | Shared filtering, sums, weighted ratios, machine totals, and coverage |
| `production_report.py` | Daily HTML report and machine comparisons |
| `production_trends.py` | 7/30-day machine history and confirmed changeover markers |
| `production_pdf.py` | Daily and trend PDF generation |
| `order_progress_demo.py` | Synthetic order progress examples and session-only target edits |
| `cloud_data.py` / `cloud_import_ui.py` | Reviewed JSON/recovery import and export, with password-controlled uploads |
| `cloud_entry.py` | Hosted entrypoint and initial enterprise demo setup |
| `database.py` | SQLite location, connection, and enterprise schema checks |
| `init_db.py` / `seed_data.py` | Non-destructive creation and seeding of enterprise demo tables |
| `verify_db.py` / `main.py` | Enterprise demo inspection and readiness checks |
| `.streamlit/config.toml` | Light theme configuration |

| Table | Purpose |
| --- | --- |
| `slitting_records` | Reviewed production observations; unique by production date, shift, machine, and product, with source metadata |
| `changeover_events` | Optional, explicitly confirmed changeovers by date, shift, and machine |
| `orders` | Simulated order ID, product, quantity, due date, and priority |
| `machines` | Simulated machine settings; not authoritative operating status for production records |
| `inventory` | Simulated material stock and safety stock |
| `bom` | Simulated product/material quantities per unit |
| `suppliers` | Simulated supplier lead times and minimum order quantities |

BOM and supplier material IDs reference inventory. The enterprise seed provides
3 orders, 7 demo machine settings, 4 materials, 8 BOM entries, and 4 supplier
entries. Observed production machine IDs are not limited to this demo machine list.

## Validation

Run the complete existing suite from this directory with dependencies installed:

```bash
.venv/bin/python -B -m unittest test_production.py test_dashboard.py test_cloud_data.py test_pdf.py test_order_progress.py -v
```

These five modules cover imports and conflicts, aggregation and filters, trend
gaps and confirmed changeovers, recovery bundles, PDF generation, and synthetic
order progress. The last recorded run passed **19 tests**. A documentation update
does not imply that the application or cloud deployment has been tested again.

## Current Boundaries

Automatic screenshot recognition, live MES/machine integration, automatic
production-to-order allocation, AI-generated analysis, scheduling optimization,
and procurement execution are not implemented. They are possible future work,
not capabilities of the current release.
