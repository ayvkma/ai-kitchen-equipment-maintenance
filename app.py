import os
import streamlit as st

from db.database import get_connection, init_db, seed_sample_data
from db.repository import (
    add_maintenance_log,
    create_ticket,
    get_equipment_by_id,
    get_equipment_history,
    list_equipment,
    list_tickets,
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

st.set_page_config(
    page_title="AI Kitchen Equipment Maintenance System",
    page_icon="🍳",
    layout="wide",
)


@st.cache_resource
def setup_database() -> None:
    """Ensure SQLite tables and sample commercial kitchen assets exist."""
    conn = get_connection()
    try:
        init_db(conn)
        seed_sample_data(conn)
    finally:
        conn.close()


setup_database()

st.title("AI Kitchen Equipment Maintenance System")
st.caption("IT + DX operations hub for commercial cooking equipment: assets, AI triage, ML anomaly detection, and maintenance scheduling.")

api_status = "Active (Gemini API)" if os.getenv("GEMINI_API_KEY") else "Fallback Mode (No GEMINI_API_KEY)"
st.sidebar.markdown(f"**AI Triage & Summary:** `{api_status}`")

conn = get_connection()
try:
    equipment_list = list_equipment(conn)
    tickets_list = list_tickets(conn)
    schedule_df = generate_maintenance_schedule(conn)
    failure_df = get_frequently_failing_equipment(conn)

    # Top KPI row
    overdue_count = int((schedule_df["schedule_status"] == "Overdue").sum()) if not schedule_df.empty else 0
    open_tickets_count = sum(1 for t in tickets_list if t["status"] != "Closed")
    total_repairs = int(failure_df["repair_count"].sum()) if not failure_df.empty else 0

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Registered Equipment", len(equipment_list))
    k2.metric("Open Tickets", open_tickets_count)
    k3.metric("Logged Repairs", total_repairs)
    k4.metric("Maintenance Overdue", overdue_count)

    tab_assets, tab_triage, tab_analytics, tab_schedule = st.tabs(
        [
            "Asset Registry & History",
            "Ticket Intake & AI Triage",
            "ML Anomaly & Failure Analytics",
            "Preventive Schedule & Report AI",
        ]
    )

    # ------------------------------------------------------------------
    # TAB 1: Asset Registry & Maintenance History
    # ------------------------------------------------------------------
    with tab_assets:
        left_col, right_col = st.columns([1, 1.4])

        with left_col:
            st.subheader("Register Equipment")
            with st.form("register_equipment_form", clear_on_submit=True):
                asset_id = st.text_input("Unique Asset ID", placeholder="HT-KTL-105")
                equipment_type = st.selectbox(
                    "Equipment Type",
                    ["Steam Kettle", "Mixing Kettle", "IH Rice Cooker", "Pressure Cooker", "Combi Oven", "Tilt Skillet"],
                )
                model_name = st.text_input("Model Name", placeholder="Hattori SK-150L")
                customer_name = st.text_input("Customer Name", placeholder="Sakura Central Kitchen")
                kitchen_location = st.text_input("Kitchen Location", placeholder="Line A - Prep")
                install_date = st.text_input("Installation Date (YYYY-MM-DD)", value="2026-01-15")
                interval_days = st.number_input("Maintenance Interval (Days)", min_value=15, max_value=365, value=90, step=15)
                tech_name = st.text_input("Commissioning Technician", value="S. Takahashi")
                submitted_asset = st.form_submit_button("Register Asset")

            if submitted_asset:
                if not asset_id.strip() or not model_name.strip() or not customer_name.strip():
                    st.error("Asset ID, Model Name, and Customer Name are required.")
                else:
                    try:
                        register_fn = __import__("db.repository", fromlist=["register_equipment"]).register_equipment
                        register_fn(
                            conn=conn,
                            asset_id=asset_id,
                            equipment_type=equipment_type,
                            model_name=model_name,
                            customer_name=customer_name,
                            kitchen_location=kitchen_location or "Main Kitchen",
                            install_date=install_date,
                            maintenance_interval_days=int(interval_days),
                            technician_name=tech_name,
                        )
                        st.success(f"Registered {asset_id.strip().upper()} and logged installation.")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Could not register equipment: {exc}")

        with right_col:
            st.subheader("Registered Fleet")
            if equipment_list:
                st.dataframe(equipment_list, use_container_width=True, hide_index=True)

                asset_ids = [item["asset_id"] for item in equipment_list]
                selected_asset = st.selectbox("Inspect Maintenance & Repair History", asset_ids)
                history_rows = get_equipment_history(conn, selected_asset)
                st.markdown(f"**Service Timeline for `{selected_asset}`**")
                if history_rows:
                    st.dataframe(history_rows, use_container_width=True, hide_index=True)
                else:
                    st.info("No service logs recorded yet for this unit.")
            else:
                st.info("No equipment registered yet.")

    # ------------------------------------------------------------------
    # TAB 2: Ticket Intake & AI Triage
    # ------------------------------------------------------------------
    with tab_triage:
        st.subheader("Submit Repair, Maintenance, Parts, or Inspection Request")
        asset_ids = [item["asset_id"] for item in equipment_list]

        if not asset_ids:
            st.warning("Register at least one piece of equipment first.")
        else:
            col_form, col_preview = st.columns([1.1, 1])

            with col_form:
                selected_ticket_asset = st.selectbox("Equipment Asset ID", asset_ids, key="triage_asset_select")
                request_type = st.selectbox(
                    "Request Type",
                    ["Repair", "Maintenance", "Replacement Parts", "Technical Support", "Equipment Inspection"],
                )
                sample_text = "Our commercial cooking kettle is heating slowly and making unusual noises."
                description = st.text_area(
                    "Customer / Kitchen Issue Description",
                    value=sample_text,
                    height=110,
                )

                if st.button("Run AI Triage"):
                    eq_info = get_equipment_by_id(conn, selected_ticket_asset)
                    if eq_info:
                        triage_result = triage_ticket(eq_info, request_type, description)
                        st.session_state["triage_draft"] = {
                            "asset_id": selected_ticket_asset,
                            "request_type": request_type,
                            "raw_description": description,
                            **triage_result,
                        }

            with col_preview:
                st.markdown("**Triage Preview & Ticket Creation**")
                draft = st.session_state.get("triage_draft")
                if draft:
                    st.write(f"**Asset:** `{draft['asset_id']}` | **Type:** `{draft['request_type']}`")
                    st.write(f"**Classified Category:** `{draft['category']}`")
                    st.write(f"**Assigned Priority:** `{draft['priority']}`")
                    st.markdown("**Retrieved Troubleshooting & Action Plan:**")
                    st.info(draft["recommended_action"])

                    if st.button("Create Maintenance Ticket"):
                        ticket_code = create_ticket(
                            conn=conn,
                            asset_id=draft["asset_id"],
                            request_type=draft["request_type"],
                            raw_description=draft["raw_description"],
                            category=draft["category"],
                            priority=draft["priority"],
                            recommended_action=draft["recommended_action"],
                        )
                        st.session_state.pop("triage_draft", None)
                        st.success(f"Created ticket `{ticket_code}` and added entry to maintenance history.")
                        st.rerun()
                else:
                    st.caption("Click **Run AI Triage** to classify the request and view troubleshooting steps before saving.")

            st.divider()
            st.subheader("Active & Historical Tickets")
            if tickets_list:
                st.dataframe(tickets_list, use_container_width=True, hide_index=True)
            else:
                st.info("No maintenance tickets created yet.")

    # ------------------------------------------------------------------
    # TAB 3: ML Anomaly Detection & Failure Analytics
    # ------------------------------------------------------------------
    with tab_analytics:
        st.subheader("ML Telemetry Anomaly Detection (IsolationForest)")
        st.caption("Evaluates operating metrics such as heat-up duration, vibration/noise level, pressure, and daily cycles.")

        base_telemetry = get_sample_telemetry_df()
        editable_telemetry = st.data_editor(
            base_telemetry,
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            key="telemetry_editor",
        )
        anomaly_results = detect_equipment_anomalies(editable_telemetry)
        st.markdown("**Anomaly Detection Output (Lowest score = highest deviation)**")
        st.dataframe(anomaly_results, use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("Frequently Failing Equipment (Repair & Ticket Counts)")
        st.dataframe(failure_df, use_container_width=True, hide_index=True)

    # ------------------------------------------------------------------
    # TAB 4: Preventive Schedule & AI Report Summarizer
    # ------------------------------------------------------------------
    with tab_schedule:
        st.subheader("Preventive Maintenance Schedule")
        st.dataframe(schedule_df, use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("AI Technician Report Summarizer & Log Saver")
        if asset_ids:
            s_col1, s_col2 = st.columns([1.1, 1])
            with s_col1:
                rep_asset = st.selectbox("Asset ID", asset_ids, key="report_asset_select")
                rep_tech = st.text_input("Technician Name", value="K. Watanabe", key="report_tech_input")
                rep_event_type = st.selectbox(
                    "Event Type to Log",
                    ["Repair", "Inspection", "Maintenance"],
                    key="report_event_type",
                )
                open_ticket_codes = [t["ticket_code"] for t in tickets_list if t["status"] != "Closed"]
                linked_ticket = st.selectbox(
                    "Link Open Ticket (Optional)",
                    ["None"] + open_ticket_codes,
                    key="report_linked_ticket",
                )
                close_linked = st.checkbox("Mark linked ticket as Closed upon saving", value=True)
                raw_notes = st.text_area(
                    "Raw Technician Field Notes",
                    value="Checked heating coil resistance and descaled inner kettle wall. Replaced worn agitator seal and re-tested heat-up time (19 mins, normal). Recommend ordering 1 spare seal kit for next month.",
                    height=120,
                )

                if st.button("Summarize Technician Report"):
                    summary_out = summarize_technician_report(rep_asset, rep_tech, raw_notes)
                    st.session_state["report_draft"] = {
                        "asset_id": rep_asset,
                        "technician_name": rep_tech,
                        "event_type": rep_event_type,
                        "ticket_code": None if linked_ticket == "None" else linked_ticket,
                        "close_ticket": close_linked,
                        **summary_out,
                    }

            with s_col2:
                st.markdown("**Structured Summary Preview**")
                rep_draft = st.session_state.get("report_draft")
                if rep_draft:
                    st.write(f"**Summary:** {rep_draft['summary']}")
                    st.write(f"**Parts Mentioned:** {rep_draft['parts_mentioned']}")
                    st.write(f"**Follow-up Action:** {rep_draft['follow_up_action']}")

                    if st.button("Save to Maintenance Logs"):
                        combined_summary = f"{rep_draft['summary']} | Follow-up: {rep_draft['follow_up_action']}"
                        add_maintenance_log(
                            conn=conn,
                            asset_id=rep_draft["asset_id"],
                            event_type=rep_draft["event_type"],
                            summary=combined_summary,
                            parts_used=rep_draft["parts_mentioned"],
                            technician_name=rep_draft["technician_name"],
                            ticket_code=rep_draft["ticket_code"],
                            close_ticket=rep_draft["close_ticket"],
                        )
                        st.session_state.pop("report_draft", None)
                        st.success("Saved summarized report to maintenance logs.")
                        st.rerun()
                else:
                    st.caption("Click **Summarize Technician Report** to generate a structured log entry.")
finally:
    conn.close()