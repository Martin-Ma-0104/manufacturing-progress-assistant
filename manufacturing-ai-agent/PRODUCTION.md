# Daily Slitting Production

This extension stores user-supplied daily production observations separately from
Phase 1 simulated orders, inventory, and machine settings. The JSON importer and
offline HTML reporter use only Python's standard library; neither calls an AI
service or implements automatic image recognition. The optional floating AI assistant
can read production facts with explicit sending permission, as described below.
Numeric screenshot transcription is reviewed in conversation and saved locally.
Future imports retain numeric records and source notes without copying new
screenshot files into the project.

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
`source_name` records the original source filename; it does not require a locally
retained image or an accessible file path. `notes` records transcription context,
units, conversion assumptions, and user confirmations. For future batches, note
that no project image copy is retained. Historical machine IDs do not inherit
current settings from the simulated machine master; an observed machine need not exist there.

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

`local_data/` (including reviewed JSON, source metadata, numeric backups, recovery
bundles, and previously retained images), `reports/`, and the SQLite database are
ignored by Git. Real production records must not be put in seed scripts, tests,
README examples, commits, or public repositories. Back up the database, reviewed
JSON, source notes, and recovery bundles separately; a Git clone alone does not
recover production data. The existing `verify_db.py` prints the five Phase 1
tables; use the production report for daily production details.

### Source retention for future imports

1. Review the supplied screenshot in conversation, including the production date,
   shift, machine, product, values, and units. Confirm any conversion explicitly.
2. Save the verified numeric JSON and necessary source text. Keep the original
   filename, source report date and shift label, transcription notes, and conversion
   or confirmation basis. An optional image digest can identify the source without
   storing its pixels; state that no project image copy is retained.
3. Validate and import the numeric records, then retain database backups and the
   numeric recovery bundle. Do not copy or back up new screenshot files into the
   project. The importer, dashboard, charts, and reports do not need those images.

This is a manual retention practice, not automatic image recognition or deletion.
Existing images and historical backups are left intact. Chat attachments, WeChat
files, and originals elsewhere are outside this policy. Later source checks rely
on the verified numbers, source notes, and any originals the user keeps elsewhere.

## Existing Streamlit web app

The existing optional Streamlit app has a **分切生产日报** sidebar page
(default), retains **订单分析** and **数据导入**, with the **AI** floating button
available across all three business screens. Use the calendar to select a production date,
shift and machine, then view
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
recorded products and selected shifts for a machine/date. In **All**, **Day**,
and **Night** modes, actual and planned lines connect consecutive recorded dates
even across missing dates; the horizontal axis keeps true calendar spacing.
Missing dates receive no points, zeros, or estimated values. An orange point
in all-shifts mode means only one shift was
recorded. One-day histories show points without inferred trends, and no line is
extrapolated beyond recorded dates. New imports are included on refresh.

## Confirmed changeovers

Trend markers read explicit records from `changeover_events`, keyed by production
date, shift and machine. Product-code differences alone never create a marker.
The optional table contains `from_product`, `to_product`, and `confirmation_note`.
Absent event tables or missing events produce no changeover markers. Events obey
the selected date and shift filters; production quantities are unchanged.

Confirmed events always display purple dashed lines, outlined circles, and
short changeover labels in the chart under the current date, machine, and shift
filters. Chart hover information remains available in HTML. The web **Show
changeover details** toggle controls only the description list below the chart
and is off by default. Hiding that list leaves the chart markers and stored
events intact. The selection is retained in the URL across refreshes; trend HTML
and PDF downloads always retain the chart markers and follow the same selection
for their below-chart description lists.

For compatibility, the `show_changeovers` URL key and renderer parameter remain
in use, but now control only these detailed descriptions. No confirmed event
means no changeover marker; product-code differences never generate one.

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


## PDF download (local Dashboard)

Use **导出日报 PDF** beside the daily HTML download or **导出趋势 PDF** beside the trend HTML download. The report follows the selected date, shift, device, period and metric. Trend PDF and HTML reports always retain confirmed changeover lines, circles, and short labels; below-chart descriptions follow **Show changeover details**. Both formats retain the same recorded-date connection rule for every shift selection, as described above. PDF details are expanded and paginated. Downloads are generated on demand with ReportLab; viewing and filtering do not generate PDF files. Existing HTML downloads and standard-library CLI reporting are unchanged.

