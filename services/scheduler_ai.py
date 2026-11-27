from datetime import date, datetime, timedelta, timezone
import json
import os
import sqlite3
from typing import Any

import pandas as pd


def _parse_date(value: str | None) -> date | None:
    """Parse YYYY-MM-DD or YYYY-MM-DD HH:MM:SS strings into a date object."""
    if not value:
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:19], fmt).date()
        except ValueError:
            continue
    return None


def generate_maintenance_schedule(
    conn: sqlite3.Connection,
    reference_date: date | None = None,
    due_soon_days: int = 14,
) -> pd.DataFrame:
    """Generate preventive maintenance due dates and urgency statuses for all equipment."""
    today = reference_date or datetime.now(timezone.utc).date()

    query = """
        SELECT
            e.asset_id,
            e.equipment_type,
            e.model_name,
            e.customer_name,
            e.kitchen_location,
            e.install_date,
            e.maintenance_interval_days,
            e.status,
            MAX(ml.logged_at) AS last_log_at
        FROM equipment e
        LEFT JOIN maintenance_logs ml
            ON e.asset_id = ml.asset_id
            AND ml.event_type IN ('Installation', 'Inspection', 'Maintenance', 'Repair')
        GROUP BY
            e.asset_id,
            e.equipment_type,
            e.model_name,
            e.customer_name,
            e.kitchen_location,
            e.install_date,
            e.maintenance_interval_days,
            e.status
        ORDER BY e.asset_id ASC
    """
    df = pd.read_sql_query(query, conn)
    if df.empty:
        return pd.DataFrame(
            columns=[
                "asset_id",
                "equipment_type",
                "model_name",
                "customer_name",
                "kitchen_location",
                "baseline_date",
                "next_due_date",
                "days_until_due",
                "schedule_status",
            ]
        )

    rows: list[dict[str, Any]] = []
    for _, rec in df.iterrows():
        baseline = _parse_date(rec["last_log_at"]) or _parse_date(rec["install_date"]) or today
        interval_days = int(rec["maintenance_interval_days"] or 90)
        next_due = baseline + timedelta(days=interval_days)
        days_remaining = (next_due - today).days

        if days_remaining < 0:
            sched_status = "Overdue"
        elif days_remaining <= due_soon_days:
            sched_status = "Due Soon"
        else:
            sched_status = "Scheduled"

        rows.append(
            {
                "asset_id": rec["asset_id"],
                "equipment_type": rec["equipment_type"],
                "model_name": rec["model_name"],
                "customer_name": rec["customer_name"],
                "kitchen_location": rec["kitchen_location"],
                "baseline_date": baseline.isoformat(),
                "next_due_date": next_due.isoformat(),
                "days_until_due": days_remaining,
                "schedule_status": sched_status,
            }
        )

    schedule_df = pd.DataFrame(rows)
    return schedule_df.sort_values(by=["days_until_due", "asset_id"], ascending=[True, True]).reset_index(
        drop=True
    )


def _fallback_report_summary(raw_notes: str) -> dict[str, str]:
    """Fallback summary when no AI API key is set or an API error occurs."""
    cleaned = " ".join(raw_notes.strip().split())
    if not cleaned:
        return {
            "summary": "No technician notes provided.",
            "parts_mentioned": "None specified",
            "follow_up_action": "Review equipment status with technician.",
        }

    sentences = [s.strip() for s in cleaned.replace("\n", ". ").split(".") if s.strip()]
    summary = sentences[0] if sentences else cleaned[:160]
    follow_up = sentences[-1] if len(sentences) > 1 else "Monitor performance during next kitchen shift."

    return {
        "summary": summary[:220],
        "parts_mentioned": "Check notes for replacement parts or consumables",
        "follow_up_action": follow_up[:220],
    }


def summarize_technician_report(
    asset_id: str,
    technician_name: str,
    raw_notes: str,
) -> dict[str, str]:
    """Use AI to summarize raw technician field notes into structured maintenance records."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return _fallback_report_summary(raw_notes)

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        prompt = f"""
You are a maintenance operations assistant for Hattori Kogyo.
Summarize the technician's field notes for asset {asset_id} (Technician: {technician_name}).

Raw Technician Notes:
{raw_notes}

Return ONLY valid JSON with these exact keys:
- "summary": concise 1-2 sentence summary of work completed and equipment state
- "parts_mentioned": comma-separated list of parts replaced or needed, or "None"
- "follow_up_action": next recommended step or preventive action, or "None required"
"""
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2,
            ),
        )
        parsed = json.loads(response.text)
        return {
            "summary": str(parsed.get("summary", "")).strip() or _fallback_report_summary(raw_notes)["summary"],
            "parts_mentioned": str(parsed.get("parts_mentioned", "None")).strip() or "None",
            "follow_up_action": str(parsed.get("follow_up_action", "None required")).strip() or "None required",
        }
    except Exception:
        return _fallback_report_summary(raw_notes)