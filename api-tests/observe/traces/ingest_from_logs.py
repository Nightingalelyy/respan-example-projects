"""POST /api/v1/traces/ingest — Ingest traces from log objects"""
import os, json, requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))
BASE_URL = os.getenv("RESPAN_BASE_URL", "https://api.respan.ai")
API_KEY = os.getenv("RESPAN_API_KEY", "")
H = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

resp = requests.post(
    f"{BASE_URL}/api/v1/traces/ingest",
    headers=H,
    json=[
        {
            "trace_unique_id": "trace-v1-001",
            "span_unique_id": "span-v1-001",
            "input": "Explain reinforcement learning.",
            "output": "Reinforcement learning is a type of machine learning where an agent learns to make decisions by interacting with an environment.",
            "model": "gpt-4o",
        },
        {
            "trace_unique_id": "trace-v1-001",
            "span_unique_id": "span-v1-002",
            "input": "Give an example of reinforcement learning.",
            "output": "A classic example is training an AI to play chess by rewarding winning moves.",
            "model": "gpt-4o",
        },
    ],
)
print(f"Status: {resp.status_code}")
print(json.dumps(resp.json(), indent=2, default=str))
