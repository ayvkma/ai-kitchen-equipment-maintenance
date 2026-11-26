from datetime import datetime, timezone
import sqlite3
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def register_equipment(
    conn: sqlite3.Connection,
    asset_id: str,
    equipment_type: str,
    model_name: str,
    customer_name: str,
    kitchen_location: str,
    install_date: str,
    maintenance_interval_days: int = 90,
    technician_name: str = "Field Engineer",
) -> None:
    """Register a new commercial kitchen machine and record its initial installation log."""
    clean_id = asset_id.strip().upper()
    timestamp = _now_iso()

    with conn:
        conn.execute(
            """
            INSERT INTO equipment (
                asset_id, equipment_type, model_name, customer_name,
                kitchen_location, install_date, maintenance_interval_days, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'Active')
            """,
            (
                clean_id,
                equipment_type.strip(),
                model_name.strip(),
                customer_name.strip(),
                kitchen_location.strip(),
                install_date.strip(),
                int(maintenance_interval_days),
            ),
        )
        conn.execute(
            """
            INSERT INTO maintenance_logs (
                asset_id, ticket_code, event_type, summary,
                parts_used, technician_name, logged_at
            ) VALUES (?, NULL, 'Installation', ?, 'None', ?, ?)
            """,
            (
                clean_id,
                f"Registered and installed {model_name.strip()} at {customer_name.strip()}.",
                technician_name.strip(),
                timestamp,
            ),
        )


def list_equipment(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Return all registered equipment ordered by asset_id."""
    rows = conn.execute("SELECT * FROM equipment ORDER BY asset_id ASC").fetchall()
    return [dict(row) for row in rows]


def get_equipment_by_id(conn: sqlite3.Connection, asset_id: str) -> dict[str, Any] | None:
    """Fetch a single equipment record by unique asset_id."""
    row = conn.execute(
        "SELECT * FROM equipment WHERE asset_id = ?",
        (asset_id.strip().upper(),),
    ).fetchone()
    return dict(row) if row else None


def get_equipment_history(conn: sqlite3.Connection, asset_id: str) -> list[dict[str, Any]]:
    """Return chronological maintenance, repair, inspection, and installation logs for an asset."""
    rows = conn.execute(
        """
        SELECT * FROM maintenance_logs
        WHERE asset_id = ?
        ORDER BY logged_at DESC, id DESC
        """,
        (asset_id.strip().upper(),),
    ).fetchall()
    return [dict(row) for row in rows]