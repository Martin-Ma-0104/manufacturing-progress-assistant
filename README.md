# Manufacturing Progress Assistant

This repository contains two Python applications. The current development focus is **Production Data Viewer Agent**, a Streamlit Dashboard for reviewing daily slitting-machine production, comparing equipment, and following historical trends. The original Flask task tracker remains available at the repository root.

| Application | Location | Purpose | Local address |
| --- | --- | --- | --- |
| **Production Data Viewer Agent** | [`manufacturing-ai-agent/`](manufacturing-ai-agent/) | Slitting production data, machine comparisons, trends, and report downloads | `http://127.0.0.1:8502/` |
| Original Manufacturing Progress Assistant | Repository root | Manufacturing project and task progress tracking | `http://127.0.0.1:5000/` |

## Slitting Production Dashboard

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
- A dashed plan line alongside actual input; gaps for missing dates and indicators for incomplete shift coverage
- Changeover markers only for explicitly confirmed events, never inferred from a product-code difference alone
- Raw production details by machine, product, and shift
- Filter selections retained in the URL across refreshes
- **PDF and HTML downloads** for the current daily report and trend selection

Input plan attainment is total input rolls divided by total planned rolls. Area qualification rate is total qualified output area divided by total actual output area. Aggregate percentages use ratios of sums; zero denominators are unavailable, and missing observations are not filled with zeros. Recorded machine count describes records, not running status or utilization.

### Data workflow

Production screenshots are reviewed in conversation, transcribed into JSON, and imported into SQLite after the date, shift, and figures are checked. The importer skips identical records and rejects conflicting batches rather than silently overwriting production data.

The application does not perform automatic image recognition, live equipment collection, or AI analysis. Production databases, original screenshots, and private import files are retained separately from the source repository. **A clone does not contain the user's production history.**

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

The Dashboard uses Python, Streamlit, SQLite, and ReportLab. Its dependencies are in `manufacturing-ai-agent/requirements.txt`; the root requirements file is for the separate Flask application. The loopback address above is accessible on the computer running the server. Private cloud setup uses a separate entrypoint and configuration, described in the deployment guide; source synchronization alone does not verify a hosted release.

### Supporting order analysis

The Dashboard retains the existing order and BOM analysis and adds an isolated **order progress demo**. Four synthetic orders demonstrate qualified finished rolls versus demand, remaining rolls, completion percentage, a progress bar, a cumulative chart with horizontal date labels, and shift/machine details. A session-only target editor demonstrates completion, overproduction, and zero demand.

Demo production is not allocated from real slitting records and does not update the production database. Connecting actual production to real customer orders requires order requirements and an agreed production-allocation rule.

### Documentation and checks

- [Dashboard setup, features, and module guide](manufacturing-ai-agent/README.md)
- [Production JSON import, metrics, and report behavior](manufacturing-ai-agent/PRODUCTION.md)
- [Private cloud access, import, and recovery](manufacturing-ai-agent/DEPLOYMENT.md)

From `manufacturing-ai-agent/`, run the regression suite:

```bash
.venv/bin/python -B -m unittest test_production.py test_dashboard.py test_cloud_data.py test_pdf.py test_order_progress.py -v
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
    `-- requirements.txt        # Streamlit and ReportLab dependencies
```

### Future ideas for the original tracker

Potential future work includes Teams, SharePoint, or Outlook connections; LLM-assisted queries; login and permissions; overdue-task reminders; and additional weekly-report export formats. These are ideas, not implemented integrations.
