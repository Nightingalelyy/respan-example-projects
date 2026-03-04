"""PATCH /api/prompts/{prompt_id}/versions/{version_id}/ — Update a prompt version"""
import os, json, requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))
BASE_URL = os.getenv("RESPAN_BASE_URL", "https://api.respan.ai")
API_KEY = os.getenv("RESPAN_API_KEY", "")
H = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

prompt_id = "REPLACE_ME"
version_id = "REPLACE_ME"

resp = requests.patch(
    f"{BASE_URL}/api/prompts/{prompt_id}/versions/{version_id}/",
    headers=H,
    json={
        "messages": [
            {"role": "system", "content": "You are an updated assistant."},
            {"role": "user", "content": "{{user_input}}"},
        ],
        "model": "gpt-4o",
        "description": "Updated version via API",
        "temperature": 0.5,
        "max_tokens": 512,
        "deploy": False,
    },
)
print(f"Status: {resp.status_code}")
print(json.dumps(resp.json(), indent=2, default=str))
