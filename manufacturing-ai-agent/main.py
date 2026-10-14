"""Phase 1 welcome and database readiness check."""

import sqlite3
from contextlib import closing

from database import DB_PATH, SETUP_MESSAGE, check_initialized, get_connection


def main():
    print("Production Data Viewer Agent\n")
    print("Phase 1: Data Foundation\n")
    if not DB_PATH.is_file():
        print(SETUP_MESSAGE)
        return 1
    try:
        with closing(get_connection()) as connection:
            check_initialized(connection)
            connection.execute("SELECT 1")
    except (ValueError, sqlite3.Error) as error:
        print(error)
        return 1
    print("Database connection: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
