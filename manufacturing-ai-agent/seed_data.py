"""Insert simulated demo records once; preserve existing records on reruns."""

import sqlite3
from contextlib import closing

from database import DB_PATH, SETUP_MESSAGE, check_initialized, get_connection


def seed_database():
    if not DB_PATH.is_file():
        raise ValueError(SETUP_MESSAGE)

    with closing(get_connection()) as connection:
        check_initialized(connection)
        # One transaction: either all demo inserts succeed or none are saved.
        with connection:
            connection.executemany("""
                INSERT INTO orders (order_id, product, quantity, due_date, priority)
                VALUES (?, ?, ?, ?, ?) ON CONFLICT(order_id) DO NOTHING
            """, [
                ("ORD001", "MSRS", 1000, "2026-11-01", "High"),
                ("ORD002", "CEC-E", 600, "2026-11-05", "Medium"),
                ("ORD003", "MSRS", 400, "2026-10-25", "High"),
            ])
            connection.executemany("""
                INSERT INTO machines (machine_id, status, cycle_time, available_hours)
                VALUES (?, ?, ?, ?) ON CONFLICT(machine_id) DO NOTHING
            """, [
                ("FX1", "Running", 27, 20),
                ("FX2", "Running", 30, 20),
                ("FX3", "Maintenance", 0, 0),
                ("FX4", "Running", 28, 20),
                ("FX5", "Running", 29, 18),
                ("FX6", "Running", 27, 20),
                ("FX7", "Offline", 0, 0),
            ])
            connection.executemany("""
                INSERT INTO inventory
                    (material_id, material_name, current_stock, safety_stock)
                VALUES (?, ?, ?, ?) ON CONFLICT(material_id) DO NOTHING
            """, [
                ("MAT001", "PE Bag", 800, 200),
                ("MAT002", "Carton", 150, 100),
                ("MAT003", "EPE", 1200, 300),
                ("MAT004", "Pallet", 30, 10),
            ])
            connection.executemany("""
                INSERT INTO bom (product, material_id, qty_per_unit)
                VALUES (?, ?, ?) ON CONFLICT(product, material_id) DO NOTHING
            """, [
                ("MSRS", "MAT001", 1),
                ("MSRS", "MAT002", 0.333),
                ("MSRS", "MAT003", 2),
                ("MSRS", "MAT004", 0.0417),
                ("CEC-E", "MAT001", 1),
                ("CEC-E", "MAT002", 0.5),
                ("CEC-E", "MAT003", 1.5),
                ("CEC-E", "MAT004", 0.05),
            ])
            connection.executemany("""
                INSERT INTO suppliers (material_id, supplier_name, lead_time_days, moq)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(material_id, supplier_name) DO NOTHING
            """, [
                ("MAT001", "Supplier A", 7, 1000),
                ("MAT002", "Supplier B", 14, 500),
                ("MAT003", "Supplier C", 10, 1000),
                ("MAT004", "Supplier D", 21, 50),
            ])
    print("Demo data seeded successfully.")


if __name__ == "__main__":
    try:
        seed_database()
    except (ValueError, sqlite3.Error) as error:
        print(error)
        raise SystemExit(1)
