#!/usr/bin/env python3
"""
Aleph Alpha + Traceloop instrumentation example for Respan tracing.

Uses opentelemetry-instrumentation-alephalpha (Traceloop) to auto-instrument the
Aleph Alpha Python SDK and exports spans to Respan.

The Aleph Alpha SDK uses its own /complete endpoint format. A local HTTP proxy
translates these requests to OpenAI chat completions for the Respan gateway
and converts responses back to the Aleph Alpha format.
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


class AlephAlphaToOpenAIProxy(BaseHTTPRequestHandler):
    """Translates Aleph Alpha /complete requests to OpenAI chat completions."""

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if "/version" in self.path or "/models_available" in self.path:
            self._send_json(200, [])
        else:
            self._send_json(200, {})

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(content_length)) if content_length else {}

        if "complete" in self.path:
            self._handle_complete(body)
        else:
            self._send_json(200, {"status": "ok"})

    def _handle_complete(self, body):
        prompt_parts = body.get("prompt", [])
        prompt_text = ""
        for part in prompt_parts:
            if isinstance(part, dict) and part.get("type") == "text":
                prompt_text += part.get("data", "")
            elif isinstance(part, str):
                prompt_text += part

        openai_body = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt_text}],
            "temperature": body.get("temperature", 0),
            "max_tokens": body.get("maximum_tokens", 256),
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

        aleph_resp = {
            "model_version": body.get("model", "luminous-base"),
            "completions": [
                {
                    "completion": choice.get("message", {}).get("content", ""),
                    "finish_reason": "maximum_tokens",
                }
            ],
            "num_tokens_prompt_total": usage.get("prompt_tokens", 0),
            "num_tokens_generated": usage.get("completion_tokens", 0),
        }

        self._send_json(200, aleph_resp)

    def _send_json(self, status, data):
        payload = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def start_proxy():
    server = HTTPServer(("127.0.0.1", 0), AlephAlphaToOpenAIProxy)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{port}"


proxy_server, proxy_url = start_proxy()

from opentelemetry.instrumentation.alephalpha import AlephAlphaInstrumentor
from respan_tracing import RespanTelemetry
from respan_tracing.decorators import workflow

telemetry = RespanTelemetry(
    app_name="alephalpha-traceloop-example",
    api_key=RESPAN_API_KEY,
    is_batching_enabled=False,
    instruments=set(),
)

AlephAlphaInstrumentor().instrument()

from aleph_alpha_client import Client, CompletionRequest, Prompt

client = Client(
    token="proxy-passthrough",
    host=proxy_url,
)


@workflow(name="alephalpha_traceloop_workflow")
def alephalpha_workflow(topic: str) -> str:
    prompt = Prompt.from_text(f"Write a haiku about {topic}. Output ONLY the haiku.")
    request = CompletionRequest(
        prompt=prompt,
        maximum_tokens=256,
        temperature=0,
    )
    response = client.complete(request, model="luminous-base")
    return response.completions[0].completion


def main() -> None:
    print("=" * 60)
    print("Aleph Alpha Traceloop Example")
    print("=" * 60)

    if not RESPAN_API_KEY:
        print("Skipping: RESPAN_API_KEY not set.")
        return

    try:
        result = alephalpha_workflow(topic="recursion in programming")
        print(result)
    finally:
        telemetry.flush()
        proxy_server.shutdown()


if __name__ == "__main__":
    main()