On macOS the PDF embeds the installed Arial Unicode font. On other systems it uses ReportLab's STSong-Light CJK font; this fallback has not been deployed as part of PLAN-008. No production data is sent to a PDF conversion service.


## Optional AI Production Assistant

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

The assistant reads the existing `slitting_records` and explicitly confirmed
`changeover_events`, and `abnormality_events` using parameterized, read-only SQLite connections with
`query_only`. It cannot execute arbitrary SQL or write production, enterprise,
or import tables. `ai_production_data.py` reuses the Dashboard's deterministic
aggregation rules. `ai_production_client.py` supplies the bounded official
OpenAI Responses API adapter; `ai_production_ui.py` handles filters, permission,
local evidence, and current-session state. `ai_floating_panel.py` mounts the
global fragment before business-page early exits; its local CSS/JavaScript
implements positioning and dragging without a new dependency or exposing keys.

Select an inclusive date range of at most 30 days, All/Day/Night, and any machines
(empty means all observed machines). Local summaries, coverage, and expandable
original numeric details are available without a key. Questions support
production lookup, machine comparison, daily observations, coverage, confirmed
changeovers, and production summaries. Missing records stay missing and zero
denominators stay unavailable. There is no automated performance verdict,
root-cause analysis, capacity forecast, shipment conclusion, purchasing action,
or access to the separate synthetic order demo.

The model selects a permitted query, then relevant fact IDs and ordering.
Displayed factual sentences and numbers are generated by Python, not copied
from unrestricted model prose. Each answer exposes its actual query scope and
evidence. Ambiguous or unsupported requests ask for clarification rather than
silently extending the selected range. Product differences never generate
changeover events.

### Configuration and user-triggered sending

The server reads `OPENAI_API_KEY` from the environment or Streamlit Secrets.
Use [the placeholder example](.streamlit/secrets.toml.example) as a reference,
append the setting privately, and preserve existing Secrets such as
`admin_import_password`. Do not copy the example over an existing Secrets file,
put a real key in source control, or send credentials in chat. The user is
responsible for API registration, billing, usage limits, and key configuration.
The assistant reports that AI is not configured when no usable key is available;
local facts remain available without inventing an AI answer.

The default is `gpt-6-luna` on the official Responses API, Standard mode,
`reasoning.effort="none"`, `store=False`, with SDK `max_retries=0`. There is no
silent model upgrade or third-party proxy fallback. At most two API requests are
allowed per submitted question, which is limited to 1,000 Unicode characters.
Each complete UTF-8 model-input package is limited to 32 KiB and each response
to 1,000 output tokens. Each request has a 30-second maximum timeout, within a
60-second total answer deadline. Over-limit, authentication, timeout, unavailable
model, and invalid-response states are explicit. Failures can still incur API
charges; application limits do not guarantee an account billing ceiling.

Before the first send, the chat stages the question locally and asks for
explicit approval after showing the scope; the sending preview is expandable.
Settings also offer permission control and shortcuts. Ordinary filtering or
refreshing makes no model request. Permission
resets when filters or the underlying data change. The model input allowlist
contains the submitted question, metric definitions, scope, necessary numeric
summaries and coverage, and confirmed-event dates with from/to products.
It excludes database files, screenshots, `source_name`, `notes`, file paths,
`confirmation_note`, synthetic orders, stock/BOM/supplier data, credentials,
and full chat history. Original production rows remain available locally in settings.

Question results are cached only in the current session, keyed by the question,
filters, model configuration, and data version. Data or scope changes invalidate
the relevant state; there is no shared user cache. API usage is returned for
checking without logging keys or complete request bodies. OpenAI API data is not
used for training by default, but abuse-monitoring logs may be retained for up
to 30 days, with policy exceptions. `store=False` is not a zero-retention promise.
See the official [data policy](https://developers.openai.com/api/docs/guides/your-data),
[setup guide](https://developers.openai.com/api/docs/quickstart),
[model documentation](https://developers.openai.com/api/docs/models/gpt-6-luna),
and [usage controls](https://developers.openai.com/api/docs/guides/spend-limits).

PLAN-018 v2 local validation passed **94 tests** (the previous 71 plus 23
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
cost, latency, or answer-quality acceptance test. No GitHub push or deployment
was performed; local verification does not establish hosted behavior or data.

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
