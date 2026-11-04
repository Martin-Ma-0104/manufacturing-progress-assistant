# Manufacturing AI — Production Data Viewer

A focused production-data application for industrial engineers and production
managers. The current Next.js website has **three pages** over existing Python
calculations and reviewed SQLite records.

| Page | Core functions |
|---|---|
| Dashboard | Production totals, machine comparisons, 7-/30-day trends, confirmed changeovers, runtime estimates, PDF/HTML downloads |
| Production Monitoring | Machine records, reviewed manual entry, nonconforming-film area and quality details |
| AI Production Expert | Input comparison, recorded abnormality-duration ranking, and a simple production chat |

Dates, machine, shift and product filters remain in the URL across refreshes.
Research analysis supports dates, machine and shift; it explicitly asks to clear
an unsupported product filter. Missing records remain unavailable, while an
explicit zero stays zero. No production data is included in a source checkout.

## Local setup

Use Python 3.12 and Node 24 from the application directory:

```bash
python3.12 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt
cd frontend
npm ci
cd ..
```

Start these in separate terminals:

```bash
bash scripts/start_backend.sh
```

```bash
bash scripts/start_frontend.sh
```

Open [Dashboard](http://127.0.0.1:3000/dashboard),
[Production Monitoring](http://127.0.0.1:3000/production), or
[AI Production Expert](http://127.0.0.1:3000/ai-expert).
For a local production-mode frontend, run `npm run build` followed by
`npm run start` in `frontend/`.

The application binds to localhost. Shared authentication and live machine feeds
are not implemented. This source update does not deploy Next.js/FastAPI externally.

## Production and quality data

Reviewed production uses the existing `slitting_records` table. Add one reviewed
date/shift/machine/product record through **Add real record**, or use the existing
reviewed JSON workflow. Identical entries are skipped; conflicting values are
rejected without overwriting production. Source references and notes stay local.

Quality records use the separate `slitting_rejects` table. Area is stored precisely
in m² and each detail is counted once; detail counts are not finished-roll counts.
Quality-only dates/products remain discoverable, without inventing production or
recalculating the original area qualification rate.

- Input plan attainment = summed actual mother rolls / summed planned mother rolls.
- Area qualification = summed qualified area / summed actual output area.
- Ratios with a zero denominator are unavailable.
- Finished rolls, input mother rolls and m² are different units.
- Reported yield is retained at source level; no unknown aggregate is inferred.
- Actual minus qualified area is not automatically classified as scrap.

Production databases, reviewed imports, source spreadsheets/images, extracted
company documents and secrets remain excluded from Git. The source checkout is
not a backup of the user's production history. See [PRODUCTION.md](PRODUCTION.md)
for the preserved data formats and [DEPLOYMENT.md](DEPLOYMENT.md) for the separate
Streamlit recovery workflow.

## Dashboard and analysis

Actual input uses a blue solid line; planned input uses a slate dashed reference.
All recorded values remain labeled, including zero. Dates stay horizontal with
calendar spacing; recorded observations connect across missing dates without
invented points. Confirmed purple changeover marks remain visible and their
explanations are collapsed. Tables and coverage definitions are available on demand.

Estimated runtime/utilization use the previously confirmed assumptions: 12-hour
shifts, two hours of flexible breaks, all recorded abnormality intervals treated
as stops, and union time to avoid repeated deduction. They remain labelled
estimates. Missing measured cycle-time and capacity placeholders are no longer
shown as dashboard features.

**Verified production analysis** above the chat calls two frozen research tools
on one read-only SQLite snapshot, with no model request:

1. Input comparison: planned/actual input mother rolls, actual minus plan,
   record-level shortfall, net shortfall and excess, with bars and a full table.
2. Abnormality duration: competition ranking of known recorded event-minute
   subtotals. Partial subtotals and missing durations remain explicit; overlaps
   are additive event records and are not net downtime. Unknown/no-event machines
   remain unranked; Open events are not extended to now.

The chat is limited to production and recorded abnormality analysis. Website
model selection exposes only `production_lookup` and `downtime_lookup`.
**AI options** holds the optional model toggle and per-question transmission
permission. Credentials stay in the backend environment; no model request is
made during ordinary production/research viewing. Live-model quality has not been
established by the offline tests.

## Focused interface

Decorative subtitles, environment badges, placeholder notifications/avatars,
repeated scope text and repeated metric summaries have been removed. Important
units, legends, numeric labels, input confirmation, errors and unavailable-data
states remain. Definitions and evidence are available in collapsed sections.

Planning, Inventory, Knowledge and Settings are no longer website pages; their
old URLs return 404. Their source modules and compatibility APIs are retained for
historical/offline use, independently of this three-page website. They are not
available as capabilities of the website chat. Existing Streamlit and the root
Flask tracker remain separate legacy applications.

## Validation and research

The core-interface change passed **251 automated tests**: 176 enterprise/research
pytest cases, 61 legacy data regressions, and 14 trend-layout tests. TypeScript and
the Next.js production build passed. Production and research calculations remain
shared Python functions; the frozen research manifest stays version 1.1. HTTP
verification does not establish browser pixel or mouse/keyboard acceptance.

```bash
PYTHON_DOTENV_DISABLED=1 backend/.venv/bin/python -B -m pytest tests/enterprise tests/research -q -p no:cacheprovider
node --test frontend/tests/trend-layout.test.mjs
```

See [architecture and validation](docs/ENTERPRISE.md),
[the 20-question research milestone](research/harry_milestone/README.md), and
[the frozen offline research results](research/harry_milestone/RESULTS.md).
Paid GPT-6 evaluation, human task-time studies and cloud data recovery are separate
activities and have not been run as part of this interface cleanup.
