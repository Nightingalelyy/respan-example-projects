"""PATCH /api/temporary-keys/{key_id}/ — Update a temporary API key"""
import os, json, requests
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone

load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))
BASE_URL = os.getenv("RESPAN_BASE_URL", "https://api.respan.ai")
API_KEY = os.getenv("RESPAN_API_KEY", "")
H = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

key_id = "REPLACE_ME"

expiry_date = (datetime.now(timezone.utc) + timedelta(days=14)).isoformat()

resp = requests.patch(
    f"{BASE_URL}/api/temporary-keys/{key_id}/",
    headers=H,
    json={
        "name": "api-test-key-updated",
        "expiry_date": expiry_date,
        "is_test": True,
        "prefix": "updated-",
    },
)
print(f"Status: {resp.status_code}")
print(json.dumps(resp.json(), indent=2, default=str))
