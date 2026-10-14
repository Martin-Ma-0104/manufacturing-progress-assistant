# Production Data Viewer Agent

## Overview

A manufacturing enterprise AI agent project, currently implementing a simple,
extensible SQLite data foundation. Phase 1 uses Python 3 and its built-in
`sqlite3` module only. No AI functionality or external services are implemented.

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

The virtual environment is optional. No package installation is necessary.
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
| `requirements.txt` | Documents the standard-library-only dependency policy |

`manufacturing.db`, virtual environments, Python caches, and `.env` are ignored
by Git. Recreate the local database with `python3 init_db.py` followed by
`python3 seed_data.py`. Do not commit secrets or confidential enterprise data.

## Daily Production Extension

See [PRODUCTION.md](PRODUCTION.md) for local daily slitting records, JSON import,
and offline comparison charts. The original Phase 1 seed data remains simulated.
User-supplied production observations are stored separately and excluded from Git.
