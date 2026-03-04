"""POST /api/logs/{log_id}/scores/ — Create a log score"""
import os, json, requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))
BASE_URL = os.getenv("RESPAN_BASE_URL", "https://api.respan.ai")
API_KEY = os.getenv("RESPAN_API_KEY", "")
H = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

log_id = "REPLACE_ME"

resp = requests.post(
    f"{BASE_URL}/api/logs/{log_id}/scores/",
    headers=H,
    json={
        "evaluator_slug": "REPLACE_ME",
        "numerical_value": 0.9,
        "boolean_value": True,
    },
)
print(f"Status: {resp.status_code}")
print(json.dumps(resp.json(), indent=2, default=str))
