"""GET /api/models/public — List public models (no auth required)"""
import os, json, requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))
BASE_URL = os.getenv("RESPAN_BASE_URL", "https://api.respan.ai")

resp = requests.get(
    f"{BASE_URL}/api/models/public",
)
print(f"Status: {resp.status_code}")
print(json.dumps(resp.json(), indent=2, default=str))
