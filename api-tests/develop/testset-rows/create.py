"""POST /api/testsets/{testset_id}/rows — Create testset rows"""
import os, json, requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))
BASE_URL = os.getenv("RESPAN_BASE_URL", "https://api.respan.ai")
API_KEY = os.getenv("RESPAN_API_KEY", "")
H = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

testset_id = "REPLACE_ME"

resp = requests.post(
    f"{BASE_URL}/api/testsets/{testset_id}/rows",
    headers=H,
    json={
        "row_data": [
            {"input": "What is AI?", "expected_output": "Artificial Intelligence"},
            {"input": "What is ML?", "expected_output": "Machine Learning"},
        ],
    },
)
print(f"Status: {resp.status_code}")
print(json.dumps(resp.json(), indent=2, default=str))
