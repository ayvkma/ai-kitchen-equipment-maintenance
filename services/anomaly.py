import sqlite3
from typing import Any

import pandas as pd
from sklearn.ensemble import IsolationForest


def get_sample_telemetry_df() -> pd.DataFrame:
    """Return sample operating metrics per equipment asset for anomaly inspection."""
    rows = [
        {
            "asset_id": "HT-KTL-101",
            "heat_up_minutes": 34.0,
            "vibration_db": 76.5,
            "pressure_bar": 1.45,
            "daily_cycles": 14,
        },
        {
            "asset_id": "HT-KTL-102",
            "heat_up_minutes": 21.0,
            "vibration_db": 58.0,
            "pressure_bar": 1.20,
            "daily_cycles": 11,
        },
        {
            "asset_id": "HT-RCK-201",
            "heat_up_minutes": 18.5,
            "vibration_db": 52.0,
            "pressure_bar": 1.05,
            "daily_cycles": 20,
        },
        {
            "asset_id": "HT-PRC-301",
            "heat_up_minutes": 22.0,
            "vibration_db": 55.5,
            "pressure_bar": 1.65,
            "daily_cycles": 9,
        },
    ]
    return pd.DataFrame(rows)


def detect_equipment_anomalies(
    telemetry_df: pd.DataFrame,
    contamination: float = 0.25,
) -> pd.DataFrame:
    """Flag unusual operating profiles using scikit-learn IsolationForest."""
    feature_cols = ["heat_up_minutes", "vibration_db", "pressure_bar", "daily_cycles"]
    result_df = telemetry_df.copy()

    if len(result_df) < 3:
        result_df["anomaly_flag"] = "Insufficient Data"
        result_df["anomaly_score"] = 0.0
        return result_df

    model = IsolationForest(contamination=contamination, random_state=42)
    preds = model.fit_predict(result_df[feature_cols])
    # decision_function: negative values indicate stronger anomaly
    scores = model.decision_function(result_df[feature_cols])

    result_df["anomaly_flag"] = ["Anomaly" if p == -1 else "Normal" for p in preds]
    result_df["anomaly_score"] = scores.round(4)
    return result_df.sort_values(by="anomaly_score", ascending=True).reset_index(drop=True)


def get_frequently_failing_equipment(conn: sqlite3.Connection) -> pd.DataFrame:
    """Rank equipment by repair/ticket count using SQL aggregation and Pandas."""
    query = """
        SELECT
            e.asset_id,
            e.equipment_type,
            e.model_name,
            e.customer_name,
            COUNT(CASE WHEN ml.event_type = 'Repair' THEN 1 END) AS repair_count,
            COUNT(DISTINCT t.id) AS ticket_count,
            MAX(ml.logged_at) AS last_service_at
        FROM equipment e
        LEFT JOIN maintenance_logs ml ON e.asset_id = ml.asset_id
        LEFT JOIN tickets t ON e.asset_id = t.asset_id
        GROUP BY
            e.asset_id,
            e.equipment_type,
            e.model_name,
            e.customer_name
        ORDER BY repair_count DESC, ticket_count DESC, e.asset_id ASC
    """
    df = pd.read_sql_query(query, conn)
    df["repair_count"] = df["repair_count"].fillna(0).astype(int)
    df["ticket_count"] = df["ticket_count"].fillna(0).astype(int)
    df["last_service_at"] = df["last_service_at"].fillna("No service logged")
    return df


def summarize_failure_hotspots(conn: sqlite3.Connection) -> dict[str, Any]:
    """Return high-level counts for top failing assets and models."""
    df = get_frequently_failing_equipment(conn)
    if df.empty:
        return {"top_asset": None, "total_repairs": 0, "total_tickets": 0, "table": df}

    top_row = df.iloc[0].to_dict()
    return {
        "top_asset": top_row["asset_id"],
        "total_repairs": int(df["repair_count"].sum()),
        "total_tickets": int(df["ticket_count"].sum()),
        "table": df,
    }