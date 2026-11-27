import json
import os
from pathlib import Path
from typing import Any

MANUALS_PATH = Path("data/manuals.json")
ALLOWED_CATEGORIES = [
    "Heating / Thermal",
    "Mechanical / Noise",
    "Controls / Sensors",
    "Parts / Inspection",
]
ALLOWED_PRIORITIES = ["Low", "Medium", "High", "Critical"]


def load_manuals(manuals_path: Path = MANUALS_PATH) -> dict[str, list[str]]:
    """Load troubleshooting steps grouped by maintenance category."""
    with manuals_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _fallback_triage(description: str, request_type: str, manuals: dict[str, list[str]]) -> dict[str, str]:
    """Deterministic fallback when no AI API key is configured or an API call fails."""
    text = f"{request_type} {description}".lower()

    if any(word in text for word in ["noise", "grinding", "rattling", "vibration", "agitator", "bearing"]):
        category = "Mechanical / Noise"
    elif any(word in text for word in ["heat", "heating", "slow", "temperature", "steam", "boiler", "burn"]):
        category = "Heating / Thermal"
    elif any(word in text for word in ["sensor", "error", "display", "panel", "switch", "control"]):
        category = "Controls / Sensors"
    else:
        category = "Parts / Inspection"

    if any(word in text for word in ["leak", "smoke", "spark", "pressure", "stop", "critical", "safety"]):
        priority = "High"
    elif category in ("Heating / Thermal", "Mechanical / Noise"):
        priority = "Medium"
    else:
        priority = "Low"

    steps = manuals.get(category, ["Inspect equipment and log diagnostic readings."])
    action = f"[{category} | Priority: {priority}] " + " ".join(f"{i+1}. {s}" for i, s in enumerate(steps))
    return {
        "category": category,
        "priority": priority,
        "recommended_action": action,
    }


def triage_ticket(
    equipment_info: dict[str, Any],
    request_type: str,
    description: str,
    manuals_path: Path = MANUALS_PATH,
) -> dict[str, str]:
    """Classify a maintenance ticket, assign priority, and generate troubleshooting guidance."""
    manuals = load_manuals(manuals_path)
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        return _fallback_triage(description, request_type, manuals)

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        prompt = f"""
You are a senior service engineer for Hattori Kogyo commercial kitchen equipment.
Triage the incoming customer request using the provided equipment context and troubleshooting manuals.

Equipment:
- Asset ID: {equipment_info.get("asset_id")}
- Type: {equipment_info.get("equipment_type")}
- Model: {equipment_info.get("model_name")}
- Location: {equipment_info.get("kitchen_location")}

Request Type: {request_type}
Customer Description: {description}

Troubleshooting Manuals by Category:
{json.dumps(manuals, indent=2)}

Return ONLY valid JSON with keys:
- "category": one of {ALLOWED_CATEGORIES}
- "priority": one of {ALLOWED_PRIORITIES}
- "recommended_action": concise, actionable technician checklist combining relevant manual steps and equipment context.
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

        category = parsed.get("category", "Parts / Inspection")
        if category not in ALLOWED_CATEGORIES:
            category = "Parts / Inspection"

        priority = parsed.get("priority", "Medium")
        if priority not in ALLOWED_PRIORITIES:
            priority = "Medium"

        recommended_action = str(parsed.get("recommended_action", "")).strip()
        if not recommended_action:
            return _fallback_triage(description, request_type, manuals)

        return {
            "category": category,
            "priority": priority,
            "recommended_action": recommended_action,
        }
    except Exception:
        return _fallback_triage(description, request_type, manuals)