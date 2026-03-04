"""PATCH /api/datasets/{dataset_id}/ — Update a dataset"""
import os, json, requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))
BASE_URL = os.getenv("RESPAN_BASE_URL", "https://api.respan.ai")
API_KEY = os.getenv("RESPAN_API_KEY", "")
H = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

dataset_id = "REPLACE_ME"

resp = requests.patch(
    f"{BASE_URL}/api/datasets/{dataset_id}/",
    headers=H,
    json={
        "name": "api-test-dataset-updated",
        "description": "Updated test dataset",
    },
)
print(f"Status: {resp.status_code}")
print(json.dumps(resp.json(), indent=2, default=str))
