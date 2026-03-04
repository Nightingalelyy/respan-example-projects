"""GET /api/users/list/ — List users"""
import os, json, requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))
BASE_URL = os.getenv("RESPAN_BASE_URL", "https://api.respan.ai")
API_KEY = os.getenv("RESPAN_API_KEY", "")
H = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

resp = requests.get(
    f"{BASE_URL}/api/users/list/",
    headers=H,
    params={
        "page": 1,
        "page_size": 10,
        "sort_by": "-first_seen",
        "environment": "prod",
    },
)
print(f"Status: {resp.status_code}")
print(json.dumps(resp.json(), indent=2, default=str))
