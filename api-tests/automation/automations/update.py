"""PATCH /automation/automations/{automation_id}/ — Update an automation"""
import os, json, requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))
BASE_URL = os.getenv("RESPAN_BASE_URL", "https://api.respan.ai")
API_KEY = os.getenv("RESPAN_API_KEY", "")
H = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

automation_id = "REPLACE_ME"

resp = requests.patch(
    f"{BASE_URL}/automation/automations/{automation_id}/",
    headers=H,
    json={
        "is_enabled": False,
        "configuration": {
            "sampling_rate": 0.5,
        },
        "evaluator_ids": ["REPLACE_ME"],
    },
)
print(f"Status: {resp.status_code}")
print(json.dumps(resp.json(), indent=2, default=str))
