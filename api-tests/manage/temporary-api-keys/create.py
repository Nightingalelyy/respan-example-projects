"""POST /api/temporary-keys/ — Create a temporary API key"""
import os, json, requests
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone

load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))
BASE_URL = os.getenv("RESPAN_BASE_URL", "https://api.respan.ai")
API_KEY = os.getenv("RESPAN_API_KEY", "")
H = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

expiry_date = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()

resp = requests.post(
    f"{BASE_URL}/api/temporary-keys/",
    headers=H,
    json={
        "name": "api-test-key",
        "expiry_date": expiry_date,
        "max_usage": 100,
        "rate_limit": 60,
        "spending_limit": 10.0,
        "is_test": True,
    },
)
print(f"Status: {resp.status_code}")
print(json.dumps(resp.json(), indent=2, default=str))
