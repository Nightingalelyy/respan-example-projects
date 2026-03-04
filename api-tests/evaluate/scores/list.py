"""GET /api/scores/ — List scores"""
import os, json, requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))
BASE_URL = os.getenv("RESPAN_BASE_URL", "https://api.respan.ai")
API_KEY = os.getenv("RESPAN_API_KEY", "")
H = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

resp = requests.get(
    f"{BASE_URL}/api/scores/",
    headers=H,
)
print(f"Status: {resp.status_code}")
print(json.dumps(resp.json(), indent=2, default=str))
