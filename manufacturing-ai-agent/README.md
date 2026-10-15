# Production Data Viewer Agent

## Overview

Production Data Viewer Agent extends the original manufacturing data foundation
with a local Streamlit Dashboard for daily production comparisons and machine
trends. SQLite import and offline reports use Python standard-library modules.
The web application uses Streamlit 1.65.0. No AI functionality is implemented.

All manufacturing data in Phase 1 is simulated demonstration data.

The future workflow is:

```text
User Request
↓
AI Agent
↓
Enterprise Tools
├── MES
├── Production Scheduling
├── Inventory
├── Procurement
├── Quality
└── Reporting
```

## Current Phase

**Phase 1 — Data Foundation**

- SQLite database
- Customer orders
- Production machines
- Material inventory
- Bill of materials (BOM)
- Supplier lead time and minimum order quantity (MOQ)

## Planned Architecture

| Phase | Scope |
| --- | --- |
| 1 | Data Foundation |
| 2 | Business Logic |
| 3 | Enterprise Tools |
| 4 | LLM Agent |
| 5 | MCP Integration |
| 6 | Production Scheduling & Procurement Optimization |

These later phases are planned work. Phase 1 performs no scheduling or material
requirement calculations.

## Database Schema

| Table | Fields and purpose |
| --- | --- |
| `orders` | `order_id` (primary key), `product` (required), `quantity`, `due_date` (ISO date text), `priority` |
| `machines` | `machine_id` (primary key), `status`, `cycle_time` (minutes per run), `available_hours` (hours per day) |
| `inventory` | `material_id` (primary key), `material_name`, `current_stock`, `safety_stock` |
| `bom` | `id` (autoincrement primary key), `product`, `material_id`, `qty_per_unit` (material quantity per finished product) |
| `suppliers` | `id` (autoincrement primary key), `material_id`, `supplier_name`, `lead_time_days`, `moq` |

BOM and supplier materials reference `inventory.material_id`; foreign keys are
enabled by the shared connection function. Unique product/material and
material/supplier pairs prevent duplicate demo records. Inventory and BOM
quantities use the corresponding material's demo unit; fractional packaging
requirements are illustrative, with rounding rules deferred to Phase 2.

The seed contains 3 orders, 7 machines (FX1–FX7), 4 materials, 8 BOM entries
across MSRS and CEC-E, and 4 suppliers. SQLite also creates the internal
`sqlite_sequence` table for autoincrement IDs.

## Setup

On macOS/Linux, open a terminal in `manufacturing-ai-agent`:

```bash
python3 -m venv .venv
source .venv/bin/activate

python3 init_db.py
python3 seed_data.py
python3 verify_db.py
python3 main.py
```

The virtual environment is optional for the standard-library CLI scripts.
For the web Dashboard, install the existing dependency declared in requirements.txt.
The database is always stored beside `database.py`, regardless of the terminal's
working directory. Initialize it before running the seed script; missing tables
produce a clear setup message and a nonzero exit status.

Initialization can be repeated without removing data. Seeding can also be
repeated: existing records are preserved, and missing demo records are inserted.
It does not reset records you have edited. Verification lists all tables and
prints the contents of each enterprise table. The main program checks that all
five tables exist and reports the connection status; an initialized but unseeded
database can pass this connection check.

## Project Files

| File | Purpose |
| --- | --- |
| `database.py` | Shared connection, database path, and schema readiness check |
| `init_db.py` | Create tables |
| `seed_data.py` | Insert simulated demo data without duplicate records |
| `verify_db.py` | Display tables and records |
| `main.py` | Welcome message and database status |
| `requirements.txt` | Streamlit and ReportLab dependencies for the web application |

`manufacturing.db`, virtual environments, Python caches, and `.env` are ignored
by Git. Recreate the local database with `python3 init_db.py` followed by
`python3 seed_data.py`. Do not commit secrets or confidential enterprise data.

## Daily Production Extension

See [PRODUCTION.md](PRODUCTION.md) for local daily slitting records, JSON import,
and offline comparison charts. The original Phase 1 seed data remains simulated.
User-supplied production observations are stored separately and excluded from Git.

## Production Dashboard

```bash
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run streamlit_app.py --server.address 127.0.0.1 --server.port 8502
```

Open http://127.0.0.1:8502. Select **当日数据** to view the four key metrics,
machine totals, linked 7/30-day trends and expandable raw details. Date, shift,
machine and metric selections persist in the URL. Existing standalone trend modes
and order analysis remain available. Download the current daily or trend report
as PDF or HTML. PDF files include the selected scope, charts and full data tables;
PDF generation runs only when the download button is clicked. Historical devices with no selected-date observation are shown as no
data, not zero output. See PRODUCTION.md for metric and coverage definitions.

Regression checks: `.venv/bin/python -B -m unittest test_production.py test_dashboard.py`.
The CLI uses no third-party packages; installing requirements is needed only for
the web application. A clone still needs separately retained local production data.

## Private Cloud Demo

See [DEPLOYMENT.md](DEPLOYMENT.md) for Community Cloud configuration, private
viewer access, manual JSON import and recovery. `cloud_entry.py` is the hosted
entrypoint. Local production data and cloud passwords are excluded from Git.

PDF regression checks: `.venv/bin/python -B -m unittest test_pdf.py`.


### Order progress demo (local)

Open **订单分析 → 订单进度 Demo** to select one of four synthetic orders.
The page shows required finished rolls, accumulated qualified finished rolls,
remaining rolls, completion percentage, a progress bar, a cumulative chart, and
synthetic shift/device details. DEMO-001 starts at 650 / 1,000 rolls (65%).
Change the target to try zero demand, completion, or overproduction; target edits
are session-only. The bar stops at 100% while the percentage retains any excess.
These records are isolated in `order_progress_demo.py`; they do not read or write
real production records or allocate production to real orders. Existing order and
BOM analysis is available under **原有订单分析**. No new dependency is required.

Checks: `.venv/bin/python -B -m unittest test_order_progress.py`.
