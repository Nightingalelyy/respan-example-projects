"""PATCH /api/models/{model_name}/ — Update a custom model"""
import os, json, requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))
BASE_URL = os.getenv("RESPAN_BASE_URL", "https://api.respan.ai")
API_KEY = os.getenv("RESPAN_API_KEY", "")
H = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

model_name = "REPLACE_ME"

resp = requests.patch(
    f"{BASE_URL}/api/models/{model_name}/",
    headers=H,
    json={
        "display_name": "Updated API Test Model",
        "input_cost": 0.002,
        "output_cost": 0.004,
    },
)
print(f"Status: {resp.status_code}")
print(json.dumps(resp.json(), indent=2, default=str))
