# Manufacturing Progress Assistant

The main application is a focused manufacturing production viewer, built with
**Next.js, React, TypeScript, FastAPI, Python and SQLite**. It helps industrial
engineers and production managers inspect reviewed slitting records and recorded
abnormalities.

The current website has three pages:

- **Dashboard:** production totals, machine comparisons, input/output trends,
  confirmed changeovers, estimated runtime/utilization and report downloads.
- **Production Monitoring:** machine records, reviewed manual production entry
  and nonconforming-film quality data.
- **AI Production Expert:** input comparison and recorded abnormality-duration
  ranking, plus a simple production chat with only two business tools.

Date, machine, shift and product filters stay in the URL. Missing records are not
zero, input mother rolls are distinct from finished rolls and area, and recorded
abnormality event-minutes are not measured net downtime. The research view makes
no model request; optional model access is explicitly enabled per question.

## Run locally

From `manufacturing-ai-agent/`, use Python 3.12 and Node 24:

```bash
python3.12 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt
cd frontend
npm ci
cd ..
```

Run these in separate terminals:

```bash
bash scripts/start_backend.sh
```

```bash
bash scripts/start_frontend.sh
```

Open [the local Dashboard](http://127.0.0.1:3000/dashboard).

The website is localhost-only and has no shared authentication or live equipment
feed. Production data, private documents, reviewed import files, databases and
credentials are excluded from this repository. A checkout starts without the
user's private production history.

## Current interface scope

The website keeps titles, filters, business metrics, chart legends and values,
input confirmation, errors and important empty states. Repeated summaries,
implementation/environment labels and decorative helper prose are removed;
definitions and coverage remain available on demand.

Planning, Inventory, Knowledge and Settings are retired from website navigation
and page routes. Placeholder notifications, avatars and unavailable cycle-time/
capacity features are removed. Historical source modules and compatibility APIs
remain available for offline/legacy use. The website chat does not expose those
retired capabilities.

## Research milestone

Two predefined, read-only tools compare planned/actual input mother rolls and rank
known recorded abnormality durations. Python/SQLite calculate all numbers.
Independent synthetic A/B fixtures, 20 frozen questions, hand-calculated answers
and a versioned manifest support reproducible offline validation. The B fixture
changes the correct leading machine. Tool checks, mocked integration and any
future live-model evaluation are reported separately.

The current core release passed **251 automated tests**, TypeScript checks and a
production build. HTTP and calculation checks do not establish browser visual
acceptance or live-model accuracy. Paid GPT-6 evaluation and human task-time
comparison remain separate, unexecuted activities.

Read the [application guide](manufacturing-ai-agent/README.md),
[architecture guide](manufacturing-ai-agent/docs/ENTERPRISE.md),
[research methodology](manufacturing-ai-agent/research/harry_milestone/README.md)
and [evaluation questions](manufacturing-ai-agent/research/harry_milestone/QA.md).

## Preserved legacy applications

The Streamlit viewer under `manufacturing-ai-agent/` retains the older reviewed
JSON import, order demonstration and report workflow. The private Streamlit cloud
entrypoint is separate from the current Next.js website; see its
[deployment/recovery guide](manufacturing-ai-agent/DEPLOYMENT.md).

The repository-root Flask task tracker (`app.py`, `templates/`, `static/`) remains
an independent legacy project. Its task/project tracking is not the production
SQLite database or the current AI analysis interface. These applications are
preserved independently of the focused production website.
