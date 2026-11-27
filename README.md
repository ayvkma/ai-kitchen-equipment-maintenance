# AI Kitchen Equipment Maintenance System (`ai-kitchen-equipment-maintenance`)

An IT + DX (Digital Transformation) maintenance management system built for commercial kitchen equipment manufacturers and service teams. It connects equipment lifecycle tracking, AI-assisted ticket triage, ML telemetry anomaly detection, failure analytics, and preventive maintenance scheduling in a single Streamlit + SQLite application.

## Core Capabilities

1. **Equipment Registry & Lifecycle History (`db/`)**
   - Registers commercial kitchen units (steam kettles, mixing kettles, IH rice cookers, pressure cookers) with unique asset IDs (`HT-...`), customer locations, installation dates, and service intervals.
   - Maintains an append-only `maintenance_logs` audit trail across installations, inspections, repairs, and ticket events.

2. **Customer Request Intake & AI Triage (`services/ai_triage.py`, `data/manuals.json`)**
   - Accepts requests for repairs, maintenance, replacement parts, technical support, and inspections.
   - Classifies the issue category, assigns priority, and retrieves matching troubleshooting steps from `data/manuals.json` using the Gemini API (with a deterministic rule-based fallback when no API key is set).

3. **ML Anomaly Detection & Failure Analytics (`services/anomaly.py`)**
   - Uses `scikit-learn` `IsolationForest` to flag abnormal operating profiles (heat-up duration, vibration/noise dB, operating pressure, daily cycles).
   - Aggregates repair and ticket counts per unit via SQL + `pandas` to surface frequently failing equipment.

4. **Preventive Schedule & AI Technician Report Summarizer (`services/scheduler_ai.py`)**
   - Calculates next due dates from the latest service event plus `maintenance_interval_days` (`Overdue`, `Due Soon`, `Scheduled`).
   - Summarizes raw technician field notes into structured summaries, parts used, and follow-up actions, optionally closing linked tickets upon saving.

## Tech Stack

- **UI:** Streamlit
- **Database:** SQLite (`sqlite3` with foreign-key enforcement)
- **Data & ML:** Pandas, Scikit-Learn (`IsolationForest`)
- **Generative AI:** Google GenAI SDK (`gemini-2.5-flash`) with offline rule fallback
- **Testing:** Pytest

## Quickstart

```bash
git clone [https://github.com/](https://github.com/)<your-username>/ai-kitchen-equipment-maintenance.git
cd ai-kitchen-equipment-maintenance
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt