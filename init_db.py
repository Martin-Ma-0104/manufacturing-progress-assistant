import sqlite3
from pathlib import Path


DATABASE = Path(__file__).with_name("database.db")


SAMPLE_TASKS = [
    (
        "Film Rack Purchase",
        "Procurement",
        "Martin",
        "Waiting for Supplier",
        "High",
        "Purchase request submitted and waiting for supplier quotation.",
        "Supplier lead time not confirmed.",
        "2026-06-15",
        "2026-06-08",
    ),
    (
        "BOPE Film Cart Purchase",
        "Procurement",
        "Wendy",
        "In Progress",
        "Medium",
        "Technical requirements confirmed. Procurement is comparing two suppliers.",
        "Final price needs confirmation before purchase order release.",
        "2026-06-20",
        "2026-06-07",
    ),
    (
        "Core Transfer Basket Purchase",
        "Procurement",
        "Allen",
        "Waiting for Approval",
        "Medium",
        "Quotation received and submitted for internal approval.",
        "Approval may delay the purchase order by several days.",
        "2026-06-18",
        "2026-06-06",
    ),
    (
        "Servo Core Removing Machine Purchase",
        "Engineering",
        "Grace",
        "Blocked",
        "Urgent",
        "Equipment specification is under review after the latest process trial.",
        "Machine design has not met cycle time target.",
        "2026-06-12",
        "2026-06-08",
    ),
    (
        "Oven Relocation",
        "Engineering",
        "Kevin",
        "In Progress",
        "High",
        "Layout plan completed. Utility check and safety review are ongoing.",
        "Production downtime window has not been fully confirmed.",
        "2026-06-25",
        "2026-06-05",
    ),
    (
        "Semi-Automatic Packaging Line Process",
        "Production Issue",
        "Lily",
        "In Progress",
        "High",
        "Trial run finished. Operators reported unstable label positioning.",
        "Rework may increase if label alignment is not improved.",
        "2026-06-14",
        "2026-06-08",
    ),
    (
        "Robot Sample Delivery Project",
        "Engineering",
        "Jason",
        "Not Started",
        "Low",
        "Initial project scope drafted. Waiting for kickoff meeting.",
        "Resource allocation is not yet confirmed.",
        "2026-07-05",
        "2026-06-03",
    ),
    (
        "Inner Packaging Dent Issue",
        "Production Issue",
        "Sophia",
        "Blocked",
        "Urgent",
        "Root cause analysis points to stacking pressure during transfer.",
        "Customer complaint risk if containment actions are delayed.",
        "2026-06-06",
        "2026-06-08",
    ),
    (
        "Customer Audit Preparation",
        "Audit Preparation",
        "Martin",
        "In Progress",
        "Urgent",
        "Document checklist is 70 percent complete. Open items remain for training records.",
        "Missing evidence could affect customer audit readiness.",
        "2026-06-10",
        "2026-06-08",
    ),
    (
        "SAP BOM Change 400000027 to 400000143",
        "SAP / BOM",
        "Diana",
        "Waiting for Approval",
        "High",
        "BOM change request has been submitted in SAP and is waiting for master data approval.",
        "Production order release may be delayed if BOM approval is late.",
        "2026-06-11",
        "2026-06-08",
    ),
]


def get_connection():
    return sqlite3.connect(DATABASE)


def initialize_database():
    with get_connection() as connection:
        connection.execute("DROP TABLE IF EXISTS tasks")
        connection.execute(
            """
            CREATE TABLE tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                owner TEXT NOT NULL,
                status TEXT NOT NULL,
                priority TEXT NOT NULL,
                progress_note TEXT NOT NULL,
                risk TEXT NOT NULL,
                due_date TEXT NOT NULL,
                last_updated TEXT NOT NULL
            )
            """
        )
        connection.executemany(
            """
            INSERT INTO tasks (
                title, category, owner, status, priority,
                progress_note, risk, due_date, last_updated
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            SAMPLE_TASKS,
        )


if __name__ == "__main__":
    initialize_database()
    print(f"Database initialized at {DATABASE}")
