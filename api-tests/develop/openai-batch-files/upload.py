"""POST /api/files/ — Upload a batch file"""
import os, json, requests, tempfile
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))
BASE_URL = os.getenv("RESPAN_BASE_URL", "https://api.respan.ai")
API_KEY = os.getenv("RESPAN_API_KEY", "")
H = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

# Create a temporary JSONL file with sample batch requests
jsonl_content = json.dumps({
    "custom_id": "request-1",
    "method": "POST",
    "url": "/v1/chat/completions",
    "body": {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": "Hello"}],
        "max_tokens": 10,
    },
})

tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
tmp.write(jsonl_content + "\n")
tmp.close()

# Auth-only headers for multipart form upload (no Content-Type)
h = {"Authorization": f"Bearer {API_KEY}"}

resp = requests.post(
    f"{BASE_URL}/api/files/",
    headers=h,
    files={"file": open(tmp.name, "rb")},
    data={"purpose": "batch"},
)

os.unlink(tmp.name)

print(f"Status: {resp.status_code}")
print(json.dumps(resp.json(), indent=2, default=str))
