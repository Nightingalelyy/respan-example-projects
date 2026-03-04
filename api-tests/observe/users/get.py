"""GET /api/users/{customer_identifier}/ — Get a single user"""
import os, json, requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))
BASE_URL = os.getenv("RESPAN_BASE_URL", "https://api.respan.ai")
API_KEY = os.getenv("RESPAN_API_KEY", "")
H = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

# Replace with an actual customer_identifier from your users
customer_identifier = "REPLACE_ME"

resp = requests.get(
    f"{BASE_URL}/api/users/{customer_identifier}/",
    headers=H,
)
print(f"Status: {resp.status_code}")
print(json.dumps(resp.json(), indent=2, default=str))
