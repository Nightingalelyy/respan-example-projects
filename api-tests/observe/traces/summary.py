"""POST /clickhouse/traces/summary/ — Get traces summary"""
import os, json, requests
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone

load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))
BASE_URL = os.getenv("RESPAN_BASE_URL", "https://api.respan.ai")
API_KEY = os.getenv("RESPAN_API_KEY", "")
H = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

now = datetime.now(timezone.utc)
start_time = (now - timedelta(hours=24)).isoformat()
end_time = now.isoformat()

resp = requests.post(
    f"{BASE_URL}/clickhouse/traces/summary/",
    headers=H,
    params={
        "start_time": start_time,
        "end_time": end_time,
    },
    json={"filters": {}},
)
print(f"Status: {resp.status_code}")
print(json.dumps(resp.json(), indent=2, default=str))
