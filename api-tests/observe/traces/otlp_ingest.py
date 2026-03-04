"""POST /api/v2/traces — Ingest traces via OTLP format"""
import os, json, requests, time
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))
BASE_URL = os.getenv("RESPAN_BASE_URL", "https://api.respan.ai")
API_KEY = os.getenv("RESPAN_API_KEY", "")
H = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

now_ns = int(time.time() * 1e9)
duration_ns = int(1.5 * 1e9)

resp = requests.post(
    f"{BASE_URL}/api/v2/traces",
    headers=H,
    json={
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": "api-test-service"}},
                    ]
                },
                "scopeSpans": [
                    {
                        "scope": {
                            "name": "api-test",
                            "version": "1.0.0",
                        },
                        "spans": [
                            {
                                "traceId": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4",
                                "spanId": "1a2b3c4d5e6f7a8b",
                                "name": "llm-call",
                                "kind": 1,
                                "startTimeUnixNano": str(now_ns - duration_ns),
                                "endTimeUnixNano": str(now_ns),
                                "status": {
                                    "code": 1,
                                    "message": "OK",
                                },
                                "attributes": [
                                    {"key": "gen_ai.system", "value": {"stringValue": "openai"}},
                                    {"key": "gen_ai.request.model", "value": {"stringValue": "gpt-4o"}},
                                    {"key": "gen_ai.usage.prompt_tokens", "value": {"intValue": "15"}},
                                    {"key": "gen_ai.usage.completion_tokens", "value": {"intValue": "25"}},
                                ],
                            },
                        ],
                    },
                ],
            },
        ],
    },
)
print(f"Status: {resp.status_code}")
print(json.dumps(resp.json(), indent=2, default=str))
