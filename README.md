# Manufacturing Progress Assistant

The current development focus is the **Manufacturing AI operations web preview**,
with Next.js, React, TypeScript and FastAPI over the existing Python calculations
and SQLite records. The Streamlit production viewer remains available as a
fallback, alongside the original Flask task tracker at the repository root.

| Application | Location | Purpose | Local address |
| --- | --- | --- | --- |
| **Manufacturing AI web preview** | [`manufacturing-ai-agent/frontend/`](manufacturing-ai-agent/frontend/) + [`backend/`](manufacturing-ai-agent/backend/) | Production analytics, read-only AI tools, scenario planning and cited SOP retrieval | `http://127.0.0.1:3000/dashboard` |
| Production Data Viewer Agent (Streamlit) | [`manufacturing-ai-agent/`](manufacturing-ai-agent/) | Reviewed slitting data, import, machine trends, order demo and report downloads | `http://127.0.0.1:8502/` |
| Original Manufacturing Progress Assistant | Repository root | Manufacturing project and task progress tracking | `http://127.0.0.1:5000/` |

## Enterprise web preview

Seven pages cover Dashboard, AI Production Expert, Production Monitoring,
Production Planning, Inventory Management, Knowledge Base and Settings. FastAPI
reuses deterministic production and abnormality calculations in Python; browser
code does not duplicate business math. Existing historical FX8 records remain
available alongside FX1-FX7, while machines without records stay unconnected.

- Filter by dates, machine, shift and product; reviewed history and synthetic
  demonstrations are separate sources. Missing data is never filled with zero.
- Use explicit minutes, cycle time, machine count, units and yield to compare
  capacity scenarios. These are assumptions, not measured plant capacity or a
  validated optimal schedule. Inventory is an isolated synthetic example.
- Upload text-based PDF, DOCX, TXT or Markdown to a separate Chroma knowledge
  index. Default local vectors are lexical hashes, not learned semantic models;
  answers quote relevant evidence with document and page/paragraph citations.
- Optional OpenAI Agents SDK tool selection and semantic API embeddings require
  server-side credentials and explicit permission. Default local tools and
  retrieval work without a key. Retrieved tool content is not sent to an LLM for
  an additional synthesis call in this first release.
- Account/notification controls are placeholders. Authentication/RBAC, live MES
  or ERP connectivity, actual work-order allocation, grounded LLM synthesis and
  real inventory transactions are not implemented. Keep this preview local.

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

From `manufacturing-ai-agent/`, set up **Python 3.12** and **Node 24**:

```bash
python3.12 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt
cd frontend
npm ci
cd ..
```

Then run these commands in separate terminals from `manufacturing-ai-agent/`:

```bash
bash scripts/start_backend.sh
```

```bash
bash scripts/start_frontend.sh
```

API docs: <http://127.0.0.1:8000/docs>. Optional configuration belongs in
`backend/.env`, using the committed placeholder example; never put a key in a
browser variable. See the [enterprise architecture, Windows setup and validation
guide](manufacturing-ai-agent/docs/ENTERPRISE.md) and
[application README](manufacturing-ai-agent/README.md). Production databases,
reviewed imports, screenshots, extracted company documents and secrets are not
included in this repository. A clone starts without private production history.
Publishing this code does not configure external Next.js/FastAPI hosting.

## Preserved Streamlit Slitting Dashboard

The Dashboard is designed for industrial engineers and production managers who need to review recorded production and compare machines such as FX1 and FX2. It preserves the reported measurements and lets users interpret the results without automatic equipment rankings or performance alerts.

### Production data for each machine

- Planned input rolls and actual input rolls
- Qualified finished rolls
- Actual output area and qualified output area, in square meters
- Input plan attainment and area qualification rate
- Original reported yield, retained at record level without an inferred aggregate

Input rolls and qualified finished rolls represent different production units. They are not interchangeable.

### Viewing, comparison, and trends

- Calendar date selection, all/day/night shift selection, and individual/all-machine filters
- Overall qualified output area, input plan attainment, area qualification rate, and recorded machine count
- Machine comparisons for planned versus actual input and actual versus qualified output area
- Rolling **7-day and 30-day trends**, with the selected report date as the inclusive end date
- A dashed plan line alongside actual input; All, Day, and Night modes connect recorded dates across gaps using true calendar spacing
- No points, zeros, or estimates added for missing dates; indicators identify incomplete shift coverage
- Confirmed changeovers always shown as purple dashed lines, outlined circles, and short chart labels; **Show changeover details** reveals the below-chart descriptions, which are hidden by default. Events are never inferred from product-code differences or deleted when descriptions are hidden
- Raw production details by machine, product, and shift
- Filter and changeover-detail selections retained in the URL across refreshes
- **PDF and HTML downloads** for the current daily report and trend selection; trend exports retain confirmed changeover markers, follow the detail-display selection, and keep the same recorded-date connection rule for every shift selection

