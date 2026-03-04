"""POST /api/providers/ — Create a custom provider"""
import os, json, requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))
BASE_URL = os.getenv("RESPAN_BASE_URL", "https://api.respan.ai")
API_KEY = os.getenv("RESPAN_API_KEY", "")
H = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

resp = requests.post(
    f"{BASE_URL}/api/providers/",
    headers=H,
    json={
        "provider_id": "api-test-provider",
        "provider_name": "API Test Provider",
        "api_key": "sk-test",
        "extra_kwargs": {
            "base_url": "https://api.example.com/v1",
        },
    },
)
print(f"Status: {resp.status_code}")
print(json.dumps(resp.json(), indent=2, default=str))
