import sqlite3
from pathlib import Path

DB_PATH = Path("data/kitchen_maintenance.db")


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Create a SQLite connection with foreign keys and dictionary-like row access."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Create tables for equipment assets, maintenance tickets, and service history."""
    with conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS equipment (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_id TEXT NOT NULL UNIQUE,
                equipment_type TEXT NOT NULL,
                model_name TEXT NOT NULL,
                customer_name TEXT NOT NULL,
                kitchen_location TEXT NOT NULL,
                install_date TEXT NOT NULL,
                maintenance_interval_days INTEGER NOT NULL DEFAULT 90,
                status TEXT NOT NULL DEFAULT 'Active'
            );

            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_code TEXT NOT NULL UNIQUE,
                asset_id TEXT NOT NULL,
                request_type TEXT NOT NULL,
                raw_description TEXT NOT NULL,
                category TEXT,
                priority TEXT,
                recommended_action TEXT,
                status TEXT NOT NULL DEFAULT 'Open',
                created_at TEXT NOT NULL,
                FOREIGN KEY (asset_id) REFERENCES equipment (asset_id)
            );

            CREATE TABLE IF NOT EXISTS maintenance_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_id TEXT NOT NULL,
                ticket_code TEXT,
                event_type TEXT NOT NULL,
                summary TEXT NOT NULL,
                parts_used TEXT,
                technician_name TEXT,
                logged_at TEXT NOT NULL,
                FOREIGN KEY (asset_id) REFERENCES equipment (asset_id),
                FOREIGN KEY (ticket_code) REFERENCES tickets (ticket_code)
            );
            """
        )


def seed_sample_data(conn: sqlite3.Connection) -> None:
    """Insert realistic commercial kitchen assets and initial service logs if empty."""
    cursor = conn.cursor()
    existing_count = cursor.execute("SELECT COUNT(*) FROM equipment").fetchone()[0]
    if existing_count > 0:
        return

    sample_assets = [
        (
            "HT-KTL-101",
            "Steam Kettle",
            "Hattori SK-150L",
            "Sakura Central Kitchen",
            "Line A - Batch Cooking",
            "2024-03-15",
            60,
            "Active",
        ),
        (
            "HT-KTL-102",
            "Mixing Kettle",
            "Hattori MK-200L",
            "Kanto Hotel Group",
            "Sauce & Soup Station",
            "2023-11-01",
            60,
            "Active",
        ),
        (
            "HT-RCK-201",
            "IH Rice Cooker",
            "Hattori DRC-3Deck",
            "Aichi Bento Factory",
            "Main Rice Line",
            "2025-01-10",
            90,
            "Active",
        ),
        (
            "HT-PRC-301",
            "Pressure Cooker",
            "Hattori PC-120",
            "Sakura Central Kitchen",
            "Line B - High Pressure",
            "2024-07-20",
            90,
            "Active",
        ),
    ]

    sample_logs = [
        (
            "HT-KTL-101",
            None,
            "Installation",
            "Commissioned 150L steam kettle; verified steam trap pressure and safety valve.",
            "None",
            "S. Takahashi",
            "2024-03-15 09:30:00",
        ),
        (
            "HT-KTL-102",
            None,
            "Inspection",
            "Routine agitator seal check and thermal sensor calibration.",
            "O-Ring Seal Kit v2",
            "R. Sato",
            "2025-08-12 14:00:00",
        ),
        (
            "HT-RCK-201",
            None,
            "Installation",
            "Installed 3-deck IH rice cooker; tested deck temperature uniformity.",
            "None",
            "S. Takahashi",
            "2025-01-10 11:15:00",
        ),
    ]

    with conn:
        conn.executemany(
            """
            INSERT INTO equipment (
                asset_id, equipment_type, model_name, customer_name,
                kitchen_location, install_date, maintenance_interval_days, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            sample_assets,
        )
        conn.executemany(
            """
            INSERT INTO maintenance_logs (
                asset_id, ticket_code, event_type, summary,
                parts_used, technician_name, logged_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            sample_logs,
        )