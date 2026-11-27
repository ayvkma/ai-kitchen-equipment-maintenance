import uuid
import sqlite3
from typing import Any
from datetime import datetime, timezone

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

def create_ticket(
    conn: sqlite3.Connection,
    asset_id: str,
    request_type: str,
    raw_description: str,
    category: str,
    priority: str,
    recommended_action: str,
) -> str:
    """Create a triaged maintenance ticket and record a Ticket Created log entry."""
    clean_asset_id = asset_id.strip().upper()
    timestamp = _now_iso()
    date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
    short_hash = uuid.uuid4().hex[:4].upper()
    ticket_code = f"TCK-{date_part}-{short_hash}"

    with conn:
        conn.execute(
            """
            INSERT INTO tickets (
                ticket_code, asset_id, request_type, raw_description,
                category, priority, recommended_action, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'Open', ?)
            """,
            (
                ticket_code,
                clean_asset_id,
                request_type.strip(),
                raw_description.strip(),
                category,
                priority,
                recommended_action,
                timestamp,
            ),
        )
        conn.execute(
            """
            INSERT INTO maintenance_logs (
                asset_id, ticket_code, event_type, summary,
                parts_used, technician_name, logged_at
            ) VALUES (?, ?, 'Ticket Created', ?, 'None', 'AI Triage System', ?)
            """,
            (
                clean_asset_id,
                ticket_code,
                f"[{priority}] {category}: {raw_description.strip()}",
                timestamp,
            ),
        )

    return ticket_code


def list_tickets(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Return all tickets joined with basic equipment info, newest first."""
    rows = conn.execute(
        """
        SELECT t.*, e.equipment_type, e.model_name, e.customer_name, e.kitchen_location
        FROM tickets t
        JOIN equipment e ON t.asset_id = e.asset_id
        ORDER BY t.created_at DESC, t.id DESC
        """
    ).fetchall()
    return [dict(row) for row in rows]