"""PATCH /api/users/{customer_identifier}/ — Update a user"""
import os, json, requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))
BASE_URL = os.getenv("RESPAN_BASE_URL", "https://api.respan.ai")
API_KEY = os.getenv("RESPAN_API_KEY", "")
H = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

# Replace with an actual customer_identifier to update
customer_identifier = "REPLACE_ME"

resp = requests.patch(
    f"{BASE_URL}/api/users/{customer_identifier}/",
    headers=H,
    json={
        "email": "testuser@example.com",
        "name": "Test User",
        "metadata": {"role": "developer", "team": "engineering"},
        "period_budget": 100.0,
        "budget_duration": "monthly",
        "total_budget": 1000.0,
        "markup_percentage": 15.0,
    },
)
print(f"Status: {resp.status_code}")
print(json.dumps(resp.json(), indent=2, default=str))
