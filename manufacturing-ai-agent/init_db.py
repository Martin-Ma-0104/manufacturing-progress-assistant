"""Create the five Phase 1 tables without deleting existing data."""

from contextlib import closing

from database import get_connection


def initialize_database():
    with closing(get_connection()) as connection:
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                product TEXT NOT NULL,
                quantity INTEGER,
                due_date TEXT,
                priority TEXT
            );

            CREATE TABLE IF NOT EXISTS machines (
                machine_id TEXT PRIMARY KEY,
                status TEXT,
                cycle_time REAL,
                available_hours REAL
            );

            CREATE TABLE IF NOT EXISTS inventory (
                material_id TEXT PRIMARY KEY,
                material_name TEXT NOT NULL,
                current_stock REAL,
                safety_stock REAL
            );

            CREATE TABLE IF NOT EXISTS bom (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product TEXT NOT NULL,
                material_id TEXT NOT NULL REFERENCES inventory(material_id),
                qty_per_unit REAL,
                UNIQUE (product, material_id)
            );

            CREATE TABLE IF NOT EXISTS suppliers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                material_id TEXT NOT NULL REFERENCES inventory(material_id),
                supplier_name TEXT NOT NULL,
                lead_time_days INTEGER,
                moq INTEGER,
                UNIQUE (material_id, supplier_name)
            );
        """)
    print("Database initialized successfully.")


if __name__ == "__main__":
    initialize_database()