Input plan attainment is total input rolls divided by total planned rolls. Area qualification rate is total qualified output area divided by total actual output area. Aggregate percentages use ratios of sums; zero denominators are unavailable, and missing observations are not filled with zeros. Recorded machine count describes records, not running status or utilization.

### Data workflow

Production screenshots are reviewed in conversation, transcribed into JSON, and imported into SQLite after the date, shift, and figures are checked. The importer skips identical records and rejects conflicting batches rather than silently overwriting production data.

For future imports, retain verified numeric JSON, SQLite records, source notes, and numeric backups or recovery bundles without copying new screenshots into the project. Preserve the original source filename, date, shift, units, conversions, and confirmations as text; a source filename does not guarantee a local image file. Existing images and historical backups remain unchanged, as do originals outside the project.

The application does not perform automatic image recognition or live equipment collection. Its optional floating AI assistant reads reviewed numeric facts and does not change production data. Production databases, source metadata, and private import or recovery files stay outside the source repository and need separate backups. **A clone does not contain the user's production history.**

### Optional Streamlit AI Production Assistant

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

The assistant supports production lookup, machine comparison, daily observations,
recorded shift coverage, confirmed changeovers, and summaries. Choose a date range
of up to 30 days, All/Day/Night, and multiple machines; an empty machine selection
means all observed machines. Existing business functions remain available.

The model chooses a permitted read-only query and relevant fact IDs and order.
Python generates the displayed factual sentences and numbers using the same
calculations as the Dashboard. Answers show query scope and evidence; local
summary tables, coverage, and expandable records remain available without AI.
The model cannot execute arbitrary SQL or write the database. Missing records
are not zero, and the assistant does not infer causes, utilization, scrap,
capacity, purchasing decisions, or events from product-code differences.

The optional connection uses the official OpenAI Python SDK and Responses API,
`gpt-6-luna`, `reasoning.effort="none"`, and `store=False`. Configure the server's
`OPENAI_API_KEY` through its environment or Streamlit Secrets using the
[placeholder example](manufacturing-ai-agent/.streamlit/secrets.toml.example).
Preserve existing Secrets, including the import password; never commit a real
key. Account registration, billing, and project usage controls are user steps.
Without a key, the page explicitly reports that AI is not configured.

