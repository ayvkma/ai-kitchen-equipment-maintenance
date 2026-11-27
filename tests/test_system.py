from datetime import date
import sqlite3

from db.database import init_db, seed_sample_data
from db.repository import (
    add_maintenance_log,
    create_ticket,
    get_equipment_by_id,
    get_equipment_history,
    list_equipment,
    list_tickets,
    register_equipment,
)
from services.ai_triage import triage_ticket
from services.anomaly import (
    detect_equipment_anomalies,
    get_frequently_failing_equipment,
    get_sample_telemetry_df,
)
from services.scheduler_ai import (
    generate_maintenance_schedule,
    summarize_technician_report,
)


def _make_memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    init_db(conn)
    seed_sample_data(conn)
    return conn


def test_register_equipment_creates_asset_and_installation_log() -> None:
    conn = _make_memory_db()
    register_equipment(
        conn=conn,
        asset_id="ht-ktl-999",
        equipment_type="Steam Kettle",
        model_name="Hattori SK-200L",
        customer_name="Tokyo