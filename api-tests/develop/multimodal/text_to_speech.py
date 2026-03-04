"""POST /api/audio/speech — Text to speech"""
import os, json, requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))
BASE_URL = os.getenv("RESPAN_BASE_URL", "https://api.respan.ai")
API_KEY = os.getenv("RESPAN_API_KEY", "")
H = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

resp = requests.post(
    f"{BASE_URL}/api/audio/speech",
    headers=H,
    json={
        "model": "tts-1",
        "input": "Hello, this is a test.",
        "voice": "alloy",
        "response_format": "mp3",
        "speed": 1.0,
    },
)
print(f"Status: {resp.status_code}")
print(f"Content-Type: {resp.headers.get('content-type')}")
print(f"Content-Length: {len(resp.content)} bytes")
