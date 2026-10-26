# Manufacturing AI / Production Data Viewer Agent

A production data application for industrial engineers and production managers,
with a **Next.js / React / TypeScript** web preview and **FastAPI / Python / SQLite**
data services. Its current focus is slitting machine input, output, production
history, recorded abnormalities and clear machine comparisons.

The original **Streamlit** viewer remains available with reviewed JSON import,
order-progress demonstrations, report downloads and its floating AI assistant.
The newer English web interface adds scenario tools and cited knowledge retrieval;
the preserved Streamlit interface uses primarily Chinese labels.

Production calculations are deterministic Python functions. The application does
not recognize screenshots, collect live machine signals or autonomously change
production records. Real production history and credentials are not included in
the repository; a clone starts without private data.

## New enterprise web preview (local first release)

A new **Next.js / React / TypeScript** interface connects to **FastAPI** while
reusing the existing SQLite records and deterministic Python calculations.
Seven pages cover Dashboard, AI Production Expert, Production Monitoring,
Production Planning, Inventory Management, Knowledge Base and Settings.
Streamlit and its existing production/import/order/download features remain
available as a fallback. No production database migration is required.

- Reviewed historical production is separate from synthetic demonstrations.
- Python tools calculate explicit capacity/forecast scenarios; missing measured
  cycle time, utilization and real capacity remain unavailable.
- Knowledge uploads support PDF/DOCX/TXT/Markdown with source locations, Chroma
  indexing and local extractive answers. Default hash vectors are lexical;
  optional semantic API embeddings require consent.
- One optional OpenAI Agents SDK selects shared read-only tools. No key is needed
  for local views, calculations or default retrieval. No machine control or
  autonomous orders/inventory actions are available.
- Authentication, live MES/ERP feeds, real scheduling and grounded LLM synthesis
  are not yet implemented. Keep the development services on localhost.

### Current Dashboard behavior

- Use calendar dates or 7-/30-day presets, with machine, shift, product and
  historical/demo filters retained in the URL across refreshes.
- Review planned and actual input, input plan attainment, qualified output and
  recorded abnormality minutes. Missing measured cycle time, utilization and
  capacity are explicitly unavailable; scenario results are separate.
- The full-width input chart uses a blue solid actual line and a slate dashed
  plan reference. Every non-null value, including an explicit zero, is labeled.
  Weekly labels identify Actual/Plan; longer ranges use colour-matched compact
  numbers. Hover shows both exact counts, the full date and mother-roll units.
- Labels follow their own points: the higher value is above, the lower below;
  equal values put plan above and actual below. Dense charts scroll horizontally
  instead of dropping labels. Dates remain horizontal and use true calendar spacing.
- Connect existing observations across missing dates without adding zeros,
  estimates or extrapolated points. First/last recorded dates and a collapsible
  missing-date list describe only the current filter.
- Selecting one machine retains confirmed purple changeover lines and rings.
  Short labels use a separate event band; detailed explanations start collapsed.
  Product text differences do not automatically create changeovers.
- Expand **View all recorded values** for the complete date/actual/plan table.
  **Machine performance records** also starts collapsed and retains every existing
  column and unavailable value. Collapsing tables does not hide chart points.
- Compare actual and qualified output by machine and recorded abnormality minutes
  by category. Export the current selection as PDF or HTML. No automatic machine
  ranking, loss attribution or root-cause conclusion is generated.

The latest Dashboard changes passed 14 layout tests, 13 existing production and
Dashboard regressions, TypeScript checks and a production build. Server-rendered
markup was checked with controlled chart props; browser pixel/layout and actual
mouse/keyboard interaction acceptance remain pending. These checks do not
establish hosted behavior or live-model answer quality.

Start from this repository with **Python 3.12** and **Node 24**:

```bash
# One-time setup; this environment is independent of the original .venv
python3.12 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt
cd frontend && npm ci
```

Then run two terminals from the repository root:

```bash
bash scripts/start_backend.sh
bash scripts/start_frontend.sh
```

Open <http://127.0.0.1:3000/dashboard>. API docs are at
<http://127.0.0.1:8000/docs>; Streamlit stays at <http://127.0.0.1:8502/> when its
original process is running. See [the enterprise guide](docs/ENTERPRISE.md) for
Windows commands, server configuration, calculations, tests and current limits.
Never commit actual `.env`, keys, SQLite files, extracted documents or company
records. The remainder below describes the preserved Streamlit functionality.

