"""POST /api/audio/transcription — Speech to text (Whisper)"""
import os, json, requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))
BASE_URL = os.getenv("RESPAN_BASE_URL", "https://api.respan.ai")
API_KEY = os.getenv("RESPAN_API_KEY", "")
H = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

audio_file_path = "REPLACE_ME"  # Path to an audio file (e.g., .mp3, .wav)

# Auth-only headers for multipart form upload (no Content-Type)
h = {"Authorization": f"Bearer {API_KEY}"}

resp = requests.post(
    f"{BASE_URL}/api/audio/transcription",
    headers=h,
    files={"file": open(audio_file_path, "rb")},
    data={
        "model": "whisper-1",
        "language": "en",
        "prompt": "",
        "response_format": "json",
        "temperature": 0,
    },
)
print(f"Status: {resp.status_code}")
print(json.dumps(resp.json(), indent=2, default=str))
