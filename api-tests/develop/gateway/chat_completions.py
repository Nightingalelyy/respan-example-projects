"""POST /api/chat/completions — Create a chat completion"""
import os, json, requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))
BASE_URL = os.getenv("RESPAN_BASE_URL", "https://api.respan.ai")
API_KEY = os.getenv("RESPAN_API_KEY", "")
H = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

resp = requests.post(
    f"{BASE_URL}/api/chat/completions",
    headers=H,
    json={
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Say hello in one word."},
        ],
        "stream": False,
        "temperature": 0.7,
        "max_tokens": 10,
        "top_p": 1.0,
        "frequency_penalty": 0,
        "presence_penalty": 0,
        "stop": ["\n"],
        "response_format": {"type": "text"},
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get weather",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {"type": "string"},
                        },
                        "required": ["location"],
                    },
                },
            }
        ],
        "tool_choice": "auto",
        "metadata": {"test": True},
        "customer_identifier": "api-test-user",
        "customer_params": {},
        "cache_enabled": False,
    },
)
print(f"Status: {resp.status_code}")
print(json.dumps(resp.json(), indent=2, default=str))
