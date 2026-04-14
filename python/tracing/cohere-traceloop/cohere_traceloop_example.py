#!/usr/bin/env python3
"""
Cohere + Traceloop instrumentation example for Respan tracing.

Uses opentelemetry-instrumentation-cohere (Traceloop) to auto-instrument the
Cohere Python SDK and exports spans to Respan.

Since Cohere uses its own API format (v2/chat), a local HTTP proxy translates
Cohere requests to OpenAI chat completions format for the Respan gateway.
"""
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import requests as http_requests
from dotenv import load_dotenv

ROOT_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(ROOT_ENV_PATH, override=True)

RESPAN_API_KEY = os.getenv("RESPAN_GATEWAY_API_KEY") or os.getenv("RESPAN_API_KEY")
RESPAN_BASE_URL = (
    os.getenv("RESPAN_GATEWAY_BASE_URL")
    or os.getenv("RESPAN_BASE_URL")
    or "https://api.respan.ai/api"
).rstrip("/")


class CohereToOpenAIProxy(BaseHTTPRequestHandler):
    """Translates Cohere v2/chat requests to OpenAI chat completions."""

    def log_message(self, format, *args):
        pass

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(content_length)) if content_length else {}

        messages = []
        for msg in body.get("messages", []):
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if isinstance(content, list):
                content = " ".join(
                    p.get("text", "") for p in content if isinstance(p, dict) and "text" in p
                )
            if content:
                messages.append({"role": role, "content": content})

        openai_body = {
            "model": "gpt-4o-mini",
            "messages": messages,
            "temperature": body.get("temperature", 0),
            "max_tokens": body.get("max_tokens", 256),
        }

        resp = http_requests.post(
            f"{RESPAN_BASE_URL}/chat/completions",
            json=openai_body,
            headers={
                "Authorization": f"Bearer {RESPAN_API_KEY}",
                "Content-Type": "application/json",
            },
        )

        if resp.status_code != 200:
            self._send_json(resp.status_code, resp.json())
            return

        openai_resp = resp.json()
        choice = openai_resp.get("choices", [{}])[0]
        usage = openai_resp.get("usage", {})

        cohere_resp = {
            "id": openai_resp.get("id", "gen-001"),
            "finish_reason": "COMPLETE",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": choice.get("message", {}).get("content", "")}],
            },
            "usage": {
                "billed_units": {
                    "input_tokens": usage.get("prompt_tokens", 0),
                    "output_tokens": usage.get("completion_tokens", 0),
                },
                "tokens": {
                    "input_tokens": usage.get("prompt_tokens", 0),
                    "output_tokens": usage.get("completion_tokens", 0),
                },
            },
        }

        self._send_json(200, cohere_resp)

    def _send_json(self, status, data):
        payload = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def start_proxy():
    server = HTTPServer(("127.0.0.1", 0), CohereToOpenAIProxy)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{port}"


proxy_server, proxy_url = start_proxy()

from opentelemetry.instrumentation.cohere import CohereInstrumentor
from respan_tracing import RespanTelemetry
from respan_tracing.decorators import workflow

telemetry = RespanTelemetry(
    app_name="cohere-traceloop-example",
    api_key=RESPAN_API_KEY,
    is_batching_enabled=False,
    instruments=set(),
)

CohereInstrumentor().instrument()

import cohere

client = cohere.ClientV2(
    api_key="proxy-passthrough",
    base_url=proxy_url,
)


@workflow(name="cohere_traceloop_workflow")
def cohere_workflow(topic: str) -> str:
    response = client.chat(
        model="command-r-plus",
        messages=[
            {"role": "user", "content": f"Write a haiku about {topic}. Output ONLY the haiku."},
        ],
        temperature=0,
        max_tokens=256,
    )
    return response.message.content[0].text


def main() -> None:
    print("=" * 60)
    print("Cohere Traceloop Example")
    print("=" * 60)

    if not RESPAN_API_KEY:
        print("Skipping: RESPAN_API_KEY not set.")
        return

    try:
        result = cohere_workflow(topic="recursion in programming")
        print(result)
    finally:
        telemetry.flush()
        proxy_server.shutdown()


if __name__ == "__main__":
    main()
