"""POST /api/v2/experiments/ — Create an experiment"""
import os, json, requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))
BASE_URL = os.getenv("RESPAN_BASE_URL", "https://api.respan.ai")
API_KEY = os.getenv("RESPAN_API_KEY", "")
H = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

resp = requests.post(
    f"{BASE_URL}/api/v2/experiments/",
    headers=H,
    json={
        "name": "api-test-experiment",
        "description": "An experiment created via API",
        "dataset_id": "REPLACE_ME",
        "workflows": [
            {
                "type": "prompt",
                "config": {
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "user", "content": "{{input}}"},
                    ],
                },
            },
        ],
        "evaluator_slugs": [
            "faithfulness",
            "answer_relevancy",
        ],
    },
)
print(f"Status: {resp.status_code}")
print(json.dumps(resp.json(), indent=2, default=str))
