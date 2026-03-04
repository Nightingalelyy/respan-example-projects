"""POST /api/models/ — Create a custom model"""
import os, json, requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))
BASE_URL = os.getenv("RESPAN_BASE_URL", "https://api.respan.ai")
API_KEY = os.getenv("RESPAN_API_KEY", "")
H = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

resp = requests.post(
    f"{BASE_URL}/api/models/",
    headers=H,
    json={
        "model_name": "api-test-model",
        "display_name": "API Test Model",
        "input_cost": 0.001,
        "output_cost": 0.002,
        "cache_hit_input_cost": 0.0005,
        "cache_creation_input_cost": 0.0015,
        "max_context_window": 128000,
        "streaming_support": 1,
        "function_call": 1,
        "image_support": 0,
    },
)
print(f"Status: {resp.status_code}")
print(json.dumps(resp.json(), indent=2, default=str))