## Preserved Streamlit Slitting Dashboard

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
- In **All**, **Day**, and **Night** modes, actual and planned lines connect
  consecutive recorded dates, including across missing dates, with true calendar
  spacing. Missing dates have no points, zeros, or estimated values.
  A single recorded date remains a point; lines are not extrapolated.
- In all-shift views, an orange point identifies a date with only one recorded
  shift. Coverage messages describe recorded shifts, not factory completeness.
- Confirmed changeovers always retain their **purple dashed lines, outlined
  circles, and short chart labels** under the current date, machine, and shift
  filters. The detailed description list below each chart is **hidden by default**;
  enable **Show changeover details** to display it. Chart hover information remains
  available. Product-code differences alone do not create events, and hiding
  descriptions does not remove stored events.
- Machine trends aggregate recorded products for the selected machine and shifts.
  They do not automatically rank machines or label a low-output machine as underperforming.

Date, shift, machine, report, trend, and changeover-detail selections persist in
the URL so a refresh restores the current view. Use the refresh button after a new import.
This restores selections, not unsaved form edits or the exact scroll position.

### PDF and HTML reports

Download the current daily report or machine trend report as **PDF or HTML**.
Exports follow the selected date, shift, machine, period, and trend metric where
applicable, and include charts and full data tables. Trend HTML and PDF exports
always include confirmed changeover lines, circles, and short labels; their
below-chart descriptions follow **Show changeover details**. Both formats retain
the same recorded-date connection rule for every shift selection.
PDF generation is deferred until the download button is clicked. Longer reports
use multiple pages.

PDF generation uses ReportLab locally, without an external conversion service.
On macOS it embeds the installed Arial Unicode font when available; other
platforms use a CJK font fallback. Local PDF rendering and downloads have been
checked; font rendering in the latest cloud build has not been verified.

## Preserved Streamlit AI Production Assistant

The assistant opens as a simple **AI Chat** floating window from the **AI**
button at the bottom right. The default view contains messages and a question
input. Optional date, shift, machine, local-evidence, sending-preview, shortcut,
and configuration controls are grouped under the single **Settings** button.
Returning from settings restores chat; closing and reopening starts in chat view.

It is available on the daily Dashboard, order analysis, and reviewed-data import
screens, including empty or locked states. Close it to collapse it, drag its title
to move it, or focus the title and use arrow keys. Escape on the title also closes
it. The panel scrolls independently and stays inside the viewport when resized.

The first question is staged locally until the user reviews the production scope
and chooses **Allow and send** or **Cancel**. Staging or canceling makes no model
request. Permission is remembered only for the unchanged context and can be
revoked in settings. Changing scope or data clears old answers/cache, discards
pending questions, and resets permission. Answers display the actual query scope.

The assistant keeps its own production scope. In settings, **Use current
production filters** adopts the current daily date or 7/30-day interval, shift,
and machine only when clicked. Navigation does not change this scope or read
order-demo/import contents. Opening, closing, moving, filtering, and navigating
do not invoke a model. Closing/reopening or switching business pages preserves
chat, scope, pending questions, and permission/cache for the unchanged context in
the same session. A browser reload can start a new session and is not a chat backup.

The sidebar retains only the three business entries. An old
`page=AI Production Assistant` URL opens the Dashboard and expands the panel.
Only panel coordinates are stored in browser session storage, never credentials,
production values, or chat. Keys and model calls remain on the Python server.

It supports production questions, side-by-side machine comparison, daily
observations, recorded shift coverage, confirmed changeovers, and short summaries.
The existing Dashboard, trends, orders, import, and downloads remain available.

Type a question directly, up to **1,000 Unicode characters**. The default
scope is the latest seven days, all observed machines and shifts; settings can
select up to **30 days**, **All / Day / Night**, and multiple machines. An empty
machine selection means all observed machines. Ordinary filtering or refreshing
does not invoke a model.

### Answers backed by local facts

Read-only tools query reviewed production observations, explicitly confirmed
changeovers, and reviewed abnormality aggregates. They reuse the Dashboard's sums, ratios of sums, and coverage rules.
SQLite connections use read-only mode and `query_only`; the model cannot run
arbitrary SQL, Python, imports, file access, network tools, or database writes.

The model chooses an allowed query and selects relevant fact IDs and their
order. **Python generates the displayed factual sentences and numbers.** The
assistant shows the actual query scope and coverage with answers; settings
provide the query details, local evidence tables, and expandable records. It does not display unrestricted model prose or invented
numeric conclusions. Unsupported or ambiguous requests ask for clarification
rather than silently expanding the selected scope.