Only an actively submitted question with permission enabled invokes the API.
The first question stays local until explicit approval; changed scope or data
resets permission. Settings hold optional scope and evidence controls.
It sends the question, scope, definitions, necessary numeric summaries/coverage,
and confirmed-event dates plus from/to products. Raw records stay local by
default. Database files, screenshots, source filenames/notes, paths, confirmation
notes, credentials, synthetic enterprise data, and full chat history are excluded.
OpenAI does not use API data for training by default, but abuse-monitoring logs
may remain for up to 30 days, with policy exceptions. `store=False` does not
promise zero retention; review the official
[data policy](https://developers.openai.com/api/docs/guides/your-data).

Each question allows at most two requests, no SDK retries, a 1,000-character
question, a 32-KiB complete input package per request, and 1,000 output tokens per
request. Request timeouts are at most 30 seconds within a 60-second total deadline.
Only current-session results are cached, with scope, model, question, and data
version in the key. These limits do not guarantee costs or response speed.

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

The local project driver document records detailed execution results. See the
[full assistant guide](manufacturing-ai-agent/README.md#ai-production-assistant)
for setup, privacy, request controls, and validation boundaries.

### Start the Dashboard

On macOS or Linux, from the repository root:

```bash
cd manufacturing-ai-agent
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 init_db.py
python3 seed_data.py
python3 -m streamlit run streamlit_app.py --server.address 127.0.0.1 --server.port 8502
```

Open [http://127.0.0.1:8502/](http://127.0.0.1:8502/). These initialization commands belong to the **subdirectory application**: they create its schema and add simulated enterprise reference data while preserving existing records. They do not load real slitting production observations.

The Dashboard uses Python, Streamlit, SQLite, and ReportLab, with the official `openai` SDK for the optional assistant. Its dependencies are in `manufacturing-ai-agent/requirements.txt`; the root requirements file is for the separate Flask application. The loopback address above is accessible on the computer running the server. Private cloud setup uses a separate entrypoint and configuration, described in the deployment guide; source synchronization alone does not verify a hosted release.

### Supporting order analysis

The Dashboard retains the existing order and BOM analysis and adds an isolated **order progress demo**. Four synthetic orders demonstrate qualified finished rolls versus demand, remaining rolls, completion percentage, a progress bar, a cumulative chart with horizontal date labels, and shift/machine details. A session-only target editor demonstrates completion, overproduction, and zero demand.

Demo production is not allocated from real slitting records and does not update the production database. Connecting actual production to real customer orders requires order requirements and an agreed production-allocation rule.

### Documentation and checks

- [Dashboard setup, features, and module guide](manufacturing-ai-agent/README.md)
- [Production JSON import, metrics, and report behavior](manufacturing-ai-agent/PRODUCTION.md)
- [Private cloud access, import, and recovery](manufacturing-ai-agent/DEPLOYMENT.md)

From `manufacturing-ai-agent/`, run the regression suite:

```bash
.venv/bin/python -B -m unittest test_production.py test_dashboard.py test_cloud_data.py test_pdf.py test_order_progress.py test_ai_production_data.py test_ai_production_client.py test_ai_production.py test_ai_floating_panel.py test_abnormality.py test_production_diagnostics.py test_planning_data_contracts.py -v
```

## Original Flask Task Tracker

The original local MVP tracks manufacturing projects, procurement, engineering, production issues, audits, and SAP/BOM progress. It uses Flask 3.0.3, SQLite, HTML/CSS, and Bootstrap. Its query page uses simple keyword matching rather than an LLM.

### Features

- Dashboard with total tasks, status counts, overdue tasks, and recently updated tasks
- Add, view, edit, and delete manufacturing progress tasks
- Task list with status, priority, due date, and action buttons
- Natural-language-like queries using keyword matching
- Weekly report with active, completed, blocked, overdue, supplier, and high-priority summaries
- Sample tasks illustrating manufacturing operations

### Start the Flask application

Use a separate environment at the **repository root**, outside `manufacturing-ai-agent/`:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

For a new sample task database, run:

```bash
python3 init_db.py
```

**The root `init_db.py` drops and recreates the `tasks` table before inserting sample tasks. Run it only when intentionally initializing or resetting sample tasks. Skip it when preserving existing tasks.** This behavior differs from the subdirectory application's initializer.

Start the tracker:

```bash
python3 app.py
```

Open [http://127.0.0.1:5000/](http://127.0.0.1:5000/).

### Example queries

- What is the status of film rack purchase?
- Which tasks are blocked?
- What tasks are waiting for supplier?
- Show overdue tasks
- How is customer audit preparation progressing?
- SAP BOM progress
- Material change progress

### Repository layout

```text
manufacturing-progress-assistant/
|-- README.md
|-- app.py                      # Original Flask tracker
|-- requirements.txt            # Flask dependencies
|-- init_db.py                  # Reset and seed the sample task table
|-- templates/                  # Flask pages
|-- static/                     # Flask styles
`-- manufacturing-ai-agent/
    |-- README.md               # Production Dashboard guide
    |-- streamlit_app.py         # Local Streamlit entrypoint
    |-- cloud_entry.py          # Hosted entrypoint
    |-- production.py           # Validated production JSON import
    |-- production_dashboard.py # Shared filtering and metrics
    |-- production_report.py    # Daily HTML reports and comparisons
    |-- production_trends.py    # Machine history and confirmed changeovers
    |-- production_pdf.py       # Daily and trend PDF generation
    |-- order_progress_demo.py  # Isolated synthetic order progress
    |-- ai_production_data.py   # Read-only production queries and verified facts
    |-- ai_production_client.py # Bounded OpenAI Responses API adapter
    |-- ai_production_ui.py     # Embeddable assistant content and permission
    |-- ai_floating_panel.py    # Global floating assistant and legacy-link migration
    |-- ai_floating_panel.css   # Scoped panel styling
    |-- ai_floating_panel.js    # Layout-only dragging and viewport bounds
    `-- requirements.txt        # Dashboard, reports, and official OpenAI SDK
```

### Future ideas for the original tracker

Potential future work includes Teams, SharePoint, or Outlook connections; LLM-assisted queries; login and permissions; overdue-task reminders; and additional weekly-report export formats. These are ideas, not implemented integrations.

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

Synthetic JSON format: [abnormalities-demo.json](manufacturing-ai-agent/examples/abnormalities-demo.json).


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
