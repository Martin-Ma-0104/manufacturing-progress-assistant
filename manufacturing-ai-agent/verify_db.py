"""List all SQLite tables and display the five enterprise tables."""

import sqlite3
from contextlib import closing

from database import (
    DB_PATH, SETUP_MESSAGE, TABLE_NAMES, check_initialized, get_connection,
)


def verify_database():
    if not DB_PATH.is_file():
        raise ValueError(SETUP_MESSAGE)

    with closing(get_connection()) as connection:
        print("=== TABLES ===")
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
        ):
            print(row[0])
        check_initialized(connection)

        for table in TABLE_NAMES:
            print(f"\n=== {table.upper()} ===\n")
            # Identifiers come only from our fixed internal table list.
            cursor = connection.execute(f"SELECT * FROM {table} ORDER BY 1")
            print(" | ".join(column[0] for column in cursor.description))
            rows = cursor.fetchall()
            for row in rows:
                print(" | ".join(str(value) for value in row))
            if not rows:
                print("(no records)")


if __name__ == "__main__":
    try:
        verify_database()
    except (ValueError, sqlite3.Error) as error:
        print(error)
        raise SystemExit(1)