Missing observations are not zero production. Zero denominators are unavailable.
Neither an observed product-code change nor a model suggestion creates a
changeover event. The assistant does not infer unknown yield formulas, scrap,
machine operating status, utilization, causes, future capacity, delivery dates,
or purchasing decisions. Synthetic order data is outside this assistant's scope.

### Configure the optional API connection

The default connection uses the official OpenAI **Responses API** at
`https://api.openai.com/v1/responses`, model **`gpt-6-luna`**, Standard mode,
`reasoning.effort="none"`, and `store=False`. It does not silently switch models
or use a third-party API proxy. Account/model access and actual response quality
must be checked with the user's own account.

Create and fund an API account yourself, configure project usage controls, and
create an API key. Keep the key out of chat, source control, URLs, and logs. The
server reads `OPENAI_API_KEY` from its environment or Streamlit Secrets only.
See [the configuration example](.streamlit/secrets.toml.example). For local
Secrets, manually add its placeholder setting to `.streamlit/secrets.toml` and
replace the placeholder privately. **Do not replace an existing Secrets file or
remove existing settings such as `admin_import_password`.** The real Secrets
file remains ignored by Git. No key-entry widget is provided in the app.

Without a key, the page explicitly reports **AI not configured** and makes no
model request. Local facts remain available; a template is not presented as a
successful AI answer. Authentication errors, unavailable models, timeouts,
oversized requests, and invalid responses display a failure or clarification
state. No automatic paid retry or more expensive model fallback occurs.

### Sending, retention, and request limits

Only an actively submitted question with permission enabled can send data to
OpenAI. The preview describes the selected dates, shifts, machines, numeric
fields, and confirmed-event fields. The allowed input contains the question,
metric definitions, selected scope, necessary production summaries, coverage,
and confirmed event dates plus from/to products. Raw production details stay
local by default. Database files, screenshots, source filenames, notes, file
paths, confirmation notes, credentials, synthetic orders, inventories, BOMs,
suppliers, and full chat history are excluded from model input.

Each question permits at most **two model requests**, with SDK retries disabled
(`max_retries=0`). Each request's complete UTF-8 model-input package is limited
to **32 KiB**, including instructions, tool definitions, arguments, and results;
reduce the selected range if the limit is exceeded. Each request has at most
**1,000 output tokens** and a **30-second** timeout, within a **60-second** total
answer deadline. Errors or timeouts do not guarantee that no API charge occurred.
API usage returned by the service is available for checking. These application
limits do not replace account billing controls or guarantee an account spend cap.

Identical requests may reuse a cache in the **current session only**, keyed by
question, filters, model configuration, and data version. Data or scope changes
invalidate the relevant state; results are not shared across users. Refreshing
the browser does not promise to preserve the assistant's chat or session cache.

