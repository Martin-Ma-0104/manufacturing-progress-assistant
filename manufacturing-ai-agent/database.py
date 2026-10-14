"""Shared SQLite connection and schema checks."""

import sqlite3
from pathlib import Path

DB_NAME = "manufacturing.db"
# Resolve relative to this file so commands work from any directory.
DB_PATH = Path(__file__).resolve().parent / DB_NAME
TABLE_NAMES = ("orders", "machines", "inventory", "bom", "suppliers")
SETUP_MESSAGE = (
    "Database not initialized.\nRun:\n\n"
    "python3 init_db.py\npython3 seed_data.py"
)


def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def check_initialized(connection):
    tables = {
        row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    if not set(TABLE_NAMES).issubset(tables):
        raise ValueError(SETUP_MESSAGE)