OpenAI API data is not used for training by default, but abuse-monitoring logs
may be retained for up to 30 days, with policy exceptions.
**`store=False` does not mean zero data retention.** Review the official
[data policy](https://developers.openai.com/api/docs/guides/your-data) before
enabling production-data sending. Setup and service details are in the official
[API quickstart](https://developers.openai.com/api/docs/quickstart),
[Python SDK guide](https://developers.openai.com/api/docs/libraries),
[model page](https://developers.openai.com/api/docs/models/gpt-6-luna),
[pricing](https://developers.openai.com/api/docs/pricing), and
[spend-limit guide](https://developers.openai.com/api/docs/guides/spend-limits).

The floating assistant is implemented locally under PLAN-017 v1. See
[Validation](#validation) for this round's automated and browser checks and the
remaining real-model acceptance boundary.

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
Streamlit and ReportLab serve the Dashboard and exports; the optional assistant
uses the official `openai==3.31.0` SDK. SQLite is part of Python. The import and
standalone HTML report scripts continue to use only the Python standard library.

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
    -> Save reviewed numeric JSON and source notes locally
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

### Source retention

For future imports, review the screenshot in conversation, then retain the verified
numeric JSON, SQLite records, source notes, and numeric backups or recovery bundles.
Do not copy or back up new screenshot files into the project after review. This is
a manual import practice; the application does not automatically transcribe or
delete images.

Keep the original filename in `source_name`, and preserve the source report date,
shift label, units, conversions, and user confirmations in the source fields and
notes. Record that no project image copy is retained; a filename is provenance,
not a guaranteed local image path. Reports and charts read the numeric records.

This policy applies to future batches. Existing project images and historical
backups remain unchanged, as do the user's chat attachments and other originals.
Retain separate backups of the numeric data for recovery. Without a project image
copy, later source checks rely on the reviewed transcription, notes, and any
originals the user keeps elsewhere.

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
`local_data/` (reviewed JSON, source metadata, numeric backups, recovery bundles,
and previously retained images), `reports/`, virtual environments, `.env`, and
`.streamlit/secrets.toml`. Back up the database, reviewed JSON, source notes, and
recovery bundles separately; cloning the source repository does not restore them.
Future imports do not add screenshot copies to the project.

A private Streamlit Community Cloud app has been deployed from
`manufacturing-ai-agent/cloud_entry.py` in this repository. Viewer access is
controlled by the hosting platform; the import password separately protects
reviewed data uploads. Do not make production records public.

Cloud local files are temporary and can be lost on restart or rebuild. The
cloud entrypoint creates enterprise demo tables if no database exists; it does
not automatically recover production history from a local computer. Retain the
local recovery bundle and restore it through the reviewed import workflow when
needed. See [DEPLOYMENT.md](DEPLOYMENT.md) for configuration and recovery steps.
The latest trend-display changes are local only and have not been synchronized
to GitHub. The latest cloud build and its retained data have not been verified.

## Project Modules and Data Tables

| File | Responsibility |
| --- | --- |
| `streamlit_app.py` | Production dashboard, filters, report downloads, order analysis, and assistant navigation |
| `ai_production_data.py` | Read-only production/abnormality queries, shared calculations, full local tables, and transport allowlist |
| `abnormality.py` | Reviewed-event schema/validation, duplicate protection, reported-minute summaries and time-quality checks |
| `ai_production_charts.py` | Local bar specifications, enlarged views, result tables and safe CSV |
| `ai_production_client.py` | Bounded OpenAI Responses API adapter, permitted tool/fact selection, and explicit error handling |
| `ai_production_ui.py` | Simple chat, optional settings, staged sending approval, durable scope, and session cache |
| `ai_floating_panel.py` / `.css` / `.js` | Global fragment, sidebar-link migration, floating layout, bounded dragging, and layout-only browser storage |
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
| `.streamlit/secrets.toml.example` | Placeholder-only API key configuration; never copy over existing Secrets |

| Table | Purpose |
| --- | --- |
| `slitting_records` | Reviewed production observations; unique by production date, shift, machine, and product, with source metadata |
| `abnormality_events` | Reviewed event IDs, business dates, nullable shifts/times/minutes, category, event status and local provenance |
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

For the current web Dashboard, run from `frontend/`:

```bash
node --test tests/trend-layout.test.mjs
npm run typecheck
npm run build
```

The current update passed 14 layout tests and 13 production/Dashboard regressions.
TypeScript and production build checks also passed. Browser visual and actual
disclosure interaction acceptance remain pending. The older browser checks below
refer to earlier Streamlit work, not the latest Next.js Dashboard.

Run the complete preserved Python suite from this directory with dependencies installed:

```bash
.venv/bin/python -B -m unittest test_production.py test_dashboard.py test_cloud_data.py test_pdf.py test_order_progress.py test_ai_production_data.py test_ai_production_client.py test_ai_production.py test_ai_floating_panel.py test_abnormality.py test_production_diagnostics.py test_planning_data_contracts.py -v
```

The original five modules cover imports and conflicts, aggregation and filters,
trend gaps and confirmed changeovers, recovery bundles, PDF generation, and
synthetic order progress. The assistant test modules add synthetic-data tool
checks, mocked API/client limits, UI permission/cache checks, and floating-panel
state/navigation regressions. They must not
use real production records or make paid model calls.

Historical Streamlit validation (PLAN-018 v2) passed **94 tests** (the previous 71 plus 23
abnormality/import/query/chart/UI regressions). Tests use synthetic SQLite data
and mocked model responses, including privacy envelopes, atomic conflicts,
old-bundle compatibility, cross-midnight times, unknown shifts, overlaps, missing
versus zero minutes, weighted production ratios, table/CSV/chart agreement,
explicit table limits, cache invalidation, and long-chat widget uniqueness.
Browser checks used a clearly labeled synthetic preview at 1280 x 720,
1440 x 900, and 1920 x 1080. Device bars, long-category horizontal bars, enlarged
views, internal scrolling, cross-page chat, and an actual CSV download were
checked. No real model request was made; live model selection quality remains
unverified in this round. The production database receives only a new empty table;
existing production/changeover/enterprise rows and source files are preserved.

Previous validation: PLAN-017 v1 passed **71 tests**: the original 60 tests plus
11 floating-panel regressions. These cover global availability, scope adoption,
legacy URLs, close/reopen/navigation state, cache reuse, empty data, data-change
permission reset, the simple chat default, staged-question approval/cancel, and
pending-question preservation. All assistant tests use synthetic SQLite records
and mocked clients; SDK response-object compatibility is tested offline.

The initial floating-panel browser checks covered 1280-, 1440-, and 1920-pixel
desktop widths, including a 720-pixel-high viewport, movement/bounds, calendar
and dropdown layering, scope adoption, navigation, and PDF/HTML downloads. The
simple-chat refinement was checked at 1280 x 720: default view, settings/return,
locally staged first question, cancellation, and close/reopen. No real model
request was made. Production data and dependencies remain unchanged. Whitespace
checks passed; the initial implementation also passed `pip check`.

User acceptance remains pending. This is not a new real-model, account-permission,
cost, latency, or answer-quality acceptance test. Those historical checks did not include a GitHub push or deployment;
local verification does not establish hosted behavior or data.

## Current Boundaries

The optional assistant's implemented scope is read-only query selection and
fact selection, with Python-generated factual sentences and evidence. Real API
and user acceptance remain pending. It does not provide unrestricted AI-written
analysis, autonomous decisions, or root-cause conclusions.

Automatic screenshot recognition, live MES/machine integration, automatic
production-to-order allocation, scheduling optimization, and procurement
execution remain possible future work rather than current capabilities.

## Reviewed Abnormalities and AI Result Tables

PLAN-018 v2 adds independent abnormality-event records to the existing SQLite
database. The initial local migration creates an **empty** table; historical
screenshot timelines have not been backfilled. Production observations and
confirmed changeovers are preserved. Continue the existing workflow: discuss
the screenshot, verify the numbers and business-date/shift attribution, prepare
numeric JSON, then explicitly confirm the import. No automatic image recognition,
device collection, or AI database writes are added. New screenshot copies are
not required; reviewed numeric JSON and source text remain the recovery source.

Each abnormality stores a stable `event_id`, `production_date`, nullable `shift`,
`machine_id`, `category`, `subcategory`, nullable `started_at` and `ended_at`,
nullable `reported_minutes`, `status`, `source_name`, and `notes`. Shifts are
`Day`, `Night`, or `null`; event handling status is `Open`, `Closed`, or `Unknown`.
This is an event status, not an equipment operating state. Times use explicit
local `YYYY-MM-DDTHH:MM[:SS]` values: crossing midnight requires the actual end
date. The importer does not infer dates or shifts from clocks. Missing values
remain null. Complete timestamps also permit an independently displayed interval
in minutes; the original reported minutes are never overwritten.

Import an event-only object containing `abnormality_events`, or add that array
to the existing `records`/`changeover_events` bundle. An event does not require a
matching production row. Reimporting the same ID and values is a no-op; a
conflicting ID rejects the whole batch, including any new production/changeover
rows. Status corrections require a separate reviewed correction and are not
silently applied. Old lists and two-field bundles still work and do not delete
existing abnormalities. Recovery export includes events when the table exists.
The synthetic example below is **only for an isolated test database**, never a
reviewed production import.

The simple AI chat now returns a concise factual summary and a corresponding
local table. It can group production by machine, day, or shift; abnormalities by
machine, day, shift, category, or event detail, with optional category and handling
status filters. A request such as "Plot the recorded abnormality minutes for
each machine in the selected period" produces labeled blue bars, a matching table,
and a CSV download. Long labels or many groups use horizontal bars; the chart
can be enlarged. The chart is drawn locally, with no model-generated code or
image-generation service. Production questions through the original query tool
also receive complete result tables.

Bar heights sum **known reported event-minutes within the chosen period**. This
is not a running cumulative time series or measured net downtime. Tables show
valid/missing-minute record counts; partial sums are identified near the chart.
Entirely missing groups have no invented zero bar; explicitly recorded zero is
retained. Overlap, incomplete timestamps, unconfirmed shifts, and discrepancies
between reported and interval minutes are disclosed under data-quality details.
Unknown-shift events appear only in All-shift queries. Cross-machine totals are
machine-event minutes, not elapsed factory time. The assistant does not infer
root causes, utilization, output losses, or rankings.

All values, table rows, chart bars, and CSV cells come from one read-only snapshot.
The model selects a whitelisted query and program-authored fact IDs. Summaries
may choose up to eight facts; tables are not shortened to that selection. The
new analysis tool offers at most 20 group-summary candidates plus aggregate and
coverage facts; any larger table is explicitly identified. Tables and CSV are
limited to the same first 1,000 rows with an explicit truncation notice; narrow
the scope for the remainder. Excessively large chart-group requests are rejected.
CSV uses UTF-8 with BOM, units in headers, and protects formula-like text labels.

The new model envelope contains only needed aggregate facts, category labels,
counts, and timing-quality statistics. Event IDs, raw timestamps, subcategory
text, source notes, and raw event tables remain local. Opening settings or
viewing local evidence makes no model request. The maximum 30-day scope,
explicit sending approval, official model, request/time/byte limits, and lack of
write tools remain in force. Abnormality changes invalidate chat/cache and reset
approval. No new dependency is required. Existing PDF/HTML reports are retained;
their templates do not yet include these new chat-result charts.

Synthetic JSON format: [abnormalities-demo.json](examples/abnormalities-demo.json).


## Production diagnostics and planning data preparation

The **Production Analysis** entry adds two tabs: **Gaps and Abnormalities** and
**Data Preparation**. Choose an inclusive range of up to 30 dates, a shift, and
machines. The page reads verified production, confirmed changeovers and recorded
abnormalities only; it does not read the simulated enterprise master tables.

Input deviation is actual minus planned **mother-roll input**. Positive means
above plan; negative means below plan. Shortfall and excess are also summed
separately per source observation, so overproduction on another observation does
not erase a shortfall. These are not missing qualified finished rolls or lost
output. Existing weighted area ratios and unavailable zero denominators remain.

Production and abnormality records are aggregated separately before aligning by
date, machine and shift. Multiple events cannot multiply production quantities.
No production record means unavailable production fields. No event record means
not recorded, not zero downtime. Explicit zero-minute events remain zero. Category
shares use known reported event-minutes only; missing minutes are disclosed and a
zero or missing denominator is unavailable. Event totals may overlap and are not
net downtime, utilization or OEE. Product mixes, incomplete shifts, uncertain
intervals and confirmed changeovers remain visible for review. Co-occurrence does
not establish cause or identify a system bottleneck.

Signed input-deviation bars, category-minute bars, percentage tables, evidence
rows and UTF-8 CSV use the same local snapshot. Machine rows follow machine ID,
not a performance ranking. Tables and CSV retain at most 1,000 rows with an
explicit total/truncation message; larger charts require a narrower scope. The
review-clue list contains at most ten dated groups and explicitly points to the
complete evidence table. This page itself makes no model calls.

The existing floating assistant can use the bounded `query_diagnostics` tool for
combined gap/abnormality questions and program-generated tables. Use **Adopt the
current production filters** explicitly in assistant settings to copy analysis
filters. Changing scope, data or tool version resets consent/cache. Existing
30-day, two-request, 32-KiB and timeout limits remain. The external service receives
bounded, question-scoped aggregate facts and coverage, never raw evidence rows, event IDs,
timestamps, products from the evidence table, source notes, files or credentials.
Model execution is optional; numerical analysis works locally without a key.

Data Preparation contains versioned field/unit/relationship descriptions for
capacity and scenario planning, order allocation/completion, and inventory/BOM.
All three remain **awaiting real data**. The downloadable field blueprint and
`examples/planning-data-contracts.json` contain empty record arrays, not fake
business observations, and are **not accepted by the production JSON importer**.
No future business tables or adapters are created in this release. Real runtime,
rate standards, calendars, routing/WIP, order allocations, units and stock data
must be reviewed before enabling their calculations. Simulated orders/inventory
are never substituted. No capacity forecast, actual completion date, bottleneck
ranking, automatic schedule or purchase action is implemented by this framework.

Implementation: `production_diagnostics.py`, `production_diagnostics_ui.py`,
`planning_data_contracts.py`, and the existing bounded data/client/UI modules.
Regression coverage includes `test_production_diagnostics.py` and
`test_planning_data_contracts.py`, with mocked model calls and synthetic data.
